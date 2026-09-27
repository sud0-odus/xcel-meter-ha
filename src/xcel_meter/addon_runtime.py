from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .certificate import inspect_client_identity
from .http import Ieee20305Client
from .identity import normalize_lfdi
from .models import MeterSnapshot
from .mqtt_runtime import MqttPublisher
from .reader import MeterProfile, discover_core_profile, read_core_snapshot

LOGGER = logging.getLogger("xcel_meter.addon")


@dataclass(frozen=True)
class IdentityLocation:
    source: str
    cert_path: Path
    key_path: Path


def _candidate_pairs(directory: Path) -> Iterable[tuple[Path, Path]]:
    names = [
        ("cert.pem", "key.pem"),
        (".cert.pem", ".key.pem"),
        ("client.crt", "client.key"),
    ]
    for cert_name, key_name in names:
        yield directory / cert_name, directory / key_name


def _find_pair(directory: Path) -> tuple[Path, Path] | None:
    for cert_path, key_path in _candidate_pairs(directory):
        if cert_path.is_file() and key_path.is_file():
            return cert_path, key_path
    return None


def find_identity(
    source: str,
    own_config_root: Path = Path("/config"),
    all_addon_configs_root: Path = Path("/addon_configs"),
    legacy_addon_slug: str | None = None,
) -> IdentityLocation:
    source = source.strip().lower()
    if source not in {"auto", "own", "legacy"}:
        raise ValueError(f"Unsupported identity_source {source!r}; use auto, own, or legacy")

    own_dirs = [own_config_root / "certs", own_config_root]
    if source in {"auto", "own"}:
        for directory in own_dirs:
            pair = _find_pair(directory)
            if pair:
                return IdentityLocation("own", pair[0], pair[1])
        if source == "own":
            raise FileNotFoundError(
                "No certificate/key found in this app's public config. "
                "Expected /config/certs/cert.pem and /config/certs/key.pem."
            )

    if source in {"auto", "legacy"}:
        legacy_dirs: list[Path] = []
        if legacy_addon_slug:
            legacy_dirs.append(all_addon_configs_root / legacy_addon_slug / "certs")
        elif all_addon_configs_root.is_dir():
            legacy_dirs.extend(
                p / "certs"
                for p in sorted(all_addon_configs_root.iterdir())
                if p.is_dir() and p.name.endswith("_xcel-itron-mqtt")
            )

        for directory in legacy_dirs:
            pair = _find_pair(directory)
            if pair:
                return IdentityLocation("legacy", pair[0], pair[1])

        raise FileNotFoundError(
            "No legacy Xcel iTron MQTT certificate/key found. "
            "Keep the legacy app installed or place cert.pem/key.pem under this app's config/certs folder."
        )

    raise RuntimeError("Identity discovery failed")


def load_options(path: Path = Path("/data/options.json")) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_lfdi(value: str) -> str:
    normalized = normalize_lfdi(value)
    return "-".join(normalized[i : i + 5] for i in range(0, len(normalized), 5))


def validate_identity(location: IdentityLocation, expected_lfdi: str | None) -> str:
    info = inspect_client_identity(location.cert_path, location.key_path)
    actual = normalize_lfdi(info.lfdi)

    LOGGER.info("Identity source: %s", location.source)
    LOGGER.info("Certificate: %s", location.cert_path)
    LOGGER.info("Certificate-derived LFDI: %s", _format_lfdi(actual))
    LOGGER.info("Certificate valid until: %s", info.not_after.isoformat())
    LOGGER.info("Certificate days remaining: %s", info.days_remaining)
    LOGGER.info("EC curve: %s", info.curve)
    LOGGER.info("Certificate/key match: %s", "OK" if info.key_matches else "FAIL")
    LOGGER.info("IEEE 2030.5 policy: %s", "OK" if info.ieee_policy_present else "FAIL")
    LOGGER.info("Digital-signature key usage: %s", "OK" if info.digital_signature_only else "FAIL")

    if info.is_expired:
        raise RuntimeError("Client certificate is expired")
    if not info.key_matches:
        raise RuntimeError("Client certificate and private key do not match")
    if not info.ieee_policy_present:
        raise RuntimeError("Required IEEE 2030.5 certificate policy is missing")
    if not info.digital_signature_only:
        raise RuntimeError("Certificate key usage does not match IEEE 2030.5 client requirements")
    if info.curve != "secp256r1":
        raise RuntimeError(f"Unsupported EC curve {info.curve}; expected secp256r1/P-256")

    if expected_lfdi and expected_lfdi.strip():
        expected = normalize_lfdi(expected_lfdi)
        LOGGER.info("Expected/Launchpad LFDI: %s", _format_lfdi(expected))
        if expected != actual:
            raise RuntimeError(
                "LFDI MISMATCH: configured/Launchpad LFDI does not match the actual certificate. "
                f"Launchpad/config={_format_lfdi(expected)} certificate={_format_lfdi(actual)}. "
                "Do not regenerate the certificate. Register the certificate-derived LFDI in Xcel Launchpad "
                "or restore the certificate that belongs to the registered LFDI."
            )
        LOGGER.info("LFDI validation: MATCH")
    else:
        LOGGER.warning(
            "No expected_lfdi configured. The certificate identity will be used, but Launchpad registration "
            "cannot be cross-checked locally."
        )

    if info.days_remaining <= 90:
        LOGGER.warning(
            "Certificate expires within 90 days. Generate and provision a replacement before expiration."
        )

    return actual


