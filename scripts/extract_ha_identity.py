#!/usr/bin/env python3
"""Extract only the Xcel add-on cert.pem/key.pem from a Home Assistant partial backup.

This intentionally does not extract the rest of the backup. Treat the output directory as secret.
"""
from __future__ import annotations

import argparse
import io
from pathlib import Path
import tarfile


def _safe_member_bytes(archive: tarfile.TarFile, member_name: str) -> bytes:
    member = archive.getmember(member_name)
    if not member.isfile():
        raise RuntimeError(f"Expected a file: {member_name}")
    f = archive.extractfile(member)
    if f is None:
        raise RuntimeError(f"Unable to read {member_name}")
    return f.read()


def extract_identity(backup_path: Path, output_dir: Path, slug: str) -> tuple[Path, Path]:
    nested_name = f"{slug}.tar.gz"
    with tarfile.open(backup_path, "r:*") as outer:
        nested_bytes = _safe_member_bytes(outer, nested_name)

    with tarfile.open(fileobj=io.BytesIO(nested_bytes), mode="r:gz") as nested:
        cert_bytes = _safe_member_bytes(nested, "config/certs/cert.pem")
        key_bytes = _safe_member_bytes(nested, "config/certs/key.pem")

    output_dir.mkdir(parents=True, exist_ok=True)
    cert_path = output_dir / "cert.pem"
    key_path = output_dir / "key.pem"
    cert_path.write_bytes(cert_bytes)
    key_path.write_bytes(key_bytes)
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    return cert_path, key_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup", type=Path, help="Home Assistant partial backup .tar")
    parser.add_argument("--out", type=Path, default=Path("./certs"))
    parser.add_argument("--slug", default="513749ae_xcel-itron-mqtt")
    args = parser.parse_args()

    cert, key = extract_identity(args.backup, args.out, args.slug)
    print(f"Certificate: {cert}")
    print(f"Private key: {key}")
    print("WARNING: Keep this directory private. Do not commit or upload the private key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
