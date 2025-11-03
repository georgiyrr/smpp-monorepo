"""
PostgreSQL database client for HLR lookups storage.
"""
import asyncio
from typing import Dict, Any, Optional, List
import asyncpg
import json
from datetime import datetime

from src.config import settings
from src.logging_config import get_logger

logger = get_logger(__name__)


class DatabaseClient:
    """Async PostgreSQL client for HLR data."""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Establish database connection pool."""
        if not settings.db_enabled:
            logger.info("database_disabled")
            return

        try:
            self.pool = await asyncpg.create_pool(
                host=settings.db_host,
                port=settings.db_port,
                database=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
                min_size=settings.db_pool_min,
                max_size=settings.db_pool_max,
                command_timeout=10
            )

            # Test connection
            async with self.pool.acquire() as conn:
                version = await conn.fetchval('SELECT version()')
                logger.info("database_connected", version=version[:50])

        except Exception as e:
            logger.error("database_connection_failed", error=str(e), error_type=type(e).__name__)
            raise

    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("database_disconnected")

    async def save_hlr_lookup(
            self,
            msisdn: str,
            classification: str,
            hlr_response: Dict[str, Any],
            latency_ms: float,
            cached: bool = False,
            source_ip: Optional[str] = None
    ) -> None:
        """
        Save HLR lookup result to database (async, non-blocking).

        Args:
            msisdn: Phone number
            classification: 'valid' or 'invalid'
            hlr_response: Full HLR API response
            latency_ms: HLR request latency
            cached: Whether result was from cache
            source_ip: Source IP address (optional)
        """
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO hlr_lookups (
                        msisdn,
                        classification,
                        error_code,
                        status_code,
                        present,
                        mcc,
                        mnc,
                        operator,
                        network_type,
                        country,
                        ported,
                        hlr_response,
                        latency_ms,
                        cached,
                        source_ip
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    """,
                    msisdn,
                    classification,
                    hlr_response.get('error'),
                    hlr_response.get('status'),
                    hlr_response.get('present'),
                    hlr_response.get('mcc'),
                    hlr_response.get('mnc'),
                    hlr_response.get('network'),
                    hlr_response.get('type'),
                    self._extract_country(hlr_response.get('mcc')),
                    hlr_response.get('ported'),
                    json.dumps(hlr_response),  # JSONB as JSON string
                    latency_ms,
                    cached,
                    source_ip
                )

                logger.debug(
                    "hlr_lookup_saved",
                    msisdn=msisdn,
                    classification=classification
                )

        except Exception as e:
            logger.error(
                "hlr_lookup_save_error",
                msisdn=msisdn,
                error=str(e),
                error_type=type(e).__name__
            )

    async def get_recent_lookups(
            self,
            days: int = 7,
            limit: int = 100000
    ) -> List[Dict[str, Any]]:
        """
        Get recent unique HLR lookups for cache warmup.

        Args:
            days: Number of days to look back
            limit: Maximum number of records

        Returns:
            List of HLR lookup records
        """
        if not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                query = f"""
                    SELECT DISTINCT ON (msisdn)
                        msisdn,
                        classification,
                        hlr_response
                    FROM hlr_lookups
                    WHERE created_at >= NOW() - INTERVAL '{days} days'
                    ORDER BY msisdn, created_at DESC
                    LIMIT {limit}
                """

                rows = await conn.fetch(query)

                results = []
                for row in rows:
                    hlr_resp = row['hlr_response']
                    # Parse JSON if it's a string
                    if isinstance(hlr_resp, str):
                        import json
                        hlr_resp = json.loads(hlr_resp)

                    results.append({
                        'msisdn': row['msisdn'],
                        'classification': row['classification'],
                        'hlr_response': hlr_resp
                    })

                logger.info(
                    "recent_lookups_loaded",
                    count=len(results),
                    days=days
                )

                return results

        except Exception as e:
            logger.error(
                "recent_lookups_error",
                error=str(e),
                error_type=type(e).__name__
            )
            return []

    async def get_lookup_stats(self, days: int = 1) -> Dict[str, Any]:
        """
        Get HLR lookup statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Statistics dictionary
        """
        if not self.pool:
            return {}

        try:
            async with self.pool.acquire() as conn:
                stats = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as total_lookups,
                        COUNT(DISTINCT msisdn) as unique_msisdns,
                        SUM(CASE WHEN classification = 'valid' THEN 1 ELSE 0 END) as valid_count,
                        SUM(CASE WHEN classification = 'invalid' THEN 1 ELSE 0 END) as invalid_count,
                        SUM(CASE WHEN cached = true THEN 1 ELSE 0 END) as cache_hits,
                        AVG(latency_ms) as avg_latency_ms,
                        MAX(latency_ms) as max_latency_ms,
                        MIN(latency_ms) as min_latency_ms
                    FROM hlr_lookups
                    WHERE created_at >= NOW() - INTERVAL '$1 days'
                    """,
                    days
                )

                return dict(stats) if stats else {}

        except Exception as e:
            logger.error("get_stats_error", error=str(e))
            return {}

    def _extract_country(self, mcc: Optional[str]) -> Optional[str]:
        """
        Extract country code from MCC.

        Simple mapping for common countries.
        """
        if not mcc:
            return None

        mcc_country_map = {
            '255': 'UA',  # Ukraine
            '310': 'US',  # USA
            '311': 'US',
            '250': 'RU',  # Russia
            '234': 'GB',  # UK
            '262': 'DE',  # Germany
            '208': 'FR',  # France
        }

        return mcc_country_map.get(mcc[:3])

    async def healthcheck(self) -> bool:
        """Check database connection health."""
        if not self.pool:
            return False

        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
            return True
        except Exception:
            return False


# Global database client instance
db_client = DatabaseClient()