def run_once(
    options: dict,
    profile: MeterProfile | None = None,
) -> tuple[MeterProfile, MeterSnapshot]:
    meter_ip = str(options.get("meter_ip") or "").strip()
    if not meter_ip:
        raise RuntimeError("meter_ip is required")

    meter_port = int(options.get("meter_port", 8081))
    timeout = float(options.get("timeout", 8))
    source = str(options.get("identity_source", "auto"))
    expected_lfdi = str(options.get("expected_lfdi") or "").strip() or None
    legacy_slug = str(options.get("legacy_addon_slug") or "").strip() or None

    LOGGER.info("============================================================")
    LOGGER.info("Xcel Meter HA diagnostic run")
    LOGGER.info("Meter endpoint: %s:%s", meter_ip, meter_port)

    location = find_identity(source, legacy_addon_slug=legacy_slug)
    validate_identity(location, expected_lfdi)

    client = Ieee20305Client(
        meter_ip,
        meter_port,
        location.cert_path,
        location.key_path,
        timeout=timeout,
    )
    if profile is None:
        LOGGER.info(
            "Meter profile cache: MISS - discovering meter layout"
        )

        profile = discover_core_profile(client)

        LOGGER.info(
            "Meter profile cache: READY - %s core reading paths",
            len(profile.core_readings),
        )
    else:
        LOGGER.debug(
            "Meter profile cache: HIT - using cached reading paths"
        )

    snapshot = read_core_snapshot(
        client,
        meter_ip,
        meter_port,
        profile=profile,
    )

    LOGGER.info("TLS/IEEE 2030.5 connection: PASS")
    LOGGER.info("Itron agent version: %s", snapshot.agent_version.value)
    LOGGER.info("Meter software version: %s", snapshot.software_version or "unknown")
    LOGGER.info("Meter LFDI reported by /sdev/sdi: %s", snapshot.meter_lfdi or "not reported")
    LOGGER.info("UsagePoint: %s", snapshot.usage_point_href)
    LOGGER.info("Instantaneous power: %s W", snapshot.instantaneous_power_w)
    LOGGER.info("Energy delivered: %s Wh", snapshot.energy_delivered_wh)
    LOGGER.info("Energy received: %s Wh", snapshot.energy_received_wh)

    core_values = {
        "instantaneous_power": snapshot.instantaneous_power_w,
        "energy_delivered": snapshot.energy_delivered_wh,
        "energy_received": snapshot.energy_received_wh,
    }

    missing = [
        name
        for name, value in core_values.items()
        if value is None
    ]

    LOGGER.info(
        "Core readings available: %s/%s",
        len(core_values) - len(missing),
        len(core_values),
    )

    if missing:
        raise RuntimeError(
            "IEEE 2030.5 connection succeeded, but required core readings "
            f"were unavailable: {', '.join(missing)}"
        )

    observed_at = datetime.now(UTC).isoformat()

    LOGGER.info("Connection health: HEALTHY")
    LOGGER.info("Last successful read (UTC observation): %s", observed_at)
    LOGGER.info("RESULT: PASS")

    LOGGER.debug(
        "Normalized snapshot: %s",
        json.dumps(snapshot.to_dict(), sort_keys=True),
    )

    return profile, snapshot


def main() -> int:
    options = load_options()
    level_name = str(options.get("log_level", "INFO")).upper()
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    poll_interval = int(options.get("poll_interval", 60))
    poll_interval = max(poll_interval, 15)

    LOGGER.info("Xcel Meter HA Diagnostic v0.4.1 starting")
    LOGGER.info(
        "This build never modifies certificate files. "
        "MQTT publishing is controlled by mqtt_enabled."
    )

    profile: MeterProfile | None = None
    mqtt_publisher: MqttPublisher | None = None
    mqtt_enabled = bool(options.get("mqtt_enabled", False))

    LOGGER.info(
        "MQTT publishing: %s",
        "ENABLED" if mqtt_enabled else "DISABLED",
    )

    while True:
        try:
            profile, snapshot = run_once(
                options,
                profile,
            )
        except Exception as exc:  # noqa: BLE001 - top-level service diagnostics
            LOGGER.error("RESULT: FAIL - %s", exc)

            if profile is not None:
                LOGGER.warning(
                    "Meter profile cache cleared after failed poll; "
                    "meter layout will be rediscovered next cycle"
                )

            profile = None

            if mqtt_publisher is not None:
                try:
                    mqtt_publisher.publish_offline()
                except Exception as mqtt_exc:  # noqa: BLE001 - service boundary
                    LOGGER.warning(
                        "Unable to publish MQTT offline status: %s",
                        mqtt_exc,
                    )

        else:
            if mqtt_enabled:
                try:
                    if mqtt_publisher is None:
                        LOGGER.info(
                            "MQTT publisher: initializing from validated meter snapshot"
                        )

                        mqtt_publisher = MqttPublisher.from_snapshot(
                            snapshot
                        )
                        mqtt_publisher.connect()
                        mqtt_publisher.publish_discovery()

                    mqtt_publisher.publish_snapshot(snapshot)

                except Exception as exc:  # noqa: BLE001 - service boundary
                    LOGGER.error(
                        "MQTT publishing: FAIL - %s",
                        exc,
                    )

                    if mqtt_publisher is not None:
                        try:
                            mqtt_publisher.close()
                        except Exception as close_exc:  # noqa: BLE001
                            LOGGER.debug(
                                "MQTT cleanup after failure: %s",
                                close_exc,
                            )

                    mqtt_publisher = None

        time.sleep(poll_interval)


if __name__ == "__main__":
    raise SystemExit(main())
