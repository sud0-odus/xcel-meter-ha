from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .certificate import generate_client_identity
from .http import Ieee20305Client
from .identity import check_identity, normalize_lfdi, resolve_identity_paths
from .probe import probe_meter
from .reader import read_core_snapshot


def _print_cert(info) -> None:
    print(f"Certificate: {info.cert_path}")
    print(f"Private key: {info.key_path}")
    print(f"LFDI: {info.lfdi}")
    print(f"Valid from: {info.not_before.isoformat()}")
    print(f"Valid until: {info.not_after.isoformat()}")
    print(f"Days remaining: {info.days_remaining}")
    print(f"Expired: {info.is_expired}")
    print(f"EC curve: {info.curve}")
    print(f"Key matches certificate: {info.key_matches}")
    print(f"IEEE 2030.5 client policy present: {info.ieee_policy_present}")
    print(f"Digital-signature key usage: {info.digital_signature_only}")
    if info.days_remaining <= 90:
        print("WARNING: certificate expires within 90 days; rotate and provision a replacement before expiry.")


def _validate_identity(cert_dir: str, expected_lfdi: str | None) -> tuple[Path, Path]:
    check = check_identity(cert_dir, expected_lfdi)
    _print_cert(check.info)
    if expected_lfdi is not None:
        expected = normalize_lfdi(expected_lfdi)
        actual = normalize_lfdi(check.info.lfdi)
        print(f"Expected/Launchpad LFDI: {expected}")
        if expected != actual:
            raise RuntimeError(
                "Configured/expected LFDI does not match the certificate-derived LFDI. "
                f"Expected {expected}; certificate is {actual}. Register the certificate LFDI "
                "with Xcel Launchpad or restore the certificate that belongs to the expected LFDI."
            )
        print("LFDI check: MATCH")
    if check.info.is_expired:
        raise RuntimeError("Client certificate is expired")
    if not check.info.key_matches:
        raise RuntimeError("Client certificate and private key do not match")
    if not check.info.ieee_policy_present:
        raise RuntimeError("Required IEEE 2030.5 client certificate policy is missing")
    if check.info.curve != "secp256r1":
        raise RuntimeError(f"Unsupported EC curve {check.info.curve}; expected secp256r1/P-256")
    return check.info.cert_path, check.info.key_path


def _add_meter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--dir", default="./certs")
    parser.add_argument("--expected-lfdi")
    parser.add_argument("--timeout", type=float, default=8.0)


def main() -> int:
    parser = argparse.ArgumentParser(prog="xcel-meter")
    sub = parser.add_subparsers(dest="command", required=True)

    cert = sub.add_parser("cert", help="Generate or inspect an IEEE 2030.5 client identity")
    cert_sub = cert.add_subparsers(dest="cert_command", required=True)

    init = cert_sub.add_parser("init", help="Generate a new EC P-256 client certificate")
    init.add_argument("--dir", default="./certs")
    init.add_argument("--cn", default="MeterReaderHanClient")
    init.add_argument("--overwrite", action="store_true")

    show = cert_sub.add_parser("show", help="Print certificate validity and LFDI")
    show.add_argument("--dir", default="./certs")
    show.add_argument("--expected-lfdi")

    probe = sub.add_parser("probe", help="Perform one TLS/HTTP probe against the meter")
    _add_meter_args(probe)
    probe.add_argument("--path", default="/sdev/sdi")

    read = sub.add_parser(
        "read", help="Discover the meter and print core power/energy readings as JSON"
    )
    _add_meter_args(read)
    read.add_argument("--pretty", action="store_true")

    args = parser.parse_args()

    try:
        if args.command == "cert" and args.cert_command == "init":
            cert_path, key_path = resolve_identity_paths(args.dir)
            info = generate_client_identity(cert_path, key_path, args.cn, overwrite=args.overwrite)
            _print_cert(info)
            print("\nRegister EXACTLY this LFDI in Xcel Energy Launchpad before probing the meter.")
            return 0

        if args.command == "cert" and args.cert_command == "show":
            check = check_identity(args.dir, args.expected_lfdi)
            _print_cert(check.info)
            if args.expected_lfdi is not None:
                print(f"Expected/Launchpad LFDI: {normalize_lfdi(args.expected_lfdi)}")
                print("LFDI check: " + ("MATCH" if check.lfdi_matches_expected else "MISMATCH"))
                return 0 if check.lfdi_matches_expected else 3
            return 0

        if args.command == "probe":
            cert_path, key_path = _validate_identity(args.dir, args.expected_lfdi)
            print(f"\nProbing https://{args.host}:{args.port}{args.path} once (no retry loop)...")
            result = probe_meter(args.host, args.port, cert_path, key_path, args.path, args.timeout)
            print(f"Stage: {result.stage}")
            print(f"Result: {result.summary}")
            if result.negotiated_cipher:
                print(f"Cipher: {result.negotiated_cipher}")
            if result.response_head:
                print("\nResponse preview:")
                print(result.response_head)
            return 0 if result.ok else 2

        if args.command == "read":
            cert_path, key_path = _validate_identity(args.dir, args.expected_lfdi)
            client = Ieee20305Client(args.host, args.port, cert_path, key_path, args.timeout)
            snapshot = read_core_snapshot(client, args.host, args.port)
            print(json.dumps(snapshot.to_dict(), indent=2 if args.pretty else None, sort_keys=True))
            return 0

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
