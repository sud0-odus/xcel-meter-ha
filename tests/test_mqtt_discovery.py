from datetime import UTC, datetime
from types import SimpleNamespace

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
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        ),
        instantaneous_power_w=1863.0,
        energy_delivered_wh=40817686.0,
        energy_received_wh=0.0,
        readings=(),
    )


def _certificate_info():
    return SimpleNamespace(
        lfdi=(
            "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
        ),
        not_after=datetime(
            2029,
            9,
            25,
            1,
            34,
            47,
            tzinfo=UTC,
        ),
        days_remaining=1093,
    )


def test_meter_identifier_prefers_meter_lfdi():
    snapshot = _snapshot()

    assert meter_identifier(snapshot) == (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )


def test_device_discovery_has_expected_components_with_export():
    definition = build_device_definition(
        _snapshot(),
        include_received=True,
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
        "meter_health",
        "meter_lfdi",
        "agent_version",
        "meter_software_version",
        "client_lfdi",
        "certificate_expiration",
        "certificate_days_remaining",
    }

    assert len(components) == 10


def test_device_discovery_has_expected_components_without_export():
    definition = build_device_definition(
        _snapshot(),
        include_received=False,
    )

    components = definition.payload["components"]

    assert set(components) == {
        "instantaneous_power",
        "energy_delivered",
        "meter_health",
        "meter_lfdi",
        "agent_version",
        "meter_software_version",
        "client_lfdi",
        "certificate_expiration",
        "certificate_days_remaining",
    }

    assert len(components) == 9
    assert definition.removed_components == (
        "last_successful_read",
        "energy_received",
    )


def test_power_sensor_configuration():
    component = build_device_definition(
        _snapshot()
    ).payload["components"]["instantaneous_power"]

    assert component["platform"] == "sensor"
    assert component["device_class"] == "power"
    assert component["state_class"] == "measurement"
    assert component["unit_of_measurement"] == "W"
    assert component["unique_id"]


def test_energy_sensor_configuration():
    components = build_device_definition(
        _snapshot(),
        include_received=True,
    ).payload["components"]

    for name in (
        "energy_delivered",
        "energy_received",
    ):
        component = components[name]

        assert component["platform"] == "sensor"
        assert component["device_class"] == "energy"
        assert component["state_class"] == "total_increasing"
        assert component["unit_of_measurement"] == "Wh"
        assert component["unique_id"]


def test_diagnostic_sensor_configuration():
    components = build_device_definition(
        _snapshot()
    ).payload["components"]

    for name in (
        "meter_health",
        "meter_lfdi",
        "agent_version",
        "meter_software_version",
        "client_lfdi",
        "certificate_expiration",
        "certificate_days_remaining",
    ):
        assert (
            components[name]["entity_category"]
            == "diagnostic"
        )

    health = components["meter_health"]

    assert health["state_topic"].endswith("/health")
    assert health["entity_category"] == "diagnostic"

    assert (
        components["certificate_expiration"]["device_class"]
        == "timestamp"
    )

    assert (
        components["certificate_days_remaining"][
            "unit_of_measurement"
        ]
        == "d"
    )


def test_state_payload_includes_certificate_diagnostics():
    payload = build_state_payload(
        _snapshot(),
        include_received=True,
        certificate_info=_certificate_info(),
    )

    assert payload == {
        "instantaneous_power_w": 1863.0,
        "energy_delivered_wh": 40817686.0,
        "energy_received_wh": 0.0,
        "meter_lfdi": (
            "AAAAA-AAAAA-AAAAA-AAAAA-AAAAA-AAAAA-AAAAA-AAAAA"
        ),
        "agent_version": "unknown",
        "meter_software_version": "unknown",
        "client_lfdi": (
            "BBBBB-BBBBB-BBBBB-BBBBB-BBBBB-BBBBB-BBBBB-BBBBB"
        ),
        "certificate_expiration": (
            "2029-09-25T01:34:47+00:00"
        ),
        "certificate_days_remaining": 1093,
    }


def test_state_payload_without_export_omits_received_value():
    payload = build_state_payload(
        _snapshot(),
        include_received=False,
        certificate_info=_certificate_info(),
    )

    assert "energy_received_wh" not in payload

    assert payload["instantaneous_power_w"] == 1863.0
    assert payload["energy_delivered_wh"] == 40817686.0
    assert payload["certificate_days_remaining"] == 1093


def test_state_payload_without_certificate_info_is_supported():
    payload = build_state_payload(
        _snapshot(),
        include_received=False,
        certificate_info=None,
    )

    assert "client_lfdi" not in payload
    assert "certificate_expiration" not in payload
    assert "certificate_days_remaining" not in payload


def test_measurements_require_app_and_meter_availability():
    definition = build_device_definition(
        _snapshot(),
        include_received=False,
    )

    components = definition.payload["components"]

    power = components["instantaneous_power"]
    health = components["meter_health"]

    assert power["availability_mode"] == "all"
    assert power["availability"] == [
        {"topic": definition.availability_topic},
        {"topic": definition.meter_availability_topic},
    ]

    assert health["availability"] == [
        {"topic": definition.availability_topic},
    ]

    assert health["state_topic"] == definition.health_topic


def test_export_enabled_still_cleans_old_timestamp_entity():
    definition = build_device_definition(
        _snapshot(),
        include_received=True,
    )

    assert definition.removed_components == (
        "last_successful_read",
    )
