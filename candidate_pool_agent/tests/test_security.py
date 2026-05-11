import logging
import time
import pytest
from app.core.logging_config import PIIScrubFilter
from app.services import session_store as ss
from app.models.schemas import SessionState


# ─── PII scrub filter ─────────────────────────────────────────────────────────

def _scrub(text: str) -> str:
    """Helper: apply the filter to a plain string and return the result."""
    f = PIIScrubFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO,
        pathname="", lineno=0,
        msg=text, args=(), exc_info=None,
    )
    f.filter(record)
    return record.msg


def test_email_is_redacted():
    result = _scrub("Failed for alice@example.com on row 4")
    assert "alice@example.com" not in result
    assert "[email redacted]" in result


def test_multiple_emails_are_all_redacted():
    result = _scrub("alice@example.com and bob@corp.io both failed")
    assert "alice@example.com" not in result
    assert "bob@corp.io" not in result
    assert result.count("[email redacted]") == 2


def test_phone_is_redacted():
    result = _scrub("Candidate phone 555-867-5309 could not be parsed")
    assert "555-867-5309" not in result
    assert "[phone redacted]" in result


def test_non_pii_text_is_unchanged():
    result = _scrub("Session created session_id=abc123 reason=load_complete")
    assert result == "Session created session_id=abc123 reason=load_complete"


def test_row_number_is_preserved():
    result = _scrub("Validation error on row 7: missing first_name")
    assert "row 7" in result


def test_error_type_is_preserved():
    result = _scrub("Workday API error session_id=xyz error_type=HTTPStatusError")
    assert "HTTPStatusError" in result
    assert "session_id=xyz" in result


def test_dict_args_are_scrubbed():
    f = PIIScrubFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO,
        pathname="", lineno=0,
        msg="context: %s",
        args=({"email": "test@test.com", "count": "5"},),
        exc_info=None,
    )
    f.filter(record)
    args_str = str(record.args)
    assert "test@test.com" not in args_str


def test_filter_returns_true_always():
    """Filter must return True so the record is always emitted."""
    f = PIIScrubFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO,
        pathname="", lineno=0,
        msg="alice@example.com", args=(), exc_info=None,
    )
    assert f.filter(record) is True


# ─── Session store: purge after completion ────────────────────────────────────

def test_purge_after_completion_removes_session():
    session = ss.create_session("recruiter_1")
    sid = session.session_id
    assert ss.get_session(sid) is not None
    ss.purge_after_completion(sid)
    assert ss.get_session(sid) is None


def test_purge_on_cancel_removes_session():
    session = ss.create_session("recruiter_2")
    sid = session.session_id
    ss.purge_on_cancel(sid)
    assert ss.get_session(sid) is None


def test_double_purge_is_safe():
    session = ss.create_session("recruiter_3")
    sid = session.session_id
    ss.purge_after_completion(sid)
    ss.purge_after_completion(sid)  # should not raise
    assert ss.get_session(sid) is None


def test_save_and_get_session_works():
    session = ss.create_session("recruiter_4")
    session.state = SessionState.AWAITING_POOL_SELECTION
    ss.save_session(session)
    retrieved = ss.get_session(session.session_id)
    assert retrieved is not None
    assert retrieved.state == SessionState.AWAITING_POOL_SELECTION


# ─── Session store: TTL expiry ────────────────────────────────────────────────

def test_expired_session_returns_none(monkeypatch):
    """A session past its TTL should be evicted and return None."""
    session = ss.create_session("recruiter_5")
    sid = session.session_id

    # Wind the clock forward past the TTL
    original_ttl = ss.SESSION_TTL_SECONDS
    monkeypatch.setattr(ss, "SESSION_TTL_SECONDS", 0)

    # Force a tiny sleep so monotonic time advances
    time.sleep(0.01)
    result = ss.get_session(sid)

    monkeypatch.setattr(ss, "SESSION_TTL_SECONDS", original_ttl)
    assert result is None


def test_sweep_removes_expired_sessions(monkeypatch):
    session_a = ss.create_session("recruiter_6a")
    session_b = ss.create_session("recruiter_6b")

    monkeypatch.setattr(ss, "SESSION_TTL_SECONDS", 0)
    time.sleep(0.01)
    ss.sweep_expired_sessions()
    monkeypatch.setattr(ss, "SESSION_TTL_SECONDS", 3600)

    assert ss.get_session(session_a.session_id) is None
    assert ss.get_session(session_b.session_id) is None


def test_sweep_leaves_fresh_sessions_intact():
    session = ss.create_session("recruiter_7")
    ss.sweep_expired_sessions()  # TTL is 3600 — this session should survive
    assert ss.get_session(session.session_id) is not None
    ss.purge_after_completion(session.session_id)
