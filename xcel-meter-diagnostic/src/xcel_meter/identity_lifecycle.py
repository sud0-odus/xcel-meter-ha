from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .certificate import CertificateInfo, generate_client_identity, inspect_client_identity


@dataclass(frozen=True)
class IdentityLocation:
    source: str
    cert_path: Path
    key_path: Path


@dataclass(frozen=True)
class IdentityPreparation:
    location: IdentityLocation
    action: str
    info: CertificateInfo


def candidate_pairs(directory: Path) -> Iterable[tuple[Path, Path]]:
    names = [
        ("cert.pem", "key.pem"),
        (".cert.pem", ".key.pem"),
        ("client.crt", "client.key"),
    ]
    for cert_name, key_name in names:
        yield directory / cert_name, directory / key_name


def find_pair(directory: Path) -> tuple[Path, Path] | None:
    partial: list[str] = []
    for cert_path, key_path in candidate_pairs(directory):
        cert_exists = cert_path.is_file()
        key_exists = key_path.is_file()
        if cert_exists and key_exists:
            return cert_path, key_path
        if cert_exists != key_exists:
            partial.append(f"{cert_path.name}/{key_path.name}")
    if partial:
        raise RuntimeError(
            f"Incomplete certificate identity under {directory}: {', '.join(partial)}. "
            "Do not generate over a partial identity; restore the matching pair first."
        )
    return None


def _legacy_directories(all_addon_configs_root: Path, legacy_addon_slug: str | None) -> list[Path]:
    if legacy_addon_slug:
        return [all_addon_configs_root / legacy_addon_slug / "certs"]
    if not all_addon_configs_root.is_dir():
        return []
    return [
        p / "certs"
        for p in sorted(all_addon_configs_root.iterdir())
        if p.is_dir() and p.name.endswith("_xcel-itron-mqtt")
    ]


def find_legacy_identity(
    all_addon_configs_root: Path,
    legacy_addon_slug: str | None = None,
) -> IdentityLocation | None:
    for directory in _legacy_directories(all_addon_configs_root, legacy_addon_slug):
        pair = find_pair(directory)
        if pair:
            return IdentityLocation("legacy", pair[0], pair[1])
    return None


def find_own_identity(own_config_root: Path) -> IdentityLocation | None:
    for directory in (own_config_root / "certs", own_config_root):
        pair = find_pair(directory)
        if pair:
            return IdentityLocation("own", pair[0], pair[1])
    return None


def _validate_profile(info: CertificateInfo) -> None:
    if info.is_expired:
        raise RuntimeError("Client certificate is expired")
    if not info.key_matches:
        raise RuntimeError("Client certificate and private key do not match")
    if not info.self_signed:
        raise RuntimeError("Client certificate is not self-signed as required by the IEEE 2030.5 client profile")
    if not info.ieee_policy_present or not info.ieee_policy_critical:
        raise RuntimeError("Required critical IEEE 2030.5 self-signed-client certificate policy is missing")
    if not info.digital_signature_present or not info.key_usage_critical:
        raise RuntimeError("Certificate must have a critical KeyUsage containing digitalSignature")
    if info.curve != "secp256r1":
        raise RuntimeError(f"Unsupported EC curve {info.curve}; expected secp256r1/P-256")
    if info.signature_hash.lower() != "sha256":
        raise RuntimeError(f"Unsupported certificate signature hash {info.signature_hash}; expected SHA-256")


def migrate_identity(source: IdentityLocation, own_config_root: Path) -> IdentityPreparation:
    source_info = inspect_client_identity(source.cert_path, source.key_path)
    _validate_profile(source_info)

    destination = own_config_root / "certs"
    destination.mkdir(parents=True, exist_ok=True)
    cert_path = destination / "cert.pem"
    key_path = destination / "key.pem"

    existing = find_pair(destination)
    if existing:
        existing_info = inspect_client_identity(existing[0], existing[1])
        if existing_info.lfdi != source_info.lfdi:
            raise RuntimeError(
                "App-owned identity already exists with a different LFDI; refusing to overwrite it."
            )
        return IdentityPreparation(
            IdentityLocation("own", existing[0], existing[1]),
            "existing",
            existing_info,
        )

    cert_tmp = destination / ".cert.pem.migrating"
    key_tmp = destination / ".key.pem.migrating"
    try:
        shutil.copyfile(source.cert_path, cert_tmp)
        shutil.copyfile(source.key_path, key_tmp)
        key_tmp.chmod(0o600)
        migrated_info = inspect_client_identity(cert_tmp, key_tmp)
        _validate_profile(migrated_info)
        if migrated_info.lfdi != source_info.lfdi:
            raise RuntimeError("Migrated identity LFDI changed unexpectedly; migration aborted")
        os.replace(cert_tmp, cert_path)
        os.replace(key_tmp, key_path)
        key_path.chmod(0o600)
    finally:
        cert_tmp.unlink(missing_ok=True)
        key_tmp.unlink(missing_ok=True)

    final_info = inspect_client_identity(cert_path, key_path)
    return IdentityPreparation(IdentityLocation("own", cert_path, key_path), "migrated", final_info)


