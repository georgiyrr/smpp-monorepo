# !/usr/bin/env python3
"""
Example SMPP client for testing the gateway.

Usage:
    python examples/test_client.py --host localhost --port 2776 --msisdn 13476841841
"""
import sys
import argparse
import socket
import struct


class SimpleSmppClient:
    """Simple SMPP client for testing."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = None
        self.sequence = 1

    def connect(self):
        """Connect to SMPP server."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))

    def disconnect(self):
        """Disconnect from server."""
        if self.sock:
            self.sock.close()

    def _send_pdu(self, command_id: int, body: bytes) -> bytes:
        """Send PDU and receive response."""
        command_length = 16 + len(body)
        header = struct.pack('>IIII', command_length, command_id, 0, self.sequence)
        pdu = header + body

        self.sock.sendall(pdu)
        self.sequence += 1

        # Receive response
        resp_header = self.sock.recv(16)
        resp_length, resp_cmd, resp_status, resp_seq = struct.unpack('>IIII', resp_header)

        resp_body = b''
        if resp_length > 16:
            resp_body = self.sock.recv(resp_length - 16)

        return resp_status, resp_body

    def bind_transmitter(self, system_id: str, password: str):
        """Bind as transmitter."""
        body = system_id.encode() + b'\x00'
        body += password.encode() + b'\x00'
        body += b'\x00' * 10  # Other fields

        status, _ = self._send_pdu(0x00000001, body)
        return status == 0

    def submit_sm(self, source: str, destination: str, message: str):
        """Submit SM."""
        body = b'\x00'  # service_type
        body += b'\x01'  # source_addr_ton
        body += b'\x01'  # source_addr_npi
        body += source.encode() + b'\x00'
        body += b'\x01'  # dest_addr_ton
        body += b'\x01'  # dest_addr_npi
        body += destination.encode() + b'\x00'
        body += b'\x00'  # esm_class
        body += b'\x00'  # protocol_id
        body += b'\x00'  # priority_flag
        body += b'\x00'  # schedule_delivery_time
        body += b'\x00'  # validity_period
        body += b'\x00'  # registered_delivery
        body += b'\x00'  # replace_if_present_flag
        body += b'\x00'  # data_coding
        body += b'\x00'  # sm_default_msg_id

        msg_bytes = message.encode('utf-8')
        body += bytes([len(msg_bytes)])
        body += msg_bytes

        status, resp_body = self._send_pdu(0x00000004, body)

        # Extract message_id from response
        message_id = resp_body.rstrip(b'\x00').decode('ascii', errors='ignore') if resp_body else ''

        return status, message_id

    def unbind(self):
        """Unbind."""
        self._send_pdu(0x00000006, b'')


def test_submit_sm(host: str, port: int, system_id: str, password: str, msisdn: str, message: str):
    """Send test SubmitSM to SMPP gateway."""
    print(f"Connecting to {host}:{port}...")

    try:
        client = SimpleSmppClient(host, port)
        client.connect()
        print("✓ Connected")

        # Bind
        success = client.bind_transmitter(system_id, password)
        if not success:
            print("✗ Bind failed")
            return False
        print(f"✓ Bound as transmitter (system_id={system_id})")

        # Send message
        print(f"\nSending SubmitSM:")
        print(f"  Destination: {msisdn}")
        print(f"  Message: {message}")

        status, message_id = client.submit_sm('1234', msisdn, message)

        # Check response
        if status == 0x00000000:  # ESME_ROK
            print(f"\n✓ Message ACCEPTED")
            print(f"  Status: ESME_ROK (0x{status:08X})")
            print(f"  Message ID: {message_id}")
            print(f"\n  → Expect DELIVRD DLR (invalid/unreachable number)")
            result = True
        elif status == 0x0000000B:  # ESME_RINVDSTADR
            print(f"\n✗ Message REJECTED")
            print(f"  Status: ESME_RINVDSTADR (0x{status:08X})")
            print(f"  Reason: Invalid destination address")
            print(f"\n  → Number is VALID (filtered by gateway)")
            result = True
        else:
            print(f"\n✗ Message REJECTED")
            print(f"  Status: 0x{status:08X}")
            result = False

        # Unbind
        client.unbind()
        print("\n✓ Unbound")

        # Disconnect
        client.disconnect()
        print("✓ Disconnected")

        return result

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test SMPP client for HLR gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with valid number (will be rejected)
  python test_client.py --msisdn 13476841841

  # Test with invalid number (will be accepted + DELIVRD)
  python test_client.py --msisdn 40722570240999

  # Custom message
  python test_client.py --msisdn 13476841841 --message "Hello World"
        """
    )

    parser.add_argument('--host', default='localhost', help='SMPP server host')
    parser.add_argument('--port', type=int, default=2776, help='SMPP server port')
    parser.add_argument('--system-id', default='testuser', help='System ID')
    parser.add_argument('--password', default='testpass', help='Password')
    parser.add_argument('--msisdn', required=True, help='Destination phone number')
    parser.add_argument('--message', default='Test message', help='Message text')

    args = parser.parse_args()

    print("=" * 60)
    print("SMPP HLR Gateway Test Client")
    print("=" * 60)

    success = test_submit_sm(
        host=args.host,
        port=args.port,
        system_id=args.system_id,
        password=args.password,
        msisdn=args.msisdn,
        message=args.message
    )

    print("\n" + "=" * 60)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()