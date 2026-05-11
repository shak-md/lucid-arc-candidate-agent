import httpx
import base64
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional
from app.models.schemas import CandidatePool, CandidateRecord
from app.core.config import settings

logger = logging.getLogger(__name__)


class WorkdayAuthAdapter(ABC):
    @abstractmethod
    async def get_auth_headers(self) -> dict:
        pass


class ISUBasicAuthAdapter(WorkdayAuthAdapter):
    def __init__(self, username: str, password: str):
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._headers = {"Authorization": f"Basic {credentials}"}

    async def get_auth_headers(self) -> dict:
        return self._headers


class OAuth2Adapter(WorkdayAuthAdapter):
    def __init__(self, client_id: str, client_secret: str, token_url: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._token: Optional[str] = None
        self._token_expiry: float = 0

    async def get_auth_headers(self) -> dict:
        if not self._token or time.time() >= self._token_expiry:
            await self._refresh_token()
        return {"Authorization": f"Bearer {self._token}"}

    async def _refresh_token(self):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()
            self._token = data["access_token"]
            self._token_expiry = time.time() + data.get("expires_in", 3600) - 60


def build_auth_adapter() -> WorkdayAuthAdapter:
    if settings.WORKDAY_AUTH_MODE == "oauth2":
        return OAuth2Adapter(
            client_id=settings.WORKDAY_CLIENT_ID,
            client_secret=settings.WORKDAY_CLIENT_SECRET,
            token_url=settings.WORKDAY_TOKEN_URL,
        )
    return ISUBasicAuthAdapter(
        username=settings.WORKDAY_ISU_USERNAME,
        password=settings.WORKDAY_ISU_PASSWORD,
    )


class WorkdayConnector:
    def __init__(self, auth_adapter: WorkdayAuthAdapter):
        self._auth = auth_adapter
        self._base_url = settings.WORKDAY_TENANT_URL.rstrip("/")

    async def get_candidate_pools(self) -> list[CandidatePool]:
        """Fetch all available candidate pools from Workday."""
        headers = await self._auth.get_auth_headers()
        headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self._base_url}/recruiting/v2/candidatePools",
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        pools = []
        for item in data.get("data", []):
            pools.append(CandidatePool(
                pool_id=item["id"],
                pool_name=item.get("descriptor", item["id"]),
            ))
        return pools

    async def add_candidates_to_pool(
        self,
        pool_id: str,
        candidates: list[CandidateRecord],
    ) -> tuple[list[str], list[dict]]:
        """
        Add candidates to a Workday candidate pool.
        Returns (succeeded_emails, failed_records).
        Failed records contain email and reason.
        """
        headers = await self._auth.get_auth_headers()
        headers["Content-Type"] = "application/json"

        succeeded = []
        failed = []

        async with httpx.AsyncClient(timeout=30) as client:
            for candidate in candidates:
                payload = {
                    "candidatePool": {"id": pool_id},
                    "candidate": {
                        "email": candidate.email,
                        "firstName": candidate.first_name,
                        "lastName": candidate.last_name,
                        **({"phone": candidate.phone} if candidate.phone else {}),
                    },
                }
                try:
                    response = await client.post(
                        f"{self._base_url}/recruiting/v2/candidatePoolMembers",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    succeeded.append(candidate.email)
                except httpx.HTTPStatusError as e:
                    reason = self._extract_error_reason(e.response)
                    failed.append({
                        "email": candidate.email,
                        "row_number": candidate.row_number,
                        "reason": reason,
                    })
                    logger.warning(f"Failed to add candidate {candidate.email}: {reason}")
                except Exception as e:
                    failed.append({
                        "email": candidate.email,
                        "row_number": candidate.row_number,
                        "reason": str(e),
                    })

        return succeeded, failed

    def _extract_error_reason(self, response: httpx.Response) -> str:
        try:
            data = response.json()
            errors = data.get("errors", [])
            if errors:
                return errors[0].get("error", response.text)
        except Exception:
            pass
        return f"HTTP {response.status_code}: {response.text[:200]}"


_auth_adapter = build_auth_adapter()
workday_connector = WorkdayConnector(_auth_adapter)
