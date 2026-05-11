import uuid
import time
import logging
from app.models.schemas import AgentSession, SessionState

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 3600  # 1 hour

# Internal store: session_id -> (AgentSession, created_at_epoch)
_sessions: dict[str, tuple[AgentSession, float]] = {}


def create_session(recruiter_id: str) -> AgentSession:
    session = AgentSession(
        session_id=str(uuid.uuid4()),
        recruiter_id=recruiter_id,
        state=SessionState.AWAITING_FILE,
    )
    _sessions[session.session_id] = (session, time.monotonic())
    logger.info(f"Session created session_id={session.session_id}")
    return session


def get_session(session_id: str) -> AgentSession | None:
    entry = _sessions.get(session_id)
    if entry is None:
        return None
    session, created_at = entry
    if time.monotonic() - created_at > SESSION_TTL_SECONDS:
        _purge(session_id, reason="ttl_expired")
        return None
    return session


def save_session(session: AgentSession):
    entry = _sessions.get(session.session_id)
    created_at = entry[1] if entry else time.monotonic()
    _sessions[session.session_id] = (session, created_at)


def purge_after_completion(session_id: str):
    """
    Explicitly delete the session and all candidate data it holds
    immediately after a pool load completes (success or failure).

    This is the primary data-minimisation control: candidate records
    parsed into memory during the session are freed here and never
    written to any persistent store.
    """
    _purge(session_id, reason="load_complete")


def purge_on_cancel(session_id: str):
    """Delete session when a recruiter cancels mid-flow."""
    _purge(session_id, reason="cancelled")


def sweep_expired_sessions():
    """
    Evict all sessions that have exceeded SESSION_TTL_SECONDS.
    Called periodically by the background sweeper in main.py.
    """
    now = time.monotonic()
    expired = [
        sid for sid, (_, created_at) in _sessions.items()
        if now - created_at > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _purge(sid, reason="ttl_sweep")
    if expired:
        logger.info(f"Session sweep evicted {len(expired)} expired session(s)")


def _purge(session_id: str, reason: str):
    session_entry = _sessions.pop(session_id, None)
    if session_entry:
        logger.info(f"Session purged session_id={session_id} reason={reason}")
