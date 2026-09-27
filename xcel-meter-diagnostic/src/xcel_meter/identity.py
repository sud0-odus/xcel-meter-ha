from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .certificate import CertificateInfo, inspect_client_identity


@dataclass(frozen=True)
class IdentityCheck:
    info: CertificateInfo
    expected_lfdi: str | None
    lfdi_matches_expected: bool | None


def normalize_lfdi(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch in "0123456789ABCDEF")


def resolve_identity_paths(cert_dir: str) -> tuple[Path, Path]:
    root = Path(cert_dir).expanduser().resolve()
    candidates = [
        (root / "cert.pem", root / "key.pem"),
        (root / ".cert.pem", root / ".key.pem"),
    ]
    for cert, key in candidates:
        if cert.exists() and key.exists():
            return cert, key
    # Preserve the upstream hidden-file convention for a fresh identity.
    return root / ".cert.pem", root / ".key.pem"


def check_identity(cert_dir: str, expected_lfdi: str | None = None) -> IdentityCheck:
    cert_path, key_path = resolve_identity_paths(cert_dir)
    info = inspect_client_identity(cert_path, key_path)
    if expected_lfdi is None:
        match = None
    else:
        match = normalize_lfdi(expected_lfdi) == normalize_lfdi(info.lfdi)
    return IdentityCheck(info=info, expected_lfdi=expected_lfdi, lfdi_matches_expected=match)
