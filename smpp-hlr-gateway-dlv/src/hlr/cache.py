"""
Redis cache layer for HLR lookup results.
"""
import json
from typing import Optional, Dict, Any
import redis.asyncio as aioredis
from src.config import settings
from src.logging_config import get_logger
from src.metrics import hlr_cache_hits_total, hlr_cache_misses_total, redis_connection_pool_size

logger = get_logger(__name__)


class HLRCache:
    """Redis-based cache for HLR lookup results."""

    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self._pool: Optional[aioredis.ConnectionPool] = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        try:
            self._pool = aioredis.ConnectionPool.from_url(
                settings.redis_url,
                max_connections=settings.redis_max_connections,
                decode_responses=True
            )
            self.redis = aioredis.Redis(connection_pool=self._pool)

            # Test connection
            await self.redis.ping()

            redis_connection_pool_size.set(settings.redis_max_connections)
            logger.info("redis_connected", url=settings.redis_url)
        except Exception as e:
            logger.error("redis_connection_failed", error=str(e))
            raise

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
        if self._pool:
            await self._pool.disconnect()
        logger.info("redis_disconnected")

    def _make_key(self, msisdn: str) -> str:
        """Generate cache key for MSISDN."""
        return f"hlr:{msisdn}"

    async def get(self, msisdn: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached HLR result.

        Args:
            msisdn: Phone number to lookup

        Returns:
            Cached HLR result or None if not found
        """
        if not self.redis or settings.hlr_cache_ttl_seconds == 0:
            return None

        try:
            key = self._make_key(msisdn)
            data = await self.redis.get(key)

            if data:
                hlr_cache_hits_total.inc()
                result = json.loads(data) if isinstance(data, str) else data
                logger.debug("cache_hit", msisdn=msisdn)
                return result
            else:
                hlr_cache_misses_total.inc()
                logger.debug("cache_miss", msisdn=msisdn)
                return None
        except Exception as e:
            logger.warning("cache_get_error", msisdn=msisdn, error=str(e))
            return None

    async def set(self, msisdn: str, result: Dict[str, Any]) -> None:
        """
        Store HLR result in cache.

        Args:
            msisdn: Phone number
            result: HLR lookup result to cache
        """
        if not self.redis or settings.hlr_cache_ttl_seconds == 0:
            return

        try:
            key = self._make_key(msisdn)
            data = json.dumps(result)
            await self.redis.setex(
                key,
                settings.hlr_cache_ttl_seconds,
                data
            )
            logger.debug(
                "cache_set",
                msisdn=msisdn,
                ttl=settings.hlr_cache_ttl_seconds
            )
        except Exception as e:
            logger.warning("cache_set_error", msisdn=msisdn, error=str(e))

    async def delete(self, msisdn: str) -> None:
        """Delete cached HLR result."""
        if not self.redis:
            return

        try:
            key = self._make_key(msisdn)
            await self.redis.delete(key)
            logger.debug("cache_deleted", msisdn=msisdn)
        except Exception as e:
            logger.warning("cache_delete_error", msisdn=msisdn, error=str(e))


# Global cache instance
cache = HLRCache()