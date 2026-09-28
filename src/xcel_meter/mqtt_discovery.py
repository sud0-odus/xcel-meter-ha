from __future__ import annotations

import re
from dataclasses import dataclass

from .certificate import CertificateInfo
from .identity import normalize_lfdi
from .models import MeterSnapshot
from .version import APP_VERSION


APP_NAME = "xcel-meter-ha"
SUPPORT_URL = "https://github.com/sud0-odus/xcel-meter-ha"


@dataclass(frozen=True)
class MqttDeviceDefinition:
    discovery_topic: str
    state_topic: str
    availability_topic: str
    meter_availability_topic: str
    health_topic: str
    payload: dict
    removed_components: tuple[str, ...] = ()


def _safe_identifier(value: str) -> str:
    cleaned = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        value.strip(),
    )
    return cleaned.strip("_").lower()


def meter_identifier(snapshot: MeterSnapshot) -> str:
    if snapshot.meter_lfdi:
        return _safe_identifier(snapshot.meter_lfdi)

    return _safe_identifier(
        f"{snapshot.host}_{snapshot.port}"
    )


def _format_lfdi(value: str | None) -> str:
    """Format an LFDI for human-readable display without changing identity."""
    if not value:
        return "unknown"

    normalized = normalize_lfdi(value)

    if not normalized:
        return "unknown"

    return "-".join(
        normalized[i : i + 5]
        for i in range(0, len(normalized), 5)
    )


def build_device_definition(
    snapshot: MeterSnapshot,
    discovery_prefix: str = "homeassistant",
    include_received: bool = True,
) -> MqttDeviceDefinition:
    identifier = meter_identifier(snapshot)

    device_id = f"xcel_meter_{identifier}"
    base_topic = f"xcel-meter-ha/{identifier}"

    state_topic = f"{base_topic}/state"
    availability_topic = f"{base_topic}/availability"
    meter_availability_topic = (
        f"{base_topic}/availability/meter"
    )
    health_topic = f"{base_topic}/health"

    discovery_topic = (
        f"{discovery_prefix}/device/"
        f"{device_id}/config"
    )

    payload = {
        "device": {
            "identifiers": [device_id],
            "name": "Xcel Energy Smart Meter",
            "manufacturer": "Itron",
            "model": "IEEE 2030.5 Smart Meter",
        },
        "origin": {
            "name": APP_NAME,
            "sw_version": APP_VERSION,
            "support_url": SUPPORT_URL,
        },
        "state_topic": state_topic,
        "components": {
            "instantaneous_power": {
                "platform": "sensor",
                "name": "Instantaneous Power",
                "unique_id": (
                    f"{device_id}_instantaneous_power"
                ),
                "device_class": "power",
                "state_class": "measurement",
                "unit_of_measurement": "W",
                "value_template": (
                    "{{ value_json.instantaneous_power_w }}"
                ),
            },
            "energy_delivered": {
                "platform": "sensor",
                "name": "Energy Delivered",
                "unique_id": (
                    f"{device_id}_energy_delivered"
                ),
                "device_class": "energy",
                "state_class": "total_increasing",
                "unit_of_measurement": "Wh",
                "value_template": (
                    "{{ value_json.energy_delivered_wh }}"
                ),
            },
            "meter_health": {
                "platform": "sensor",
                "name": "Meter Health",
                "unique_id": f"{device_id}_meter_health",
                "entity_category": "diagnostic",
                "state_topic": health_topic,
            },
            "meter_lfdi": {
                "platform": "sensor",
                "name": "Meter LFDI",
                "unique_id": (
                    f"{device_id}_meter_lfdi"
                ),
                "entity_category": "diagnostic",
                "value_template": (
                    "{{ value_json.meter_lfdi }}"
                ),
            },
            "agent_version": {
                "platform": "sensor",
                "name": "Itron Agent Version",
                "unique_id": (
                    f"{device_id}_agent_version"
                ),
                "entity_category": "diagnostic",
                "value_template": (
                    "{{ value_json.agent_version }}"
                ),
            },
            "meter_software_version": {
                "platform": "sensor",
                "name": "Meter Software Version",
                "unique_id": (
                    f"{device_id}_meter_software_version"
                ),
                "entity_category": "diagnostic",
                "value_template": (
                    "{{ value_json.meter_software_version }}"
                ),
            },
        },
    }

    payload["components"].update(
        {
            "client_lfdi": {
                "platform": "sensor",
                "name": "Client LFDI",
                "unique_id": f"{device_id}_client_lfdi",
                "entity_category": "diagnostic",
                "value_template": (
                    "{{ value_json.client_lfdi }}"
                ),
            },
            "certificate_expiration": {
                "platform": "sensor",
                "name": "Certificate Expiration",
                "unique_id": (
                    f"{device_id}_certificate_expiration"
                ),
                "device_class": "timestamp",
                "entity_category": "diagnostic",
                "value_template": (
                    "{{ value_json.certificate_expiration }}"
                ),
            },
            "certificate_days_remaining": {
                "platform": "sensor",
                "name": "Certificate Days Remaining",
                "unique_id": (
                    f"{device_id}_certificate_days_remaining"
                ),
                "unit_of_measurement": "d",
                "entity_category": "diagnostic",
                "value_template": (
                    "{{ value_json.certificate_days_remaining }}"
                ),
            },
        }
    )

    removed_components_list = [
        "last_successful_read",
    ]

    if include_received:
        payload["components"]["energy_received"] = {
            "platform": "sensor",
            "name": "Energy Received",
            "unique_id": (
                f"{device_id}_energy_received"
            ),
            "device_class": "energy",
            "state_class": "total_increasing",
            "unit_of_measurement": "Wh",
            "value_template": (
                "{{ value_json.energy_received_wh }}"
            ),
        }
    else:
        removed_components_list.append(
            "energy_received"
        )

    measurement_components = {
        "instantaneous_power",
        "energy_delivered",
        "energy_received",
    }

    for component_id, component in (
        payload["components"].items()
    ):
        if component_id in measurement_components:
            component["availability"] = [
                {"topic": availability_topic},
                {"topic": meter_availability_topic},
            ]
            component["availability_mode"] = "all"
        else:
            component["availability"] = [
                {"topic": availability_topic},
            ]

    removed_components = tuple(
        removed_components_list
    )

    return MqttDeviceDefinition(
        discovery_topic=discovery_topic,
        state_topic=state_topic,
        availability_topic=availability_topic,
        meter_availability_topic=meter_availability_topic,
        health_topic=health_topic,
        payload=payload,
        removed_components=removed_components,
    )


def build_state_payload(
    snapshot: MeterSnapshot,
    include_received: bool = True,
    certificate_info: CertificateInfo | None = None,
) -> dict[str, str | float | int | None]:
    payload: dict[str, str | float | int | None] = {
        "instantaneous_power_w": (
            snapshot.instantaneous_power_w
        ),
        "energy_delivered_wh": (
            snapshot.energy_delivered_wh
        ),
        "meter_lfdi": _format_lfdi(snapshot.meter_lfdi),
        "agent_version": snapshot.agent_version.value,
        "meter_software_version": (
            snapshot.software_version or "unknown"
        ),
    }

    if certificate_info is not None:
        payload["client_lfdi"] = _format_lfdi(
            certificate_info.lfdi
        )
        payload["certificate_expiration"] = (
            certificate_info.not_after.isoformat()
        )
        payload["certificate_days_remaining"] = (
            certificate_info.days_remaining
        )

    if include_received:
        payload["energy_received_wh"] = (
            snapshot.energy_received_wh
        )

    return payload
