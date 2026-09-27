from xcel_meter.models import AgentVersion, MeterSnapshot
from xcel_meter.mqtt_discovery import (
    build_device_definition,
    build_state_payload,
    meter_identifier,
)


def _snapshot() -> MeterSnapshot:
    return MeterSnapshot(
        host="192.0.2.10",
        port=8081,
        agent_version=AgentVersion.UNKNOWN,
        software_version=None,
        usage_point_href="/upt/1",
        meter_reading_list_href="/upt/1/mr",
        meter_lfdi=(
            "5BA70BD0DBA11778EA0773AAAB7FF2A95AA7D00F"
        ),
        instantaneous_power_w=1863.0,
        energy_delivered_wh=40817686.0,
        energy_received_wh=0.0,
        readings=(),
    )


def test_meter_identifier_prefers_meter_lfdi():
    snapshot = _snapshot()

    assert meter_identifier(snapshot) == (
        "5ba70bd0dba11778ea0773aaab7ff2a95aa7d00f"
    )


def test_device_discovery_has_three_core_components():
    definition = build_device_definition(
        _snapshot()
    )

    payload = definition.payload

    assert definition.discovery_topic.startswith(
        "homeassistant/device/xcel_meter_"
    )

    assert payload["device"]["manufacturer"] == "Itron"
    assert payload["origin"]["name"] == "xcel-meter-ha"

    components = payload["components"]

    assert set(components) == {
        "instantaneous_power",
        "energy_delivered",
        "energy_received",
    }


def test_power_sensor_configuration():
    component = build_device_definition(
        _snapshot()
    ).payload["components"]["instantaneous_power"]

    assert component["platform"] == "sensor"
    assert component["device_class"] == "power"
    assert component["state_class"] == "measurement"
    assert component["unit_of_measurement"] == "W"
    assert component["unique_id"]


def test_delivered_energy_sensor_configuration():
    component = build_device_definition(
        _snapshot()
    ).payload["components"]["energy_delivered"]

    assert component["platform"] == "sensor"
    assert component["device_class"] == "energy"
    assert component["state_class"] == "total_increasing"
    assert component["unit_of_measurement"] == "Wh"
    assert component["unique_id"]


def test_received_energy_sensor_configuration():
    component = build_device_definition(
        _snapshot()
    ).payload["components"]["energy_received"]

    assert component["platform"] == "sensor"
    assert component["device_class"] == "energy"
    assert component["state_class"] == "total_increasing"
    assert component["unit_of_measurement"] == "Wh"
    assert component["unique_id"]


def test_state_payload_preserves_zero_export():
    payload = build_state_payload(
        _snapshot()
    )

    assert payload == {
        "instantaneous_power_w": 1863.0,
        "energy_delivered_wh": 40817686.0,
        "energy_received_wh": 0.0,
    }
