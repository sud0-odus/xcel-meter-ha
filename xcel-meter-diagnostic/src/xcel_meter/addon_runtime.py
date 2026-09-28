from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from .certificate import CertificateInfo, inspect_client_identity
from .freshness import (
    DEFAULT_MAX_SAMPLE_AGE_SECONDS,
    instantaneous_power_freshness,
)
from .http import Ieee20305Client, MeterHttpError
from .identity import normalize_lfdi
from .identity_lifecycle import (
    IdentityLocation,
    find_legacy_identity,
    find_own_identity,
    prepare_identity,
    read_identity_manifest,
    write_identity_manifest,
)
from .models import MeterSnapshot
from .mqtt_runtime import MqttPublisher, MqttUnavailableError
from .reader import MeterProfile, discover_core_profile, read_core_snapshot
from .version import APP_VERSION

LOGGER = logging.getLogger("xcel_meter.addon")


class OnboardingPendingError(RuntimeError):
    """Expected onboarding state that is not a meter-health failure."""


def find_identity(
    source: str,
    own_config_root: Path = Path("/config"),
    all_addon_configs_root: Path = Path("/addon_configs"),
    legacy_addon_slug: str | None = None,
) -> IdentityLocation:
    """Compatibility lookup helper; does not generate or migrate identities."""
    source = source.strip().lower()
    if source not in {"auto", "own", "legacy"}:
        raise ValueError(f"Unsupported identity_source {source!r}; use auto, own, or legacy")
    if source in {"auto", "own"}:
        own = find_own_identity(own_config_root)
        if own:
            return own
        if source == "own":
            raise FileNotFoundError("No certificate/key found in this app's config")
    if source in {"auto", "legacy"}:
        legacy = find_legacy_identity(all_addon_configs_root, legacy_addon_slug)
        if legacy:
            return legacy
        raise FileNotFoundError("No legacy Xcel iTron MQTT certificate/key found")
    raise RuntimeError("Identity discovery failed")


def load_options(path: Path = Path("/data/options.json")) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_lfdi(value: str) -> str:
    normalized = normalize_lfdi(value)
    return "-".join(normalized[i : i + 5] for i in range(0, len(normalized), 5))


def validate_identity(
    location: IdentityLocation,
    expected_lfdi: str | None,
) -> CertificateInfo:
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
    LOGGER.info("Digital-signature key usage: %s", "OK" if info.digital_signature_present else "FAIL")
    LOGGER.info("Certificate profile critical extensions: %s", "OK" if info.key_usage_critical and info.ieee_policy_critical else "FAIL")
    LOGGER.info("Certificate self-signed: %s", "OK" if info.self_signed else "FAIL")

    if info.is_expired:
        raise RuntimeError("Client certificate is expired")
    if not info.key_matches:
        raise RuntimeError("Client certificate and private key do not match")
    if not info.ieee_policy_present:
        raise RuntimeError("Required IEEE 2030.5 certificate policy is missing")
    if not info.digital_signature_present or not info.key_usage_critical:
        raise RuntimeError("Certificate requires critical KeyUsage containing digitalSignature")
    if not info.ieee_policy_critical:
        raise RuntimeError("IEEE 2030.5 certificate policy extension must be critical")
    if not info.self_signed:
        raise RuntimeError("IEEE 2030.5 client certificate must be self-signed")
    if info.signature_hash.lower() != "sha256":
        raise RuntimeError(f"Unsupported certificate signature hash {info.signature_hash}; expected SHA-256")
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

    return info


def _should_invalidate_meter_profile(
    exc: BaseException,
) -> bool:
    return (
        isinstance(exc, MeterHttpError)
        and exc.invalidates_profile
    )


