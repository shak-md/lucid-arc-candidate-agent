# Maps Teams conversation_id -> agent session_id
# Swap for Redis when scaling to multiple bot instances.
_sessions: dict[str, str] = {}


def get_session_id(conversation_id: str) -> str | None:
    return _sessions.get(conversation_id)


def set_session_id(conversation_id: str, session_id: str):
    _sessions[conversation_id] = session_id


def clear_session(conversation_id: str):
    _sessions.pop(conversation_id, None)
