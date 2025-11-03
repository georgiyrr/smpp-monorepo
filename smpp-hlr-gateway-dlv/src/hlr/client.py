"""
Async HTTP client for TMT Velocity HLR API with database storage.
Uses thread pool to prevent blocking event loop.
"""
import time
import asyncio
from typing import Dict, Any, Optional
from functools import partial
import concurrent.futures
import httpx

from src.config import settings
from src.logging_config import get_logger
from src.metrics import hlr_requests_total, hlr_latency_seconds
from src.hlr.cache import cache

logger = get_logger(__name__)


class HLRClient:
    """Async client for TMT Velocity HLR lookups with thread pool."""

    def __init__(self):
        self.sync_client: Optional[httpx.Client] = None  # Синхронний клієнт
        self.db_client = None  # Will be set in connect()
        # Thread pool для HLR запитів (не блокує event loop!)
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=100,
            thread_name_prefix="hlr_worker"
        )
        # Semaphore для обмеження одночасних запитів
        self.semaphore = asyncio.Semaphore(100)

    async def connect(self) -> None:
        """Initialize HTTP client."""
        # Використовуємо синхронний httpx.Client для thread pool
        self.sync_client = httpx.Client(
            timeout=httpx.Timeout(settings.hlr_timeout_seconds),
            limits=httpx.Limits(
                max_keepalive_connections=200,
                max_connections=500
            )
        )

        # Import here to avoid circular dependency
        from src.database.client import db_client
        self.db_client = db_client

        loop = asyncio.get_event_loop()
        warmup_tasks = []
        for i in range(20):  # Створити 10 threads завчасно
            task = loop.run_in_executor(
                self.executor,
                lambda: time.sleep(0.001)  # Dummy task
            )
            warmup_tasks.append(task)

        await asyncio.gather(*warmup_tasks)

        logger.info("hlr_client_initialized", executor_workers=100, threads_warmed=20)

    async def close(self) -> None:
        """Close HTTP client and thread pool."""
        if self.sync_client:
            self.sync_client.close()

        # Shutdown thread pool gracefully
        self.executor.shutdown(wait=True, cancel_futures=False)

        logger.info("hlr_client_closed")

    def _build_url(self, msisdn: str) -> str:
        """Build TMT Velocity API URL."""
        return f"{settings.hlr_base_url}/{settings.hlr_api_key}/{settings.hlr_api_secret}/{msisdn}"

    def _classify_result(self, result: Dict[str, Any]) -> str:
        """
        Classify HLR result.

        Returns:
            'valid' - number is valid (error=0, status=0)
            'invalid' - number is invalid or unsupported
        """
        error = result.get("error", 0)
        status = result.get("status", 1)

        # Valid number: error=0, status=0
        if error == 0 and status == 0:
            return "valid"
        else:
            return "invalid"

    def _sync_hlr_request(self, msisdn: str) -> Dict[str, Any]:
        """
        Синхронний HLR запит (виконується в окремому thread).

        Це НЕ блокує event loop!
        """
        url = self._build_url(msisdn)
        start_time = time.time()

        try:
            if not self.sync_client:
                raise RuntimeError("HLR client not initialized")

            # Синхронний HTTP запит (виконується в thread pool)
            response = self.sync_client.get(url)
            response.raise_for_status()

            latency = time.time() - start_time

            data = response.json()

            # Extract result for the specific number
            result = data.get(msisdn, {})

            if not result:
                result = {
                    "number": msisdn,
                    "error": 1,
                    "status": 1,
                    "status_message": "Empty response from HLR"
                }

            # Add classification
            classification = self._classify_result(result)
            result["classification"] = classification

            # Update metrics
            hlr_latency_seconds.observe(latency)
            hlr_requests_total.labels(result=classification).inc()

            return result

        except httpx.TimeoutException as e:
            latency = time.time() - start_time
            hlr_latency_seconds.observe(latency)
            hlr_requests_total.labels(result="timeout").inc()
            raise

        except httpx.HTTPError as e:
            latency = time.time() - start_time
            hlr_latency_seconds.observe(latency)
            hlr_requests_total.labels(result="error").inc()
            raise

        except Exception as e:
            latency = time.time() - start_time
            hlr_requests_total.labels(result="error").inc()
            raise

    async def lookup(self, msisdn: str, source_ip: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform HLR lookup with caching and database storage.

        HLR запит виконується в thread pool, тому НЕ блокує event loop!

        Args:
            msisdn: Phone number to lookup
            source_ip: Source IP address (optional)

        Returns:
            Dict containing HLR result with additional 'classification' field

        Raises:
            httpx.TimeoutException: If request times out
            httpx.HTTPError: For other HTTP errors
        """
        # Check cache first (швидко, в event loop)
        cached = await cache.get(msisdn)
        if cached:
            logger.debug("hlr_cache_hit", msisdn=msisdn)
            return cached

        # Semaphore для обмеження одночасних запитів
        async with self.semaphore:
            # Double-check cache
            cached = await cache.get(msisdn)
            if cached:
                logger.debug("hlr_cache_hit_after_wait", msisdn=msisdn)
                return cached

            logger.debug("hlr_request_start", msisdn=msisdn)

            try:
                # ✅ Виконати HLR запит в окремому thread (НЕ блокує event loop!)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self.executor,
                    self._sync_hlr_request,
                    msisdn
                )

                # Cache result (async, швидко)
                await cache.set(msisdn, result)

                # Save to database (async, non-blocking)
                if self.db_client:
                    asyncio.create_task(
                        self.db_client.save_hlr_lookup(
                            msisdn=msisdn,
                            classification=result["classification"],
                            hlr_response=result,
                            latency_ms=result.get("latency_ms", 0),
                            cached=False,
                            source_ip=source_ip
                        )
                    )

                logger.info(
                    "hlr_lookup_success",
                    msisdn=msisdn,
                    classification=result["classification"],
                    error=result.get("error"),
                    status=result.get("status"),
                    present=result.get("present")
                )

                return result

            except Exception as e:
                logger.error(
                    "hlr_lookup_error",
                    msisdn=msisdn,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise


# Global HLR client instance
hlr_client = HLRClient()