def run_once(
    options: dict,
    profile: MeterProfile | None = None,
) -> tuple[MeterProfile, MeterSnapshot, CertificateInfo]:
    meter_ip = str(options.get("meter_ip") or "").strip()
    meter_port = int(options.get("meter_port", 8081))
    timeout = float(options.get("timeout", 8))
    source = str(options.get("identity_source", "auto"))
    expected_lfdi = str(options.get("expected_lfdi") or "").strip() or None
    legacy_slug = str(options.get("legacy_addon_slug") or "").strip() or None
    energy_export_enabled = bool(
        options.get("energy_export_enabled", False)
    )

    LOGGER.info("============================================================")
    LOGGER.info("Xcel Meter HA diagnostic run")
    if meter_ip:
        LOGGER.info("Meter endpoint: %s:%s", meter_ip, meter_port)
    else:
        LOGGER.info("Meter endpoint: not configured yet")

    preparation = prepare_identity(
        source,
        legacy_addon_slug=legacy_slug,
        migrate_legacy=bool(options.get("migrate_legacy_identity", True)),
        generate_if_missing=bool(options.get("generate_identity_if_missing", True)),
    )
    location = preparation.location
    identity_info = validate_identity(location, expected_lfdi)
    write_identity_manifest(preparation)

    if preparation.action == "generated":
        LOGGER.warning(
            "NEW app-owned IEEE 2030.5 identity generated. Register this LFDI in Xcel Energy "
            "Launchpad and keep this identity; the app will retry while provisioning completes: %s",
            _format_lfdi(identity_info.lfdi),
        )
    elif preparation.action == "migrated":
        LOGGER.info(
            "Legacy identity safely migrated into app-owned storage with unchanged LFDI: %s",
            _format_lfdi(identity_info.lfdi),
        )

    if not meter_ip:
        raise OnboardingPendingError(
            "Client identity is ready. Register/copy the displayed LFDI as needed, then configure "
            "meter_ip to begin local meter validation. The identity will be reused unchanged."
        )

    client = Ieee20305Client(
        meter_ip,
        meter_port,
        location.cert_path,
        location.key_path,
        timeout=timeout,
    )
    try:
        if profile is None:
            LOGGER.info(
                "Meter profile cache: MISS - discovering meter layout"
            )

            profile = discover_core_profile(
                client,
                include_received=energy_export_enabled,
            )

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
    except MeterHttpError as exc:
        manifest = read_identity_manifest()
        if (
            exc.kind == "client_auth"
            and manifest.get("identity_origin") == "generated"
            and not bool(manifest.get("meter_authenticated", False))
        ):
            raise OnboardingPendingError(
                "The meter rejected this newly generated client identity during TLS. "
                "Because this LFDI has never authenticated successfully, Launchpad registration/"
                "provisioning may still be pending. Keep the same identity and retry; do not "
                "regenerate it. If provisioning should be complete, verify the registered LFDI."
            ) from exc
        raise

    LOGGER.info("TLS/IEEE 2030.5 connection: PASS")
    LOGGER.info("Itron agent version: %s", snapshot.agent_version.value)
    LOGGER.info("Meter software version: %s", snapshot.software_version or "unknown")
    LOGGER.info("Meter LFDI reported by /sdev/sdi: %s", snapshot.meter_lfdi or "not reported")
    LOGGER.info("UsagePoint: %s", snapshot.usage_point_href)
    LOGGER.info("Instantaneous power: %s W", snapshot.instantaneous_power_w)
    LOGGER.info("Energy delivered: %s Wh", snapshot.energy_delivered_wh)

    if energy_export_enabled:
        LOGGER.info(
            "Energy received: %s Wh",
            snapshot.energy_received_wh,
        )
    else:
        LOGGER.info(
            "Energy received/export monitoring: DISABLED"
        )

    core_values = {
        "instantaneous_power": snapshot.instantaneous_power_w,
        "energy_delivered": snapshot.energy_delivered_wh,
    }

    if energy_export_enabled:
        core_values["energy_received"] = (
            snapshot.energy_received_wh
        )

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

    observed_at = datetime.now(UTC)
    freshness = instantaneous_power_freshness(
        snapshot,
        observed_at,
    )

    if freshness is None:
        LOGGER.info(
            "Instantaneous sample freshness: unavailable "
            "(meter did not report timePeriod.start)"
        )
    else:
        sample_start = datetime.fromtimestamp(
            freshness.sample_start_epoch,
            UTC,
        ).isoformat()

        duration_text = (
            f"{freshness.sample_duration_seconds}s"
            if freshness.sample_duration_seconds is not None
            else "unknown"
        )

        LOGGER.info(
            "Instantaneous sample: start=%s duration=%s age=%.3fs",
            sample_start,
            duration_text,
            freshness.age_seconds,
        )

        if freshness.stale:
            raise RuntimeError(
                "Instantaneous Demand sample is stale: "
                f"age={freshness.age_seconds:.1f}s exceeds "
                f"{DEFAULT_MAX_SAMPLE_AGE_SECONDS:.0f}s; "
                "meter-reported power will not be published as current"
            )

    observed_at_text = observed_at.isoformat()

    LOGGER.info("Connection health: HEALTHY")
    LOGGER.info(
        "Last successful read (UTC observation): %s",
        observed_at_text,
    )
    LOGGER.info("RESULT: PASS")
    write_identity_manifest(preparation, meter_authenticated=True)

    LOGGER.debug(
        "Normalized snapshot: %s",
        json.dumps(snapshot.to_dict(), sort_keys=True),
    )

    return profile, snapshot, identity_info


