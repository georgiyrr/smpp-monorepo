"""
Unit tests for HLR client.
"""
import pytest
from unittest.mock import AsyncMock, patch
import httpx

from smpp_hlr_gateway.src.hlr.client import HLRClient


@pytest.fixture
async def hlr_client():
    """Create HLR client fixture."""
    client = HLRClient()
    await client.connect()
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_hlr_lookup_valid_number(hlr_client):
    """Test HLR lookup for valid number."""
    msisdn = "13476841841"

    mock_response = {
        msisdn: {
            "cic": "151971",
            "error": 0,
            "imsi": "310004XXXXXXXXX",
            "mcc": "310",
            "mnc": "004",
            "network": "Verizon Wireless:6006 - SVR/2",
            "number": 13476841841,
            "ported": False,
            "present": "yes",
            "status": 0,
            "status_message": "Success",
            "type": "mobile",
            "trxid": "Fx0ke_S"
        }
    }

    with patch.object(hlr_client.client, 'get') as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )
        mock_get.return_value.raise_for_status = lambda: None

        result = await hlr_client.lookup(msisdn)

        assert result['classification'] == 'valid'
        assert result['error'] == 0
        assert result['status'] == 0
        assert result['present'] == 'yes'


@pytest.mark.asyncio
async def test_hlr_lookup_invalid_number(hlr_client):
    """Test HLR lookup for invalid number."""
    msisdn = "40722570240999"

    mock_response = {
        msisdn: {
            "number": 40722570240999,
            "status": 1,
            "status_message": "Invalid Number",
            "error": 0
        }
    }

    with patch.object(hlr_client.client, 'get') as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )
        mock_get.return_value.raise_for_status = lambda: None

        result = await hlr_client.lookup(msisdn)

        assert result['classification'] == 'invalid'
        assert result['status'] == 1


@pytest.mark.asyncio
async def test_hlr_lookup_unsupported_network(hlr_client):
    """Test HLR lookup for unsupported network (error 191)."""
    msisdn = "2347010000044"

    mock_response = {
        msisdn: {
            "cic": "234503",
            "error": 191,
            "imsi": "62160XXXXXXXXXX",
            "mcc": "621",
            "mnc": "60",
            "network": "9Mobile(ETISALAT)",
            "number": 2347010000044,
            "ported": True,
            "present": "na",
            "status": 0,
            "status_message": "Success",
            "type": "mobile",
            "trxid": "viMn_p9"
        }
    }

    with patch.object(hlr_client.client, 'get') as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )
        mock_get.return_value.raise_for_status = lambda: None

        result = await hlr_client.lookup(msisdn)

        assert result['classification'] == 'invalid'
        assert result['error'] == 191


@pytest.mark.asyncio
async def test_hlr_lookup_landline(hlr_client):
    """Test HLR lookup for landline (error 193)."""
    msisdn = "33387840133"

    mock_response = {
        msisdn: {
            "cic": "33511",
            "error": 193,
            "imsi": "",
            "mcc": None,
            "mnc": None,
            "network": "Orange",
            "number": 33387840133,
            "ported": False,
            "present": "na",
            "status": 0,
            "status_message": "Success",
            "type": "fixed",
            "trxid": "AD0uuKo"
        }
    }

    with patch.object(hlr_client.client, 'get') as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )
        mock_get.return_value.raise_for_status = lambda: None

        result = await hlr_client.lookup(msisdn)

        assert result['classification'] == 'invalid'
        assert result['error'] == 193
        assert result['type'] == 'fixed'


@pytest.mark.asyncio
async def test_hlr_lookup_timeout(hlr_client):
    """Test HLR lookup timeout."""
    msisdn = "13476841841"

    with patch.object(hlr_client.client, 'get') as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Request timed out")

        with pytest.raises(httpx.TimeoutException):
            await hlr_client.lookup(msisdn)


@pytest.mark.asyncio
async def test_hlr_lookup_http_error(hlr_client):
    """Test HLR lookup HTTP error."""
    msisdn = "13476841841"

    with patch.object(hlr_client.client, 'get') as mock_get:
        mock_get.side_effect = httpx.HTTPError("Connection error")

        with pytest.raises(httpx.HTTPError):
            await hlr_client.lookup(msisdn)


def test_classify_result_valid():
    """Test classification of valid number."""
    client = HLRClient()

    result = {
        "error": 0,
        "status": 0,
        "present": "yes"
    }

    assert client._classify_result(result) == "valid"


def test_classify_result_invalid():
    """Test classification of invalid number."""
    client = HLRClient()

    # Invalid status
    result1 = {"error": 0, "status": 1, "present": "yes"}
    assert client._classify_result(result1) == "invalid"

    # Error present
    result2 = {"error": 191, "status": 0, "present": "na"}
    assert client._classify_result(result2) == "invalid"

    # Not present
    result3 = {"error": 0, "status": 0, "present": "no"}
    assert client._classify_result(result3) == "invalid"