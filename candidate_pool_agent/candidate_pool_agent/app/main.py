from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.routes import router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.services.session_store import sweep_expired_sessions
import asyncio
import logging

# Configure logging first — before any module emits a log record.
# This ensures the PII scrub filter is in place from startup.
configure_logging()
logger = logging.getLogger(__name__)


async def _session_sweeper():
    """
    Background task that evicts abandoned sessions every 10 minutes.
    Prevents candidate data from accumulating in memory if a recruiter
    starts a flow and never completes or cancels it.
    """
    while True:
        await asyncio.sleep(600)
        sweep_expired_sessions()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Candidate Pool Agent starting")
    sweeper = asyncio.create_task(_session_sweeper())
    yield
    sweeper.cancel()
    try:
        await sweeper
    except asyncio.CancelledError:
        pass
    logger.info("Candidate Pool Agent stopped")


app = FastAPI(
    title="Candidate Pool Agent",
    description="AI agent service for automating Workday candidate pool management",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
