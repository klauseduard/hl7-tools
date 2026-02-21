"""MLLP (Minimal Lower Layer Protocol) transport for HL7 messages."""

import socket
import time

MLLP_VT = b'\x0b'
MLLP_FS = b'\x1c'
MLLP_CR = b'\x0d'


def reconstruct_message(parsed) -> str:
    """Join parsed segments' raw_lines with \\r for wire format."""
    return '\r'.join(seg.raw_line for seg in parsed.segments) + '\r'


def mllp_send(host, port, message_text, timeout=10, wait_for_ack=True,
              tls_config=None):
    """Send MLLP-framed HL7 message and optionally wait for response.

    Args:
        host: Target hostname or IP
        port: Target port number
        message_text: HL7 message text (segments joined with \\r)
        timeout: Socket timeout in seconds
        wait_for_ack: If True, wait for and return the ACK response
        tls_config: Optional dict with TLS settings:
            ca_cert: path to CA certificate PEM
            client_cert: path to client certificate PEM (enables mTLS)
            client_key: path to client private key PEM
            insecure: skip server certificate verification

    Returns:
        (response_text: str|None, elapsed_ms: int)

    Raises:
        ConnectionError, TimeoutError, OSError, ssl.SSLError
    """
    payload = MLLP_VT + message_text.encode('utf-8') + MLLP_FS + MLLP_CR

    start = time.monotonic()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        if tls_config:
            import ssl
            if tls_config.get("insecure"):
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            elif tls_config.get("ca_cert"):
                ctx = ssl.create_default_context(cafile=tls_config["ca_cert"])
            else:
                ctx = ssl.create_default_context()
            if tls_config.get("client_cert"):
                ctx.load_cert_chain(
                    certfile=tls_config["client_cert"],
                    keyfile=tls_config.get("client_key"),
                )
            sock = ctx.wrap_socket(sock, server_hostname=host)
        sock.connect((host, port))
        sock.sendall(payload)

        if not wait_for_ack:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return None, elapsed_ms

        # Read until we see FS byte
        buf = bytearray()
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
            if MLLP_FS[0] in buf:
                break

        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Strip MLLP framing: VT at start, FS+CR at end
        data = bytes(buf)
        if data.startswith(MLLP_VT):
            data = data[1:]
        fs_pos = data.find(MLLP_FS)
        if fs_pos >= 0:
            data = data[:fs_pos]

        return data.decode('utf-8', errors='replace'), elapsed_ms
    finally:
        sock.close()
