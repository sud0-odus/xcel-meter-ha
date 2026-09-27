from xcel_meter import reader
from xcel_meter.models import (
    AgentVersion,
    MeterReadingDescriptor,
    ReadingKind,
    ReadingTypeInfo,
)


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_xml(self, path):
        self.calls.append(path)
        return self.responses[path]


def _descriptor(
    kind: ReadingKind,
    description: str,
    reading_link: str,
    reading_type_link: str,
) -> MeterReadingDescriptor:
    return MeterReadingDescriptor(
        href=None,
        description=description,
        mrid=None,
        reading_link=reading_link,
        reading_type_link=reading_type_link,
        reading_set_list_link=None,
        reading_set_all=None,
        kind=kind,
    )


def test_cached_profile_skips_rediscovery(monkeypatch):
    calls = {
        "agent": 0,
        "usage": 0,
        "discovery": 0,
    }

    demand_info = ReadingTypeInfo(
        accumulation_behaviour=12,
        data_qualifier=0,
        flow_direction=1,
        kind=8,
        phase=None,
        uom=38,
        power_of_ten_multiplier=0,
    )

    delivered_info = ReadingTypeInfo(
        accumulation_behaviour=9,
        data_qualifier=0,
        flow_direction=1,
        kind=12,
        phase=None,
        uom=72,
        power_of_ten_multiplier=0,
    )

    received_info = ReadingTypeInfo(
        accumulation_behaviour=9,
        data_qualifier=0,
        flow_direction=19,
        kind=12,
        phase=None,
        uom=72,
        power_of_ten_multiplier=0,
    )

    descriptors = [
        (
            _descriptor(
                ReadingKind.INSTANTANEOUS_DEMAND,
                "Instantaneous Demand",
                "/r/1",
                "/rt/1",
            ),
            demand_info,
        ),
        (
            _descriptor(
                ReadingKind.CURRENT_SUMMATION_DELIVERED,
                "Current Summation Delivered",
                "/r/3",
                "/rt/3",
            ),
            delivered_info,
        ),
        (
            _descriptor(
                ReadingKind.CURRENT_SUMMATION_RECEIVED,
                "Current Summation Received",
                "/r/2",
                "/rt/2",
            ),
            received_info,
        ),
    ]

    def fake_agent(client):
        calls["agent"] += 1
        return AgentVersion.UNKNOWN, None, "TEST-LFDI"

    def fake_usage(client):
        calls["usage"] += 1
        return "/upt/1", "/upt/1/mr", 22

    def fake_discovery(client, href, count, agent_version):
        calls["discovery"] += 1
        return descriptors

    monkeypatch.setattr(
        reader,
        "determine_agent_version",
        fake_agent,
    )
    monkeypatch.setattr(
        reader,
        "find_electricity_usage_point",
        fake_usage,
    )
    monkeypatch.setattr(
        reader,
        "discover_meter_readings",
        fake_discovery,
    )

    client = FakeClient(
        {
            "/r/1": "<Reading><value>875</value></Reading>",
            "/r/3": "<Reading><value>40808961</value></Reading>",
            "/r/2": "<Reading><value>0</value></Reading>",
        }
    )

    profile = reader.discover_core_profile(client)

    first = reader.read_core_snapshot(
        client,
        "192.0.2.1",
        8081,
        profile=profile,
    )

    second = reader.read_core_snapshot(
        client,
        "192.0.2.1",
        8081,
        profile=profile,
    )

    assert calls == {
        "agent": 1,
        "usage": 1,
        "discovery": 1,
    }

    assert client.calls == [
        "/r/1",
        "/r/3",
        "/r/2",
        "/r/1",
        "/r/3",
        "/r/2",
    ]

    assert first.instantaneous_power_w == 875
    assert first.energy_delivered_wh == 40808961
    assert first.energy_received_wh == 0

    assert second.instantaneous_power_w == 875
    assert second.energy_delivered_wh == 40808961
    assert second.energy_received_wh == 0