def prepare_identity(
    source: str,
    *,
    own_config_root: Path = Path("/config"),
    all_addon_configs_root: Path = Path("/addon_configs"),
    legacy_addon_slug: str | None = None,
    migrate_legacy: bool = True,
    generate_if_missing: bool = True,
) -> IdentityPreparation:
    source = source.strip().lower()
    if source not in {"auto", "own", "legacy"}:
        raise ValueError(f"Unsupported identity_source {source!r}; use auto, own, or legacy")

    if source in {"auto", "own"}:
        own = find_own_identity(own_config_root)
        if own:
            info = inspect_client_identity(own.cert_path, own.key_path)
            return IdentityPreparation(own, "existing", info)

    if source in {"auto", "legacy"}:
        legacy = find_legacy_identity(all_addon_configs_root, legacy_addon_slug)
        if legacy:
            if source == "auto" and migrate_legacy:
                return migrate_identity(legacy, own_config_root)
            info = inspect_client_identity(legacy.cert_path, legacy.key_path)
            return IdentityPreparation(legacy, "legacy", info)
        if source == "legacy":
            raise FileNotFoundError("No legacy Xcel iTron MQTT certificate/key found")

    if source in {"auto", "own"} and generate_if_missing:
        destination = own_config_root / "certs"
        destination.mkdir(parents=True, exist_ok=True)
        cert_path = destination / "cert.pem"
        key_path = destination / "key.pem"
        info = generate_client_identity(cert_path, key_path)
        return IdentityPreparation(IdentityLocation("own", cert_path, key_path), "generated", info)

    raise FileNotFoundError(
        "No usable client identity found. Enable generate_identity_if_missing or provide an existing identity."
    )




def read_identity_manifest(own_config_root: Path = Path("/config")) -> dict:
    path = own_config_root / "certs" / "identity.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_identity_manifest(
    preparation: IdentityPreparation,
    *,
    own_config_root: Path = Path("/config"),
    meter_authenticated: bool | None = None,
) -> Path | None:
    if preparation.location.source != "own":
        return None
    destination = own_config_root / "certs" / "identity.json"
    existing = read_identity_manifest(own_config_root)

    origin = existing.get("identity_origin")
    if preparation.action in {"generated", "migrated"}:
        origin = preparation.action
    elif not origin:
        origin = "existing"

    previously_authenticated = bool(existing.get("meter_authenticated", False))
    if previously_authenticated:
        onboarding_state = "active"
    elif origin == "generated":
        onboarding_state = "register_or_wait_for_provisioning"
    elif origin == "migrated":
        onboarding_state = "migrated_not_yet_validated"
    else:
        onboarding_state = "identity_ready_not_yet_validated"

    payload = {
        "schema_version": 1,
        "lfdi": preparation.info.lfdi,
        "certificate_expiration": preparation.info.not_after.isoformat(),
        "identity_origin": origin,
        "last_identity_action": preparation.action,
        "meter_authenticated": previously_authenticated,
        "last_meter_authenticated_utc": existing.get("last_meter_authenticated_utc"),
        "onboarding_state": onboarding_state,
        "updated_utc": datetime.now(UTC).isoformat(),
    }
    if meter_authenticated is True:
        payload["meter_authenticated"] = True
        payload["onboarding_state"] = "active"
        payload["last_meter_authenticated_utc"] = datetime.now(UTC).isoformat()
    elif meter_authenticated is False:
        payload["meter_authenticated"] = False

    tmp = destination.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, destination)
    return destination
