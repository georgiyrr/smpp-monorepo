"""
Integration tests with mocked HLR API.
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock
import httpx

from smpp_hlr_gateway.src.hlr.client import hlr_client
from smpp_hlr_gateway.src.hlr.cache import cache
from smpp_hlr_gateway.src.config import settings


@pytest.fixture(autouse=True)
async def setup_teardown():
    """Setup and teardown for integration tests."""
    # Setup
    await cache.connect()
    await hlr_client.connect()

    yield

    # Teardown
    await hlr_client.close()
    await cache.close()


@pytest.mark.asyncio
async def test_hlr_lookup_with_cache():
    """Test HLR lookup with Redis caching."""
    msisdn = "13476841841"

    mock_response = {
        msisdn: {
            "error": 0,
            "status": 0,
            "present": "yes",
            "type": "mobile",
            "classification": "valid"
        }
    }

    # First lookup - should call API
    with patch.object(hlr_client.client, 'get') as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )
        mock_get.return_value.raise_for_status = lambda: None

        result1 = await hlr_client.lookup(msisdn)
        assert result1['classification'] == 'valid'
        assert mock_get.call_count == 1

    # Second lookup - should use cache
    with patch.object(hlr_client.client, 'get') as mock_get:
        result2 = await hlr_client.lookup(msisdn)
        assert result2['classification'] == 'valid'
        assert mock_get.call_count == 0  # No API call

    # Verify results are the same
    assert result1 == result2


@pytest.mark.asyncio
async def test_cache_expiration():
    """Test that cache expires after TTL."""
    msisdn = "test_expiry"

    # Set short TTL for testing
    original_ttl = settings.hlr_cache_ttl_seconds
    settings.hlr_cache_ttl_seconds = 1

    try:
        test_data = {"test": "data", "classification": "valid"}

        # Store in cache
        await cache.set(msisdn, test_data)

        # Should exist immediately
        result = await cache.get(msisdn)
        assert result is not None

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Should be expired
        result = await cache.get(msisdn)
        assert result is None

    finally:
        settings.hlr_cache_ttl_seconds = original_ttl


@pytest.mark.asyncio
async def test_multiple_concurrent_hlr_requests():
    """Test handling of multiple concurrent HLR requests."""
    msisdns = [f"13476841{i:03d}" for i in range(10)]

    async def mock_lookup(msisdn):
        await asyncio.sleep(0.1)  # Simulate API delay
        return {
            "error": 0,
            "status": 0,
            "present": "yes",
            "classification": "valid",
            "number": msisdn
        }

    with patch('src.hlr.client.hlr_client.lookup', side_effect=mock_lookup):
        # Perform concurrent lookups
        tasks = [hlr_client.lookup(msisdn) for msisdn in msisdns]
        results = await asyncio.gather(*tasks)

        # Verify all completed successfully
        assert len(results) == 10
        for i, result in enumerate(results):
            assert result['classification'] == 'valid'


@pytest.mark.asyncio
async def test_hlr_retry_on_transient_error():
    """Test that transient errors are handled gracefully."""
    msisdn = "13476841841"

    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # First call fails
            raise httpx.HTTPError("Temporary error")
        else:
            # Second call succeeds
            response = AsyncMock()
            response.status_code = 200
            response.json = lambda: {
                msisdn: {
                    "error": 0,
                    "status": 0,
                    "present": "yes",
                    "classification": "valid"
                }
            }
            response.raise_for_status = lambda: None
            return response

    with patch.object(hlr_client.client, 'get', side_effect=mock_get):
        # First attempt should fail
        with pytest.raises(httpx.HTTPError):
            await hlr_client.lookup(msisdn)

        # Second attempt should succeed
        result = await hlr_client.lookup(msisdn)
        assert result['classification'] == 'valid'
        assert call_count == 2


@pytest.mark.asyncio
async def test_end_to_end_valid_number_flow():
    """Test complete flow for valid number (should be rejected)."""
    from smpp_hlr_gateway.src.smpp.handler import SubmitSMHandler, ESME_RINVDSTADR
    from unittest.mock import MagicMock

    msisdn = "13476841841"
    mock_response = {
        msisdn: {
            "error": 0,
            "status": 0,
            "present": "yes",
            "classification": "valid"
        }
    }

    with patch.object(hlr_client.client, 'get') as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )
        mock_get.return_value.raise_for_status = lambda: None

        handler = SubmitSMHandler(MagicMock())
        result = await handler.handle_submit_sm(
            pdu={},
            source_addr="1234",
            destination_addr=msisdn,
            short_message=b"Test"
        )

        assert result['command_status'] == ESME_RINVDSTADR
        assert result['message_id'] is None


@pytest.mark.asyncio
async def test_end_to_end_invalid_number_flow():
    """Test complete flow for invalid number (should be accepted + DELIVRD)."""
    from smpp_hlr_gateway.src.smpp.handler import SubmitSMHandler, ESME_ROK
    from unittest.mock import MagicMock

    msisdn = "40722570240999"
    mock_response = {
        msisdn: {
            "error": 1,
            "status": 1,
            "status_message": "Invalid Number",
            "classification": "invalid"
        }
    }

    with patch.object(hlr_client.client, 'get') as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )
        mock_get.return_value.raise_for_status = lambda: None

        with patch('asyncio.create_task') as mock_task:
            handler = SubmitSMHandler(MagicMock())
            result = await handler.handle_submit_sm(
                pdu={},
                source_addr="1234",
                destination_addr=msisdn,
                short_message=b"Test"
            )

            assert result['command_status'] == ESME_ROK
            assert result['message_id'] is not None

            # Verify DLR task was scheduled
            mock_task.assert_called_once()