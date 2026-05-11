# Candidate Pool Agent - Core Service

AI agent service that automates loading LinkedIn Recruiter exports into Workday candidate pools.

## Project structure

```
candidate_pool_agent/
  app/
    api/routes.py              # FastAPI endpoints
    agent/
      file_parser.py           # xlsx validation, row-level error reporting
      conversation_manager.py  # state machine orchestrating the full flow
    workday/
      connector.py             # Workday API client, ISU + OAuth 2.0 auth adapter
    services/
      pool_cache.py            # Cached pool list from Workday
      session_store.py         # In-memory session store (swap for Redis at scale)
      audit_log.py             # SQLAlchemy audit log
    models/schemas.py          # Pydantic models
    core/config.py             # Settings loaded from .env
    main.py                    # FastAPI app entry point
  tests/
    test_file_parser.py        # Unit tests for validation logic
  requirements.txt
  .env.example
```

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your Workday tenant URL and credentials
```

## Run

```bash
uvicorn app.main:app --reload
```

API docs available at http://localhost:8000/docs

## Run tests

```bash
pytest tests/
```

## API flow

1. POST /api/v1/session/start?recruiter_id=<id>  → get session_id
2. POST /api/v1/upload                            → upload xlsx, get validation result
3. POST /api/v1/message                           → select pool by name
4. POST /api/v1/message                           → send "confirm" to execute
5. GET  /api/v1/audit                             → HR Tech reviews submission history

## Auth modes

Set WORKDAY_AUTH_MODE in .env:
- `basic`  - ISU username/password (legacy tenants)
- `oauth2` - Client credentials flow (modern tenants)

The connector handles both transparently. No changes needed to the rest of the service.

## Scaling notes

- Session store is in-memory by default. For multi-instance deployments, replace the dict in
  `app/services/session_store.py` with a Redis client behind the same get/save/delete interface.
- Audit log defaults to SQLite. Swap AUDIT_LOG_DB_URL for a Postgres connection string in production.
- Pool cache TTL is configurable via POOL_CACHE_TTL (default 300s).
