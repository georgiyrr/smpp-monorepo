"""
Async SMPP server implementation using asyncio.
"""
import asyncio
import struct
from typing import Optional

from src.config import settings
from src.logging_config import get_logger
from src.metrics import active_smpp_connections
from src.smpp.handler import SubmitSMHandler

logger = get_logger(__name__)

# SMPP constants
SMPP_CMD_BIND_TRANSMITTER = 0x00000001
SMPP_CMD_BIND_TRANSMITTER_RESP = 0x80000001
SMPP_CMD_BIND_RECEIVER = 0x00000002
SMPP_CMD_BIND_RECEIVER_RESP = 0x80000002
SMPP_CMD_BIND_TRANSCEIVER = 0x00000009
SMPP_CMD_BIND_TRANSCEIVER_RESP = 0x80000009
SMPP_CMD_UNBIND = 0x00000006
SMPP_CMD_UNBIND_RESP = 0x80000006
SMPP_CMD_SUBMIT_SM = 0x00000004
SMPP_CMD_SUBMIT_SM_RESP = 0x80000004
SMPP_CMD_ENQUIRE_LINK = 0x00000015
SMPP_CMD_ENQUIRE_LINK_RESP = 0x80000015

SMPP_ESME_RINVBNDSTS = 0x00000004
SMPP_ESME_RINVPASWD = 0x0000000E
SMPP_CMD_DELIVER_SM = 0x00000005
SMPP_CMD_DELIVER_SM_RESP = 0x80000005


class SMPPServer:
    """Async SMPP server."""

    def __init__(self):
        self.server: Optional[asyncio.Server] = None
        self.clients = set()

    async def start(self) -> None:
        """Start SMPP server."""
        self.server = await asyncio.start_server(
            self._handle_client,
            settings.smpp_host,
            settings.smpp_port
        )

        addr = self.server.sockets[0].getsockname()
        logger.info("smpp_server_started", host=addr[0], port=addr[1])

        async with self.server:
            await self.server.serve_forever()

    async def stop(self) -> None:
        """Stop SMPP server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        logger.info("smpp_server_stopped")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle individual SMPP client connection."""
        addr = writer.get_extra_info('peername')
        client_id = f"{addr[0]}:{addr[1]}"

        logger.info("client_connected", client_id=client_id)
        self.clients.add(client_id)
        active_smpp_connections.inc()

        session = SMPPSession(reader, writer, client_id)

        try:
            await session.run()
        except Exception as e:
            logger.error(
                "client_error",
                client_id=client_id,
                error=str(e),
                error_type=type(e).__name__
            )
        finally:
            self.clients.discard(client_id)
            active_smpp_connections.dec()
            logger.info("client_disconnected", client_id=client_id)

            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


