import time
import logging
from app.models.schemas import CandidatePool
from app.workday.connector import workday_connector
from app.core.config import settings

logger = logging.getLogger(__name__)


class PoolCache:
    def __init__(self, ttl: int = settings.POOL_CACHE_TTL):
        self._ttl = ttl
        self._cache: list[CandidatePool] = []
        self._last_fetched: float = 0

    async def get_pools(self, force_refresh: bool = False) -> list[CandidatePool]:
        if force_refresh or not self._cache or time.time() - self._last_fetched > self._ttl:
            logger.info("Fetching candidate pools from Workday")
            self._cache = await workday_connector.get_candidate_pools()
            self._last_fetched = time.time()
        return self._cache

    def find_pool(self, name_or_id: str) -> CandidatePool | None:
        name_lower = name_or_id.strip().lower()
        for pool in self._cache:
            if pool.pool_id == name_or_id or pool.pool_name.lower() == name_lower:
                return pool
        return None


pool_cache = PoolCache()
