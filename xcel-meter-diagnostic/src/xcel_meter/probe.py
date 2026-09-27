from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .http import Ieee20305Client, MeterHttpError


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    stage: str
    summary: str
    negotiated_cipher: str | None = None
    response_head: str | None = None


def probe_meter(
    host: str,
    port: int,
    cert_path: Path,
    key_path: Path,
    path: str = "/sdev/sdi",
    timeout: float = 8.0,
) -> ProbeResult:
    client = Ieee20305Client(host, port, cert_path, key_path, timeout)
    try:
        response = client.get(path)
    except MeterHttpError as exc:
        message = str(exc)
        stage = "tls" if "TLS" in message or "certificate" in message else "tcp/http"
        return ProbeResult(False, stage, message)
    first_line = f"HTTP {response.status} {response.reason}".strip()
    preview = "\n".join(response.text.splitlines()[:20])
    return ProbeResult(
        True,
        "http",
        first_line,
        negotiated_cipher=response.cipher,
        response_head=preview,
    )
