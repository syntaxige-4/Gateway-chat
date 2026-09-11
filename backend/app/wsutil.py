"""
wsutil.py — a minimal RFC 6455 WebSocket implementation from scratch, using only
the standard library (hashlib, base64, socket, struct). No `websockets` /
`websocket-client` package required.
"""
import hashlib
import base64
import struct
import socket

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

OPCODE_TEXT = 0x1
OPCODE_BINARY = 0x2
OPCODE_CLOSE = 0x8
OPCODE_PING = 0x9
OPCODE_PONG = 0xA


def compute_accept_key(client_key: str) -> str:
    sha1 = hashlib.sha1((client_key + WS_GUID).encode("utf-8")).digest()
    return base64.b64encode(sha1).decode("utf-8")


def build_handshake_response(client_key: str) -> bytes:
    accept = compute_accept_key(client_key)
    lines = [
        "HTTP/1.1 101 Switching Protocols",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Accept: {accept}",
        "", "",
    ]
    return "\r\n".join(lines).encode("utf-8")


def encode_frame(payload: bytes, opcode=OPCODE_TEXT) -> bytes:
    """Server -> client frames are never masked."""
    fin_and_opcode = 0x80 | opcode
    length = len(payload)
    if length <= 125:
        header = struct.pack("!BB", fin_and_opcode, length)
    elif length <= 0xFFFF:
        header = struct.pack("!BBH", fin_and_opcode, 126, length)
    else:
        header = struct.pack("!BBQ", fin_and_opcode, 127, length)
    return header + payload


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed")
        buf += chunk
    return buf


def decode_frame(sock: socket.socket):
    """Read and unmask one client -> server frame. Returns (opcode, payload) or None on close."""
    first2 = _recv_exact(sock, 2)
    b0, b1 = first2[0], first2[1]
    opcode = b0 & 0x0F
    masked = (b1 & 0x80) != 0
    length = b1 & 0x7F
    if length == 126:
        length = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(sock, 8))[0]
    mask_key = _recv_exact(sock, 4) if masked else b"\x00\x00\x00\x00"
    payload = _recv_exact(sock, length) if length else b""
    if masked:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    if opcode == OPCODE_CLOSE:
        return OPCODE_CLOSE, payload
    return opcode, payload


class WebSocketConnection:
    """Thin wrapper around a hijacked raw socket, used after the HTTP Upgrade handshake."""

    def __init__(self, sock: socket.socket, user_id: int):
        self.sock = sock
        self.user_id = user_id
        self.alive = True

    def send_text(self, text: str):
        if not self.alive:
            return
        try:
            self.sock.sendall(encode_frame(text.encode("utf-8"), OPCODE_TEXT))
        except OSError:
            self.alive = False

    def send_pong(self, payload=b""):
        try:
            self.sock.sendall(encode_frame(payload, OPCODE_PONG))
        except OSError:
            self.alive = False

    def recv(self):
        """Blocks until a frame arrives. Returns text payload (str) or None on close/error."""
        try:
            opcode, payload = decode_frame(self.sock)
        except (ConnectionError, OSError, struct.error):
            self.alive = False
            return None
        if opcode == OPCODE_CLOSE:
            self.alive = False
            return None
        if opcode == OPCODE_PING:
            self.send_pong(payload)
            return ""
        if opcode in (OPCODE_TEXT, OPCODE_BINARY):
            try:
                return payload.decode("utf-8")
            except UnicodeDecodeError:
                return ""
        return ""

    def close(self):
        self.alive = False
        try:
            self.sock.sendall(encode_frame(b"", OPCODE_CLOSE))
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
