import logging
from app.models.schemas import (
    AgentSession, AgentResponse, SessionState,
    CandidatePool, AuditLogEntry
)
from app.agent.file_parser import parse_and_validate
from app.services.pool_cache import pool_cache
from app.services.session_store import get_session, save_session, purge_after_completion, purge_on_cancel
from app.services.audit_log import write_audit_log
from app.workday.connector import workday_connector

logger = logging.getLogger(__name__)


async def handle_file_upload(
    session: AgentSession,
    file_content_base64: str,
    filename: str,
) -> AgentResponse:
    """Parse and validate the uploaded xlsx file."""
    try:
        parse_result, warnings = parse_and_validate(file_content_base64)
    except ValueError as e:
        return AgentResponse(
            session_id=session.session_id,
            state=SessionState.ERROR,
            message=f"I could not read your file: {str(e)}. Please check the format and try again.",
            success=False,
        )

    session.parse_result = parse_result

    if parse_result.invalid_count > 0:
        error_lines = []
        seen_rows = set()
        for err in parse_result.invalid_records:
            if err.row_number not in seen_rows:
                seen_rows.add(err.row_number)
                row_errors = [
                    e for e in parse_result.invalid_records if e.row_number == err.row_number
                ]
                reasons = "; ".join(e.reason for e in row_errors)
                error_lines.append(f"  Row {err.row_number}: {reasons}")

        error_summary = "\n".join(error_lines[:20])
        if len(seen_rows) > 20:
            error_summary += f"\n  ... and {len(seen_rows) - 20} more rows with errors"

        message = (
            f"I found {parse_result.total_rows} candidates in your file, "
            f"but {parse_result.invalid_count} rows have issues that need to be fixed before I can proceed:\n\n"
            f"{error_summary}\n\n"
            f"Please correct these rows and re-upload the file."
        )
        session.state = SessionState.FILE_PARSED
        save_session(session)
        return AgentResponse(
            session_id=session.session_id,
            state=session.state,
            message=message,
            parse_result=parse_result,
            success=False,
        )

    # All records valid - fetch pool list
    try:
        pools = await pool_cache.get_pools()
    except Exception as e:
        logger.error(f"Failed to fetch pools: {e}")
        return AgentResponse(
            session_id=session.session_id,
            state=SessionState.ERROR,
            message="I could not retrieve the candidate pool list from Workday. Please try again in a moment.",
            success=False,
        )

    session.available_pools = pools
    session.state = SessionState.AWAITING_POOL_SELECTION
    save_session(session)

    pool_list = "\n".join(f"  - {p.pool_name}" for p in pools)
    message = (
        f"I found {parse_result.valid_count} valid candidates in **{filename}**. "
        f"Which candidate pool should I add them to?\n\n{pool_list}"
    )

    return AgentResponse(
        session_id=session.session_id,
        state=session.state,
        message=message,
        available_pools=pools,
        parse_result=parse_result,
    )


async def handle_message(session: AgentSession, message: str) -> AgentResponse:
    """Route recruiter messages based on current session state."""

    if session.state == SessionState.AWAITING_POOL_SELECTION:
        return await _handle_pool_selection(session, message)

    if session.state == SessionState.AWAITING_CONFIRMATION:
        return await _handle_confirmation(session, message)

    return AgentResponse(
        session_id=session.session_id,
        state=session.state,
        message="Please upload a candidate file to get started.",
        success=False,
    )


async def _handle_pool_selection(session: AgentSession, message: str) -> AgentResponse:
    pool = pool_cache.find_pool(message)

    if not pool:
        pool_list = "\n".join(f"  - {p.pool_name}" for p in session.available_pools)
        return AgentResponse(
            session_id=session.session_id,
            state=session.state,
            message=(
                f"I couldn't find a pool matching '{message}'. "
                f"Please choose from the available pools:\n\n{pool_list}"
            ),
            available_pools=session.available_pools,
            success=False,
        )

    session.selected_pool = pool
    session.state = SessionState.AWAITING_CONFIRMATION
    save_session(session)

    count = session.parse_result.valid_count
    return AgentResponse(
        session_id=session.session_id,
        state=session.state,
        message=(
            f"Ready to add **{count} candidates** to **{pool.pool_name}**. "
            f"Type **confirm** to proceed or **cancel** to stop."
        ),
    )


async def _handle_confirmation(session: AgentSession, message: str) -> AgentResponse:
    text = message.strip().lower()

    if text in ("cancel", "no", "stop"):
        purge_on_cancel(session.session_id)
        return AgentResponse(
            session_id=session.session_id,
            state=SessionState.AWAITING_FILE,
            message="Cancelled. Upload a new file whenever you're ready.",
        )

    if text not in ("confirm", "yes", "ok", "proceed"):
        return AgentResponse(
            session_id=session.session_id,
            state=session.state,
            message="Please type **confirm** to proceed or **cancel** to stop.",
            success=False,
        )

    return await _execute_pool_load(session)


async def _execute_pool_load(session: AgentSession) -> AgentResponse:
    candidates = session.parse_result.valid_records
    pool = session.selected_pool

    try:
        succeeded, failed = await workday_connector.add_candidates_to_pool(
            pool_id=pool.pool_id,
            candidates=candidates,
        )
    except Exception as e:
        logger.error(f"Workday API error during pool load session_id={session.session_id} error_type={type(e).__name__}")
        purge_after_completion(session.session_id)
        return AgentResponse(
            session_id=session.session_id,
            state=SessionState.ERROR,
            message="Something went wrong while loading candidates into Workday. Please try again.",
            success=False,
        )

    write_audit_log(AuditLogEntry(
        session_id=session.session_id,
        recruiter_id=session.recruiter_id,
        pool_id=pool.pool_id,
        pool_name=pool.pool_name,
        records_submitted=len(candidates),
        records_succeeded=len(succeeded),
        records_failed=len(failed),
    ))

    # Purge session immediately — candidate data must not persist in memory
    # beyond the completion of the Workday API call.
    purge_after_completion(session.session_id)

    if not failed:
        message = (
            f"Done! All **{len(succeeded)} candidates** have been added to **{pool.pool_name}**."
        )
    else:
        # Surface row numbers only — do not include emails in the response
        # message since it may be logged by the Teams bot or Copilot Studio.
        failed_lines = "\n".join(
            f"  Row {f['row_number']}: {f['reason']}" for f in failed[:20]
        )
        message = (
            f"Completed with some issues.\n\n"
            f"**{len(succeeded)} candidates** added successfully to **{pool.pool_name}**.\n\n"
            f"**{len(failed)} candidates** could not be added:\n{failed_lines}\n\n"
            f"Please fix and resubmit the failed records."
        )

    return AgentResponse(
        session_id=session.session_id,
        state=SessionState.COMPLETE,
        message=message,
        success=True,
    )