class SMPPSession:
    """Individual SMPP client session handler."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        client_id: str
    ):
        self.reader = reader
        self.writer = writer
        self.client_id = client_id
        self.authenticated = False
        self.system_id: Optional[str] = None
        self.sequence_number = 1

    async def run(self) -> None:
        """Main session loop."""
        while True:
            try:
                header = await self.reader.readexactly(16)
                if not header:
                    break

                command_length, command_id, command_status, sequence = struct.unpack(
                    '>IIII',
                    header
                )

                body_length = command_length - 16
                body = b''
                if body_length > 0:
                    body = await self.reader.readexactly(body_length)

                await self._process_pdu(command_id, command_status, sequence, body)

            except asyncio.IncompleteReadError:
                break
            except ConnectionResetError:
                break
            except Exception as e:
                logger.error(
                    "pdu_processing_error",
                    client_id=self.client_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                break

    def _get_command_name(self, command_id: int) -> str:
        """Get command name for logging."""
        names = {
            0x00000001: "BIND_TRANSMITTER",
            0x00000002: "BIND_RECEIVER",
            0x00000004: "SUBMIT_SM",
            0x00000006: "UNBIND",
            0x00000009: "BIND_TRANSCEIVER",
            0x00000015: "ENQUIRE_LINK",
            0x80000005: "DELIVER_SM_RESP",
        }
        return names.get(command_id, f"UNKNOWN_{hex(command_id)}")

    async def _process_pdu(
        self,
        command_id: int,
        command_status: int,
        sequence: int,
        body: bytes
    ) -> None:

        logger.info(
            "pdu_received_processing",
            client_id=self.client_id,
            command_id=hex(command_id),
            command_name=self._get_command_name(command_id),
            sequence=sequence
        )

        """Process received PDU."""
        if command_id == SMPP_CMD_BIND_TRANSMITTER:
            await self._handle_bind(body, sequence, SMPP_CMD_BIND_TRANSMITTER_RESP)
        elif command_id == SMPP_CMD_BIND_RECEIVER:
            await self._handle_bind(body, sequence, SMPP_CMD_BIND_RECEIVER_RESP)
        elif command_id == SMPP_CMD_BIND_TRANSCEIVER:
            await self._handle_bind(body, sequence, SMPP_CMD_BIND_TRANSCEIVER_RESP)
        elif command_id == SMPP_CMD_UNBIND:
            await self._handle_unbind(sequence)
        elif command_id == SMPP_CMD_SUBMIT_SM:
            if self.authenticated:
                await self._handle_submit_sm(body, sequence)
            else:
                await self._send_error_response(
                    SMPP_CMD_SUBMIT_SM_RESP,
                    SMPP_ESME_RINVBNDSTS,
                    sequence
                )
        elif command_id == SMPP_CMD_ENQUIRE_LINK:
            # ✅ CRITICAL FIX: Fast path for ENQL
            await self._handle_enquire_link(sequence)
        elif command_id == SMPP_CMD_DELIVER_SM_RESP:
            logger.debug(
                "deliver_sm_resp_received",
                client_id=self.client_id,
                sequence=sequence,
                status=command_status
            )

    async def _handle_enquire_link(self, sequence: int) -> None:
        """
        Handle Enquire Link - MUST BE FAST!

        This is called frequently (every 5-30s) and MUST NOT block.
        Client (Alaris) blocks SubmitSM while waiting for ENQL_RSP.
        """
        logger.info(
            "enquire_link_received",
            client_id=self.client_id,
            sequence=sequence
        )

        # Build response PDU directly (no body, just header)
        command_length = 16
        header = struct.pack(
            '>IIII',
            command_length,
            SMPP_CMD_ENQUIRE_LINK_RESP,
            0,  # status = ESME_ROK
            sequence
        )

        # Write immediately
        self.writer.write(header)

        # ✅ CRITICAL: Do NOT await drain()!
        # drain() can block for 100-1000ms if TCP buffer is full
        # TCP will send when it can, we don't need to wait
        # This prevents blocking other operations (SubmitSM)

        logger.info(
            "enquire_link_resp_sent",
            client_id=self.client_id,
            sequence=sequence
        )

    async def _handle_bind(self, body: bytes, sequence: int, resp_cmd: int) -> None:
        """Handle bind request."""
        system_id, password = self._parse_bind_body(body)

        if system_id == settings.smpp_system_id and password == settings.smpp_password:
            self.authenticated = True
            self.system_id = system_id
            logger.info("bind_success", client_id=self.client_id, system_id=system_id)
            resp_body = b'SMPPGateway\x00'
            await self._send_response(resp_cmd, 0, sequence, resp_body)
        else:
            logger.warning("bind_failed", client_id=self.client_id, system_id=system_id)
            await self._send_error_response(resp_cmd, SMPP_ESME_RINVPASWD, sequence)

    async def _handle_unbind(self, sequence: int) -> None:
        """Handle unbind request."""
        logger.info("unbind_request", client_id=self.client_id)
        await self._send_response(SMPP_CMD_UNBIND_RESP, 0, sequence, b'')
        self.authenticated = False

    async def _handle_submit_sm(self, body: bytes, sequence: int) -> None:
        """Handle Submit SM request."""
        parsed = self._parse_submit_sm(body)

        handler = SubmitSMHandler(self)
        result = await handler.handle_submit_sm(
            pdu={},
            source_addr=parsed['source_addr'],
            destination_addr=parsed['destination_addr'],
            short_message=parsed['short_message']
        )

        command_status = result['command_status']
        message_id = result.get('message_id', '')

        if message_id:
            resp_body = message_id.encode('ascii') + b'\x00'
        else:
            resp_body = b'\x00'

        await self._send_response(
            SMPP_CMD_SUBMIT_SM_RESP,
            command_status,
            sequence,
            resp_body
        )

    def _parse_bind_body(self, body: bytes) -> tuple:
        """Parse Bind PDU body."""
        fields = body.split(b'\x00')
        system_id = fields[0].decode('ascii', errors='ignore') if fields else ''
        password = fields[1].decode('ascii', errors='ignore') if len(fields) > 1 else ''
        return system_id, password

    def _parse_submit_sm(self, body: bytes) -> dict:
        """Parse SubmitSM PDU body."""
        offset = 0

        # service_type (null-terminated)
        service_type_end = body.find(b'\x00', offset)
        offset = service_type_end + 1

        # source_addr_ton, source_addr_npi
        offset += 2

        # source_addr (null-terminated)
        source_addr_end = body.find(b'\x00', offset)
        source_addr = body[offset:source_addr_end].decode('ascii', errors='ignore')
        offset = source_addr_end + 1

        # dest_addr_ton, dest_addr_npi
        offset += 2

        # destination_addr (null-terminated)
        dest_addr_end = body.find(b'\x00', offset)
        destination_addr = body[offset:dest_addr_end].decode('ascii', errors='ignore')
        offset = dest_addr_end + 1

        # esm_class, protocol_id, priority_flag
        offset += 3

        # schedule_delivery_time (null-terminated)
        schedule_end = body.find(b'\x00', offset)
        offset = schedule_end + 1

        # validity_period (null-terminated)
        validity_end = body.find(b'\x00', offset)
        offset = validity_end + 1

        # registered_delivery, replace_if_present_flag, data_coding, sm_default_msg_id
        offset += 4

        # sm_length
        sm_length = body[offset]
        offset += 1

        # short_message
        short_message = body[offset:offset + sm_length]

        return {
            'source_addr': source_addr,
            'destination_addr': destination_addr,
            'short_message': short_message
        }

    async def _send_response(
        self,
        command_id: int,
        command_status: int,
        sequence: int,
        body: bytes
    ) -> None:
        """Send SMPP response PDU."""
        command_length = 16 + len(body)
        header = struct.pack('>IIII', command_length, command_id, command_status, sequence)
        pdu = header + body
        self.writer.write(pdu)

        ## ✅ Drain тільки для великих відповідей
        if len(body) > 100 or command_id == SMPP_CMD_DELIVER_SM:
            try:
                await asyncio.wait_for(self.writer.drain(), timeout=0.03)
            except asyncio.TimeoutError:
                pass

    async def _send_error_response(
        self,
        command_id: int,
        error_code: int,
        sequence: int
    ) -> None:
        """Send error response."""
        await self._send_response(command_id, error_code, sequence, b'')

    async def send_deliver_sm(
            self,
            source_addr: str,
            destination_addr: str,
            short_message: bytes,
            message_id: str = None
    ) -> None:
        """Send DeliverSM PDU to client (for DLR)."""
        if not self.authenticated:
            logger.warning(
                "deliver_sm_skipped_not_authenticated",
                client_id=self.client_id
            )
            return

        try:
            # Build DeliverSM body
            body = bytearray()

            # service_type (empty)
            body.extend(b'\x00')

            # source_addr_ton, source_addr_npi (International, ISDN)
            body.extend(bytes([1, 1]))

            # source_addr (null-terminated)
            body.extend(source_addr.encode('ascii'))
            body.extend(b'\x00')

            # dest_addr_ton, dest_addr_npi
            body.extend(bytes([1, 1]))

            # destination_addr (null-terminated)
            body.extend(destination_addr.encode('ascii'))
            body.extend(b'\x00')

            # esm_class (0x04 = SMSC Delivery Receipt)
            body.extend(bytes([0x04]))

            # protocol_id, priority_flag
            body.extend(bytes([0, 0]))

            # schedule_delivery_time (empty, null-terminated)
            body.extend(b'\x00')

            # validity_period (empty, null-terminated)
            body.extend(b'\x00')

            # registered_delivery, replace_if_present_flag
            body.extend(bytes([1, 0]))

            # data_coding (0 = SMSC Default)
            body.extend(bytes([0]))

            # sm_default_msg_id
            body.extend(bytes([0]))

            # sm_length
            sm_len = len(short_message)
            body.extend(bytes([sm_len]))

            # short_message
            body.extend(short_message)

            # Send PDU
            sequence = self.sequence_number
            self.sequence_number += 1

            await self._send_response(
                SMPP_CMD_DELIVER_SM,
                0,
                sequence,
                bytes(body)
            )

            logger.info(
                "deliver_sm_sent",
                client_id=self.client_id,
                message_id=message_id,
                source=source_addr,
                destination=destination_addr,
                sequence=sequence,
                dlr_length=sm_len
            )

        except Exception as e:
            logger.error(
                "deliver_sm_send_error",
                client_id=self.client_id,
                message_id=message_id,
                error=str(e),
                error_type=type(e).__name__
            )