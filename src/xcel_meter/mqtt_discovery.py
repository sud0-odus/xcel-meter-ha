from __future__ import annotations

import re
from dataclasses import dataclass

from .models import MeterSnapshot


APP_NAME = "xcel-meter-ha"
APP_VERSION = "0.4.1"
SUPPORT_URL = "https://github.com/sud0-odus/xcel-meter-ha"


@dataclass(frozen=True)
class MqttDeviceDefinition:
    discovery_topic: str
    state_topic: str
    availability_topic: str
    payload: dict


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


def build_device_definition(
    snapshot: MeterSnapshot,
    discovery_prefix: str = "homeassistant",
) -> MqttDeviceDefinition:
    identifier = meter_identifier(snapshot)

    device_id = f"xcel_meter_{identifier}"
    base_topic = f"xcel-meter-ha/{identifier}"

    state_topic = f"{base_topic}/state"
    availability_topic = f"{base_topic}/availability"

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
        "availability_topic": availability_topic,
        "payload_available": "online",
        "payload_not_available": "offline",
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
            "energy_received": {
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
            },
            "last_successful_read": {
                "platform": "sensor",
                "name": "Last Successful Read",
                "unique_id": (
                    f"{device_id}_last_successful_read"
                ),
                "device_class": "timestamp",
                "entity_category": "diagnostic",
                "value_template": (
                    "{{ value_json.last_successful_read }}"
                ),
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

    return MqttDeviceDefinition(
        discovery_topic=discovery_topic,
        state_topic=state_topic,
        availability_topic=availability_topic,
        payload=payload,
    )


def build_state_payload(
    snapshot: MeterSnapshot,
    last_successful_read: str | None = None,
) -> dict[str, str | float | None]:
    return {
        "instantaneous_power_w": (
            snapshot.instantaneous_power_w
        ),
        "energy_delivered_wh": (
            snapshot.energy_delivered_wh
        ),
        "energy_received_wh": (
            snapshot.energy_received_wh
        ),
        "last_successful_read": last_successful_read,
        "meter_lfdi": snapshot.meter_lfdi or "unknown",
        "agent_version": snapshot.agent_version.value,
        "meter_software_version": (
            snapshot.software_version or "unknown"
        ),
    }
