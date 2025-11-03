"""
Prometheus metrics definitions and HTTP server.
"""
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from src.config import settings
from src.logging_config import get_logger

logger = get_logger(__name__)

# Counters
submit_total = Counter(
    'submit_total',
    'Total number of SubmitSM requests',
    ['status']  # accepted, rejected
)

hlr_requests_total = Counter(
    'hlr_requests_total',
    'Total number of HLR API requests',
    ['result']  # valid, invalid, timeout, error
)

hlr_cache_hits_total = Counter(
    'hlr_cache_hits_total',
    'Total number of HLR cache hits'
)

hlr_cache_misses_total = Counter(
    'hlr_cache_misses_total',
    'Total number of HLR cache misses'
)

delivrd_total = Counter(
    'delivrd_total',
    'Total number of DELIVRD messages sent',
    ['reason']  # invalid_number, timeout, hlr_error
)

# Histograms
hlr_latency_seconds = Histogram(
    'hlr_latency_seconds',
    'HLR API response time in seconds',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

submit_processing_seconds = Histogram(
    'submit_processing_seconds',
    'SubmitSM processing time in seconds',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)

# Gauges
active_smpp_connections = Gauge(
    'active_smpp_connections',
    'Current number of active SMPP connections'
)

active_tasks = Gauge(
    'active_tasks',
    'Current number of active asyncio tasks'
)

redis_connection_pool_size = Gauge(
    'redis_connection_pool_size',
    'Current Redis connection pool size'
)


def start_metrics_server() -> None:
    """Start Prometheus metrics HTTP server."""
    if settings.metrics_enabled:
        try:
            start_http_server(settings.metrics_port)
            logger.info(
                "metrics_server_started",
                port=settings.metrics_port,
                path=settings.metrics_path
            )
        except Exception as e:
            logger.error("failed_to_start_metrics_server", error=str(e))
            raise