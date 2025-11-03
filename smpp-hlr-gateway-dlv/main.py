"""
SMPP HLR Gateway main entry point.
"""
import asyncio
import signal
import sys
from typing import Optional

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from src.config import settings
from src.logging_config import setup_logging, get_logger
from src.metrics import start_metrics_server
from src.hlr.client import hlr_client
from src.hlr.cache import cache
from src.database.client import db_client
from src.smpp.server import SMPPServer

# Setup logging first
setup_logging()
logger = get_logger(__name__)


class Application:
    """Main application coordinator."""

    def __init__(self):
        self.smpp_server: Optional[SMPPServer] = None
        self.shutdown_event = asyncio.Event()

    async def startup(self) -> None:
        """Initialize all components."""
        logger.info(
            "application_starting",
            smpp_port=settings.smpp_port,
            hlr_url=settings.hlr_base_url,
            redis_url=settings.redis_url,
            db_enabled=settings.db_enabled
        )

        # Start metrics server
        if settings.metrics_enabled:
            start_metrics_server()

        # Connect to Redis
        await cache.connect()

        # Connect to PostgreSQL
        if settings.db_enabled:
            await db_client.connect()

        # Cache warmup from database
        if settings.db_enabled and settings.cache_warmup_enabled:
            await self._warmup_cache()

        # Initialize HLR client
        await hlr_client.connect()

        logger.info("application_started")

    async def _warmup_cache(self) -> None:
        """Load recent HLR lookups from database into Redis cache."""
        try:
            logger.info(
                "cache_warmup_started",
                days=settings.cache_warmup_days,
                limit=settings.cache_warmup_limit
            )

            # Load recent lookups from database
            lookups = await db_client.get_recent_lookups(
                days=settings.cache_warmup_days,
                limit=settings.cache_warmup_limit
            )

            # Load into Redis cache
            loaded_count = 0
            for lookup in lookups:
                msisdn = lookup['msisdn']
                hlr_response = lookup['hlr_response']

                # Ensure hlr_response is a dict (asyncpg should return dict for jsonb)
                if not isinstance(hlr_response, dict):
                    logger.warning("hlr_response_not_dict", msisdn=msisdn, type=type(hlr_response).__name__)
                    continue

                await cache.set(msisdn, hlr_response)
                loaded_count += 1

            logger.info(
                "cache_warmup_complete",
                records_loaded=loaded_count,
                total_available=len(lookups)
            )

        except Exception as e:
            logger.error(
                "cache_warmup_error",
                error=str(e),
                error_type=type(e).__name__
            )
            # Don't fail startup if warmup fails

    async def shutdown(self) -> None:
        """Cleanup all components."""
        logger.info("application_shutting_down")

        # Stop SMPP server
        if self.smpp_server:
            await self.smpp_server.stop()

        # Close HLR client
        await hlr_client.close()

        # Close database connection
        if settings.db_enabled:
            await db_client.close()

        # Close Redis connection
        await cache.close()

        logger.info("application_shutdown_complete")

    async def run(self) -> None:
        """Run the application."""
        # Setup signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self._handle_shutdown())
            )

        try:
            # Startup
            await self.startup()

            # Start SMPP server
            self.smpp_server = SMPPServer()
            server_task = asyncio.create_task(self.smpp_server.start())

            # Wait for shutdown signal
            await self.shutdown_event.wait()

            # Cancel server task
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

        except Exception as e:
            logger.error(
                "application_error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

        finally:
            await self.shutdown()

    async def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        logger.info("shutdown_signal_received")
        self.shutdown_event.set()


async def healthcheck() -> int:
    """
    Perform health check for container.

    Returns:
        0 if healthy, 1 if unhealthy
    """
    try:
        # Check Redis connection
        await cache.connect()
        await cache.redis.ping()
        await cache.close()

        # Check database connection
        if settings.db_enabled:
            await db_client.connect()
            db_healthy = await db_client.healthcheck()
            await db_client.close()

            if not db_healthy:
                logger.error("healthcheck_failed", reason="database_unhealthy")
                return 1

        logger.info("healthcheck_passed")
        return 0

    except Exception as e:
        logger.error("healthcheck_failed", error=str(e))
        return 1


def main() -> None:
    """Main entry point."""
    # Check if running healthcheck
    if len(sys.argv) > 1 and sys.argv[1] == "healthcheck":
        exit_code = asyncio.run(healthcheck())
        sys.exit(exit_code)

    # Run application
    app = Application()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("application_interrupted")
    except Exception as e:
        logger.error(
            "application_fatal_error",
            error=str(e),
            error_type=type(e).__name__
        )
        sys.exit(1)


if __name__ == "__main__":
    main()