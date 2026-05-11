import httpx
import logging
from bot.config import settings

logger = logging.getLogger(__name__)

BASE_URL = settings.AGENT_SERVICE_URL.rstrip("/")


class AgentServiceClient:
    """HTTP client for the candidate pool agent core service."""

    async def start_session(self, recruiter_id: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{BASE_URL}/session/start",
                params={"recruiter_id": recruiter_id},
            )
            response.raise_for_status()
            return response.json()

    async def upload_file(
        self,
        session_id: str,
        recruiter_id: str,
        file_content_base64: str,
        filename: str,
    ) -> dict:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{BASE_URL}/upload",
                json={
                    "session_id": session_id,
                    "recruiter_id": recruiter_id,
                    "file_content_base64": file_content_base64,
                    "filename": filename,
                },
            )
            response.raise_for_status()
            return response.json()

    async def send_message(
        self,
        session_id: str,
        recruiter_id: str,
        message: str,
    ) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{BASE_URL}/message",
                json={
                    "session_id": session_id,
                    "recruiter_id": recruiter_id,
                    "message": message,
                },
            )
            response.raise_for_status()
            return response.json()


agent_client = AgentServiceClient()
