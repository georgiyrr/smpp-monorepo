"""
Pytest configuration and shared fixtures.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.ping.return_value = True
    redis.get.return_value = None
    redis.setex.return_value = True
    redis.delete.return_value = 1
    return redis


@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient."""
    client = AsyncMock()
    return client