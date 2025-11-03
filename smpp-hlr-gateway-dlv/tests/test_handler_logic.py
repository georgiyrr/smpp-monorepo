"""
Unit tests for SubmitSM handler logic.
"""
import pytest
from unittest.mock import MagicMock, patch
import httpx

from smpp_hlr_gateway.src.smpp.handler import SubmitSMHandler, ESME_ROK, ESME_RINVDSTADR, ESME_RSYSERR


@pytest.fixture
def mock_connection():
    """Create mock SMPP connection."""
    return MagicMock()


@pytest.fixture
def handler(mock_connection):
    """Create SubmitSM handler."""
    return SubmitSMHandler(mock_connection)


@pytest.mark.asyncio
async def test_submit_sm_valid_number_rejected(handler):
    """Test that valid number is rejected immediately."""
    pdu = {}
    source = "1234"
    destination = "13476841841"
    message = b"Test message"

    # Mock HLR response for valid number
    hlr_result = {
        "error": 0,
        "status": 0,
        "present": "yes",
        "classification": "valid"
    }

    with patch('src.smpp.handler.hlr_client.lookup', return_value=hlr_result):
        result = await handler.handle_submit_sm(pdu, source, destination, message)

        assert result['command_status'] == ESME_RINVDSTADR
        assert result['message_id'] is None


@pytest.mark.asyncio
async def test_submit_sm_invalid_number_accepted(handler):
    """Test that invalid number is accepted with DELIVRD scheduled."""
    pdu = {}
    source = "1234"
    destination = "40722570240999"
    message = b"Test message"

    # Mock HLR response for invalid number
    hlr_result = {
        "error": 1,
        "status": 1,
        "status_message": "Invalid Number",
        "classification": "invalid"
    }

    with patch('src.smpp.handler.hlr_client.lookup', return_value=hlr_result):
        with patch('asyncio.create_task') as mock_create_task:
            result = await handler.handle_submit_sm(pdu, source, destination, message)

            assert result['command_status'] == ESME_ROK
            assert result['message_id'] is not None
            assert len(result['message_id']) == 16

            # Verify DLR task was created
            mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_submit_sm_unsupported_network(handler):
    """Test handling of unsupported network (error 191)."""
    pdu = {}
    source = "1234"
    destination = "2347010000044"
    message = b"Test message"

    # Mock HLR response for unsupported network
    hlr_result = {
        "error": 191,
        "status": 0,
        "present": "na",
        "classification": "invalid"
    }

    with patch('src.smpp.handler.hlr_client.lookup', return_value=hlr_result):
        with patch('asyncio.create_task'):
            result = await handler.handle_submit_sm(pdu, source, destination, message)

            assert result['command_status'] == ESME_ROK
            assert result['message_id'] is not None


@pytest.mark.asyncio
async def test_submit_sm_landline(handler):
    """Test handling of landline number (error 193)."""
    pdu = {}
    source = "1234"
    destination = "33387840133"
    message = b"Test message"

    # Mock HLR response for landline
    hlr_result = {
        "error": 193,
        "status": 0,
        "type": "fixed",
        "classification": "invalid"
    }

    with patch('src.smpp.handler.hlr_client.lookup', return_value=hlr_result):
        with patch('asyncio.create_task'):
            result = await handler.handle_submit_sm(pdu, source, destination, message)

            assert result['command_status'] == ESME_ROK
            assert result['message_id'] is not None


@pytest.mark.asyncio
async def test_submit_sm_hlr_timeout(handler):
    """Test handling of HLR timeout with reject policy."""
    pdu = {}
    source = "1234"
    destination = "13476841841"
    message = b"Test message"

    with patch('src.smpp.handler.hlr_client.lookup', side_effect=httpx.TimeoutException("Timeout")):
        result = await handler.handle_submit_sm(pdu, source, destination, message)

        assert result['command_status'] == ESME_RSYSERR
        assert result['message_id'] is None


@pytest.mark.asyncio
async def test_submit_sm_hlr_error(handler):
    """Test handling of HLR error."""
    pdu = {}
    source = "1234"
    destination = "13476841841"
    message = b"Test message"

    with patch('src.smpp.handler.hlr_client.lookup', side_effect=Exception("Network error")):
        result = await handler.handle_submit_sm(pdu, source, destination, message)

        assert result['command_status'] == ESME_RSYSERR
        assert result['message_id'] is None


@pytest.mark.asyncio
async def test_DELIVRD_dlr_generation(handler):
    """Test DELIVRD DLR generation."""
    message_id = "ABC123DEF456"
    destination = "40722570240999"
    source = "1234"
    hlr_result = {
        "error": 1,
        "status": 1,
        "status_message": "Invalid Number"
    }

    with patch('src.smpp.handler.settings.dlr_delay_seconds', 0.01):
        with patch('src.smpp.handler.logger') as mock_logger:
            await handler._send_DELIVRD_dlr(message_id, destination, source, hlr_result)

            # Verify DLR was logged
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args
            assert call_args[0][0] == "dlr_DELIVRD_sent"
            assert call_args[1]['message_id'] == message_id