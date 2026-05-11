from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import (
    UploadRequest, MessageRequest, AgentResponse, SessionState
)
from app.services.session_store import create_session, get_session, save_session
from app.services.audit_log import get_audit_log
from app.agent.conversation_manager import handle_file_upload, handle_message

router = APIRouter()


@router.post("/session/start", response_model=AgentResponse)
async def start_session(recruiter_id: str = Query(...)):
    """Create a new agent session for a recruiter."""
    session = create_session(recruiter_id)
    return AgentResponse(
        session_id=session.session_id,
        state=session.state,
        message="Ready. Please upload your LinkedIn Recruiter export (xlsx) to get started.",
    )


@router.post("/upload", response_model=AgentResponse)
async def upload_file(request: UploadRequest):
    """Accept a base64-encoded xlsx file and begin the validation flow."""
    session = get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Please start a new session.")

    if session.recruiter_id != request.recruiter_id:
        raise HTTPException(status_code=403, detail="Recruiter ID does not match session.")

    # Reset state if recruiter uploads a new file mid-flow
    if session.state not in (SessionState.AWAITING_FILE, SessionState.FILE_PARSED, SessionState.COMPLETE):
        session.state = SessionState.AWAITING_FILE
        save_session(session)

    return await handle_file_upload(session, request.file_content_base64, request.filename)


@router.post("/message", response_model=AgentResponse)
async def send_message(request: MessageRequest):
    """Handle a recruiter message (pool selection or confirmation)."""
    session = get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Please start a new session.")

    if session.recruiter_id != request.recruiter_id:
        raise HTTPException(status_code=403, detail="Recruiter ID does not match session.")

    return await handle_message(session, request.message)


@router.get("/audit")
async def get_audit_entries(
    recruiter_id: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
):
    """Return audit log entries. Optionally filter by recruiter."""
    return get_audit_log(recruiter_id=recruiter_id, limit=limit)


@router.get("/pools/refresh", response_model=dict)
async def refresh_pool_cache():
    """Force a refresh of the candidate pool list from Workday."""
    from app.services.pool_cache import pool_cache
    pools = await pool_cache.get_pools(force_refresh=True)
    return {"message": f"Pool cache refreshed. {len(pools)} pools loaded."}
