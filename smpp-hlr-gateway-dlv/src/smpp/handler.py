"""
Core SubmitSM handling logic with HLR lookup.
"""
import time
import asyncio
from typing import Dict, Any
import httpx

from src.config import settings
from src.logging_config import get_logger
from src.metrics import (
    submit_total, submit_processing_seconds,
    delivrd_total, active_tasks
)
from src.hlr.client import hlr_client
from src.smpp.pdu_builder import (
    generate_message_id, build_dlr_text,
    get_error_code_from_hlr, get_reason
)

logger = get_logger(__name__)


# SMPP Command Status codes
ESME_ROK = 0x00000000
ESME_RINVDSTADR = 0x0000000B  # Invalid destination address
ESME_RSYSERR = 0x00000008     # System error


class SubmitSMHandler:
    """Handles SubmitSM PDU processing with HLR lookup."""
    
    def __init__(self, client_connection):
        """
        Initialize handler.
        
        Args:
            client_connection: SMPP client connection object
        """
        self.connection = client_connection
    
    async def handle_submit_sm(
        self,
        pdu: Dict[str, Any],
        source_addr: str,
        destination_addr: str,
        short_message: bytes
    ) -> Dict[str, Any]:
        """
        Process SubmitSM with HLR lookup.
        
        Logic:
        1. Perform async HLR lookup
        2. If valid (error=0, status=0, present=yes) → return error immediately
        3. If invalid → return OK, schedule DELIVRD DLR
        
        Args:
            pdu: Parsed SubmitSM PDU
            source_addr: Source address
            destination_addr: Destination MSISDN
            short_message: Message content
            
        Returns:
            Dict with 'command_status' and optional 'message_id'
        """
        start_time = time.time()
        message_id = generate_message_id()
        
        logger.info(
            "submit_sm_received",
            message_id=message_id,
            source=source_addr,
            destination=destination_addr,
            message_length=len(short_message)
        )
        
        try:
            # Perform HLR lookup
            hlr_result = await hlr_client.lookup(destination_addr)
            classification = hlr_result.get("classification", "invalid")
            
            if classification == "valid":
                # Valid number → REJECT immediately
                submit_total.labels(status="rejected").inc()
                
                logger.info(
                    "submit_sm_rejected_valid_number",
                    message_id=message_id,
                    destination=destination_addr,
                    hlr_error=hlr_result.get("error"),
                    hlr_status=hlr_result.get("status")
                )
                
                processing_time = time.time() - start_time
                submit_processing_seconds.observe(processing_time)
                
                return {
                    "command_status": ESME_RINVDSTADR,
                    "message_id": None
                }
            
            else:
                # Invalid number → ACCEPT + schedule DELIVRD
                submit_total.labels(status="accepted").inc()
                
                logger.info(
                    "submit_sm_accepted_invalid_number",
                    message_id=message_id,
                    destination=destination_addr,
                    hlr_error=hlr_result.get("error"),
                    hlr_status=hlr_result.get("status")
                )
                
                # Schedule DLR delivery (non-blocking)
                asyncio.create_task(
                    self._send_DELIVRD_dlr(
                        message_id=message_id,
                        destination_addr=destination_addr,
                        source_addr=source_addr,
                        hlr_result=hlr_result
                    )
                )
                
                processing_time = time.time() - start_time
                submit_processing_seconds.observe(processing_time)
                
                return {
                    "command_status": ESME_ROK,
                    "message_id": message_id
                }
        
        except httpx.TimeoutException:
            # HLR timeout → apply policy
            if settings.hlr_timeout_policy == "reject":
                submit_total.labels(status="rejected").inc()
                
                logger.warning(
                    "submit_sm_rejected_hlr_timeout",
                    message_id=message_id,
                    destination=destination_addr
                )
                
                processing_time = time.time() - start_time
                submit_processing_seconds.observe(processing_time)
                
                return {
                    "command_status": ESME_RSYSERR,
                    "message_id": None
                }
        
        except Exception as e:
            # Unexpected error → reject
            submit_total.labels(status="rejected").inc()
            
            logger.error(
                "submit_sm_error",
                message_id=message_id,
                destination=destination_addr,
                error=str(e),
                error_type=type(e).__name__
            )
            
            processing_time = time.time() - start_time
            submit_processing_seconds.observe(processing_time)
            
            return {
                "command_status": ESME_RSYSERR,
                "message_id": None
            }

    async def _send_DELIVRD_dlr(
            self,
            message_id: str,
            destination_addr: str,
            source_addr: str,
            hlr_result: Dict[str, Any]
    ) -> None:
        """Send DELIVRD DLR after delay."""
        active_tasks.inc()

        try:
            # Wait before sending DLR
            await asyncio.sleep(settings.dlr_delay_seconds)

            # Build DLR text
            error_code = get_error_code_from_hlr(hlr_result)
            dlr_text = build_dlr_text(
                message_id=message_id,
                stat="DELIVRD",
                err=error_code
            )

            # Update metrics
            reason = get_reason(hlr_result)
            delivrd_total.labels(reason=reason).inc()

            # ✅ Send DeliverSM PDU to client
            await self.connection.send_deliver_sm(
                source_addr=destination_addr,  # DLR from original destination
                destination_addr=source_addr,  # To original sender
                short_message=dlr_text.encode('ascii')
            )

            logger.info(
                "dlr_DELIVRD_sent",
                message_id=message_id,
                destination=destination_addr,
                error_code=error_code,
                reason=reason,
                dlr_text=dlr_text[:50]
            )

        except asyncio.CancelledError:
            logger.warning(
                "dlr_task_cancelled",
                message_id=message_id
            )
            raise

        except Exception as e:
            logger.error(
                "dlr_send_error",
                message_id=message_id,
                error=str(e),
                error_type=type(e).__name__
            )

        finally:
            active_tasks.dec()
