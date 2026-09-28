from __future__ import annotations

import logging
import socket
import ssl
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from .version import APP_VERSION


LOGGER = logging.getLogger("xcel_meter.http")

IEEE2030_5_ACCEPT = "application/sep+xml;level=-S1"
IEEE2030_5_TLS_CIPHER = "ECDHE-ECDSA-AES128-CCM8:@SECLEVEL=0"


class MeterHttpError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        kind: str = "protocol",
        status: int | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status
        self.path = path

    @property
    def invalidates_profile(self) -> bool:
        """Return True only when the cached resource is known to be gone."""
        return self.kind == "http" and self.status in {404, 410}


def _is_transient_bad_signature(exc: ssl.SSLError) -> bool:
    return "bad signature" in str(exc).lower()


def _is_transient_handshake_timeout(exc: BaseException) -> bool:
    return "handshake operation timed out" in str(exc).lower()


def _is_retryable_transport_error(exc: BaseException) -> bool:
    return isinstance(
        exc,
        (
            TimeoutError,
            ConnectionResetError,
            ConnectionAbortedError,
            BrokenPipeError,
        ),
    ) or _is_transient_handshake_timeout(exc)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    reason: str
    headers: dict[str, str]
    body: bytes
    cipher: str | None

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


def build_ssl_context(cert_path: Path, key_path: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_2
    context.options |= ssl.OP_LEGACY_SERVER_CONNECT
    context.set_ciphers(IEEE2030_5_TLS_CIPHER)
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    return context


def classify_ssl_error(exc: ssl.SSLError) -> str:
    message = str(exc).lower()
    if "bad certificate" in message:
        return (
            "The meter rejected the client certificate during mutual TLS. Verify the LFDI "
            "derived from the certificate is registered/provisioned in Xcel Energy Launchpad."
        )
    if "certificate expired" in message:
        return "A certificate in the TLS exchange appears expired."
    if "handshake failure" in message or "no shared cipher" in message:
        return (
            "TLS negotiation failed before HTTP. The meter expects TLS 1.2 with "
            "ECDHE-ECDSA-AES128-CCM8."
        )
    return f"TLS failed: {exc}"


def _decode_chunked(body: bytes) -> bytes:
    output = bytearray()
    cursor = 0
    while True:
        line_end = body.find(b"\r\n", cursor)
        if line_end < 0:
            raise MeterHttpError("Malformed chunked HTTP response")
        size_text = body[cursor:line_end].split(b";", 1)[0]
        size = int(size_text, 16)
        cursor = line_end + 2
        if size == 0:
            return bytes(output)
        output.extend(body[cursor : cursor + size])
        cursor += size
        if body[cursor : cursor + 2] != b"\r\n":
            raise MeterHttpError("Malformed chunk terminator")
        cursor += 2


def parse_http_response(raw: bytes, cipher: str | None = None) -> HttpResponse:
    head, sep, body = raw.partition(b"\r\n\r\n")
    if not sep:
        raise MeterHttpError("Meter returned an incomplete HTTP response")
    lines = head.decode("iso-8859-1", errors="replace").split("\r\n")
    if not lines or not lines[0].startswith("HTTP/"):
        raise MeterHttpError("Meter returned a non-HTTP response")
    parts = lines[0].split(" ", 2)
    if len(parts) < 2:
        raise MeterHttpError(f"Malformed HTTP status line: {lines[0]}")
    status = int(parts[1])
    reason = parts[2] if len(parts) > 2 else ""
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    if headers.get("transfer-encoding", "").lower() == "chunked":
        body = _decode_chunked(body)
    elif "content-length" in headers:
        body = body[: int(headers["content-length"])]
    return HttpResponse(status=status, reason=reason, headers=headers, body=body, cipher=cipher)


class Ieee20305Client:
    def __init__(
        self,
        host: str,
        port: int,
        cert_path: Path,
        key_path: Path,
        timeout: float = 8.0,
    ) -> None:
        self.host = host
        self.port = port
        self.cert_path = cert_path
        self.key_path = key_path
        self.timeout = timeout
        self._ssl_context = build_ssl_context(cert_path, key_path)

    def get(self, path: str) -> HttpResponse:
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc:
            raise ValueError("Meter request path must be relative, e.g. /sdev/sdi")

        request_path = path if path.startswith("/") else f"/{path}"
        request = (
            f"GET {request_path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Accept: {IEEE2030_5_ACCEPT}\r\n"
            f"User-Agent: xcel-meter-ha/{APP_VERSION}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")

        for attempt in range(2):
            try:
                with (
                    socket.create_connection(
                        (self.host, self.port),
                        timeout=self.timeout,
                    ) as raw,
                    self._ssl_context.wrap_socket(
                        raw,
                        server_hostname=self.host,
                    ) as tls,
                ):
                    tls.settimeout(self.timeout)
                    tls.sendall(request)

                    chunks: list[bytes] = []
                    while True:
                        chunk = tls.recv(16384)
                        if not chunk:
                            break
                        chunks.append(chunk)

                    cipher = tls.cipher()[0] if tls.cipher() else None

            except ssl.SSLError as exc:
                if attempt == 0 and (
                    _is_transient_bad_signature(exc)
                    or _is_transient_handshake_timeout(exc)
                ):
                    LOGGER.warning(
                        "Transient TLS handshake failure from meter; "
                        "retrying request once: %s",
                        exc,
                    )
                    time.sleep(0.25)
                    continue

                kind = "client_auth" if "bad certificate" in str(exc).lower() else "transport"
                raise MeterHttpError(
                    classify_ssl_error(exc),
                    kind=kind,
                    path=request_path,
                ) from exc

            except (ConnectionRefusedError, TimeoutError, OSError) as exc:
                if (
                    attempt == 0
                    and _is_retryable_transport_error(exc)
                ):
                    LOGGER.warning(
                        "Transient meter transport failure; "
                        "retrying request once: %s",
                        exc,
                    )
                    time.sleep(0.25)
                    continue

                raise MeterHttpError(
                    (
                        f"TCP connection to {self.host}:{self.port} "
                        f"failed: {exc}"
                    ),
                    kind="transport",
                    path=request_path,
                ) from exc

            response = parse_http_response(b"".join(chunks), cipher)

            if not 200 <= response.status < 300:
                preview = response.text.strip().replace("\n", " ")[:300]
                raise MeterHttpError(
                    (
                        f"Meter returned HTTP {response.status} "
                        f"{response.reason} for {request_path}. "
                        f"Response: {preview or '<empty>'}"
                    ),
                    kind="http",
                    status=response.status,
                    path=request_path,
                )

            return response

        raise MeterHttpError("Meter request retry loop exhausted unexpectedly")

    def get_xml(self, path: str) -> str:
        return self.get(path).text
