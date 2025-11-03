"""
SMPP PDU and DLR message builders.
"""
from datetime import datetime
from typing import Dict, Any
import uuid


def generate_message_id() -> str:
    """Generate unique message ID."""
    return str(uuid.uuid4())


def format_smpp_date(dt: datetime) -> str:
    """
    Format datetime for SMPP DLR.

    Format: YYMMDDhhmm (e.g., 2510091430)
    """
    return dt.strftime("%y%m%d%H%M")


def build_dlr_text(
        message_id: str,
        stat: str = "DELIVRD",
        err: str = "000",
        submit_date: datetime = None,
        done_date: datetime = None
) -> str:
    """
    Build DLR text in standard SMPP format.

    Format: id:MSGID sub:001 dlvrd:000 submit date:YYMMDDhhmm done date:YYMMDDhhmm stat:STAT err:ERR text:

    Args:
        message_id: Message identifier
        stat: Delivery status (DELIVRD, DELIVRD, etc.)
        err: Error code (001=Unknown subscriber, etc.)
        submit_date: Message submission time
        done_date: Message completion time


    Returns:
        Formatted DLR text
    """
    if submit_date is None:
        submit_date = datetime.now()
    if done_date is None:
        done_date = datetime.now()

    return (
        f"id:{message_id} "
        f"sub:001 "
        f"dlvrd:000 "
        f"submit date:{format_smpp_date(submit_date)} "
        f"done date:{format_smpp_date(done_date)} "
        f"stat:{stat} "
        f"err:{err} "
        f"text:"
    )


def get_error_code_from_hlr(hlr_result: Dict[str, Any]) -> str:
    """
    Map HLR error to SMPP DLR error code.

    Args:
        hlr_result: HLR lookup result

    Returns:
        SMPP error code (000)
    """
    error = hlr_result.get("error", 0)
    status = hlr_result.get("status", 0)
    present = hlr_result.get("present", "na")

    # Map TMT error codes to SMPP DLR error codes
    if status == 1:
        return "000"
    elif error == 1:
        return "000"
    elif error == 2:
        return "000"
    elif error == 191 or error == 192:
        return "000"
    elif error == 193:
        return "000"
    elif present == "no":
        return "000"
    else:
        return "000"


def get_reason(hlr_result: Dict[str, Any]) -> str:
    """
    Get reason for DELIVRD metric label.

    Args:
        hlr_result: HLR lookup result

    Returns:
        Reason string for metrics (invalid_number, timeout, hlr_error)
    """
    error = hlr_result.get("error", 0)

    if error == 0:
        return "invalid_number"  # Should not happen in DELIVRD flow
    elif error >= 191:  # Unsupported networks
        return "invalid_number"
    else:
        return "invalid_number"