def main() -> int:
    options = load_options()
    level_name = str(options.get("log_level", "INFO")).upper()
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    poll_interval = int(options.get("poll_interval", 60))
    poll_interval = max(poll_interval, 15)

    LOGGER.info("Xcel Meter HA v%s starting", APP_VERSION)
    LOGGER.info(
        "Native identity lifecycle enabled: reuse app identity, safely migrate legacy identity, "
        "or generate once when no identity exists. MQTT is controlled by mqtt_enabled."
    )

    profile: MeterProfile | None = None
    mqtt_publisher: MqttPublisher | None = None
    mqtt_enabled = bool(options.get("mqtt_enabled", False))
    energy_export_enabled = bool(
        options.get("energy_export_enabled", False)
    )

    LOGGER.info(
        "Energy export monitoring: %s",
        "ENABLED" if energy_export_enabled else "DISABLED",
    )

    LOGGER.info(
        "MQTT publishing: %s",
        "ENABLED" if mqtt_enabled else "DISABLED",
    )

    while True:
        try:
            profile, snapshot, identity_info = run_once(
                options,
                profile,
            )
        except OnboardingPendingError as exc:
            LOGGER.warning("Onboarding pending: %s", exc)
        except Exception as exc:  # noqa: BLE001 - top-level service diagnostics
            LOGGER.error("Meter poll failed; retrying on the next poll: %s", exc)

            if profile is not None:
                if _should_invalidate_meter_profile(exc):
                    if isinstance(exc, MeterHttpError):
                        LOGGER.warning(
                            "Meter profile cache cleared because "
                            "cached resource returned HTTP %s: %s",
                            exc.status,
                            exc.path or "<unknown>",
                        )

                    profile = None
                else:
                    LOGGER.warning(
                        "Meter profile cache retained after failed poll; "
                        "failure did not indicate a meter layout change"
                    )

            if mqtt_publisher is not None:
                try:
                    mqtt_publisher.publish_meter_problem()
                except Exception as mqtt_exc:  # noqa: BLE001 - service boundary
                    LOGGER.warning(
                        "Unable to publish MQTT meter problem status: %s",
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
                            snapshot,
                            include_received=energy_export_enabled,
                        )
                        mqtt_publisher.connect()
                        mqtt_publisher.publish_discovery()

                    mqtt_publisher.publish_snapshot(
                        snapshot,
                        certificate_info=identity_info,
                    )

                except Exception as exc:  # noqa: BLE001 - service boundary
                    if isinstance(exc, MqttUnavailableError):
                        LOGGER.warning(
                            "MQTT unavailable; meter polling will continue "
                            "and MQTT will retry on the next poll: %s",
                            exc,
                        )
                    else:
                        LOGGER.error(
                            "MQTT publishing failed unexpectedly: %s",
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
