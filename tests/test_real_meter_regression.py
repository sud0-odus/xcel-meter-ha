from xcel_meter.discovery import classify_reading_type, determine_agent_version
from xcel_meter.models import AgentVersion, ReadingKind, ReadingTypeInfo
from xcel_meter.reader import read_core_snapshot


class FakeClient:
    def __init__(self, responses):
        self.responses = responses

    def get_xml(self, path):
        return self.responses[path]


def test_missing_software_version_is_unknown():
    client = FakeClient(
        {
            "/sdev/sdi": """
                <DeviceInformation>
                    <lFDI>TEST-METER-LFDI</lFDI>
                </DeviceInformation>
            """
        }
    )

    version, software, lfdi = determine_agent_version(client)

    assert version == AgentVersion.UNKNOWN
    assert software is None
    assert lfdi == "TEST-METER-LFDI"


def test_real_meter_core_types_allow_omitted_phase():
    demand = ReadingTypeInfo(
        accumulation_behaviour=12,
        data_qualifier=0,
        flow_direction=1,
        kind=8,
        phase=None,
        uom=38,
        power_of_ten_multiplier=0,
    )

    delivered = ReadingTypeInfo(
        accumulation_behaviour=9,
        data_qualifier=0,
        flow_direction=1,
        kind=12,
        phase=None,
        uom=72,
        power_of_ten_multiplier=0,
    )

    received = ReadingTypeInfo(
        accumulation_behaviour=9,
        data_qualifier=0,
        flow_direction=19,
        kind=12,
        phase=None,
        uom=72,
        power_of_ten_multiplier=0,
    )

    assert (
        classify_reading_type(
            demand,
            "Instantaneous Demand",
            AgentVersion.UNKNOWN,
        )
        == ReadingKind.INSTANTANEOUS_DEMAND
    )

    assert (
        classify_reading_type(
            delivered,
            "Current Summation Delivered",
            AgentVersion.UNKNOWN,
        )
        == ReadingKind.CURRENT_SUMMATION_DELIVERED
    )

    assert (
        classify_reading_type(
            received,
            "Current Summation Received",
            AgentVersion.UNKNOWN,
        )
        == ReadingKind.CURRENT_SUMMATION_RECEIVED
    )


def test_real_meter_style_snapshot_reads_core_values():
    responses = {
        "/sdev/sdi": """
            <DeviceInformation>
                <lFDI>TEST-METER-LFDI</lFDI>
            </DeviceInformation>
        """,
        "/upt": """
            <UsagePointList>
                <UsagePoint href="/upt/1">
                    <status>1</status>
                    <serviceCategoryKind>0</serviceCategoryKind>
                    <MeterReadingListLink href="/upt/1/mr" all="3" />
                </UsagePoint>
            </UsagePointList>
        """,
        "/upt/1/mr?l=3": """
            <MeterReadingList all="3" results="3">
                <MeterReading href="/upt/1/mr/3">
                    <description>Current Summation Delivered</description>
                    <ReadingLink href="/upt/1/mr/3/r" />
                    <ReadingTypeLink href="/rt/3" />
                </MeterReading>
                <MeterReading href="/upt/1/mr/2">
                    <description>Current Summation Received</description>
                    <ReadingLink href="/upt/1/mr/2/r" />
                    <ReadingTypeLink href="/rt/2" />
                </MeterReading>
                <MeterReading href="/upt/1/mr/1">
                    <description>Instantaneous Demand</description>
                    <ReadingLink href="/upt/1/mr/1/r" />
                    <ReadingTypeLink href="/rt/1" />
                </MeterReading>
            </MeterReadingList>
        """,
        "/rt/3": """
            <ReadingType>
                <accumulationBehaviour>9</accumulationBehaviour>
                <dataQualifier>0</dataQualifier>
                <flowDirection>1</flowDirection>
                <kind>12</kind>
                <uom>72</uom>
                <powerOfTenMultiplier>0</powerOfTenMultiplier>
            </ReadingType>
        """,
        "/rt/2": """
            <ReadingType>
                <accumulationBehaviour>9</accumulationBehaviour>
                <dataQualifier>0</dataQualifier>
                <flowDirection>19</flowDirection>
                <kind>12</kind>
                <uom>72</uom>
                <powerOfTenMultiplier>0</powerOfTenMultiplier>
            </ReadingType>
        """,
        "/rt/1": """
            <ReadingType>
                <accumulationBehaviour>12</accumulationBehaviour>
                <dataQualifier>0</dataQualifier>
                <flowDirection>1</flowDirection>
                <kind>8</kind>
                <uom>38</uom>
                <powerOfTenMultiplier>0</powerOfTenMultiplier>
            </ReadingType>
        """,
        "/upt/1/mr/3/r": "<Reading><value>40808961</value></Reading>",
        "/upt/1/mr/2/r": "<Reading><value>1250</value></Reading>",
        "/upt/1/mr/1/r": """
            <Reading>
                <timePeriod>
                    <start>1790557488</start>
                    <duration>1</duration>
                </timePeriod>
                <value>875</value>
            </Reading>
        """,
    }

    snapshot = read_core_snapshot(
        FakeClient(responses),
        "192.0.2.1",
        8081,
    )

    assert snapshot.agent_version == AgentVersion.UNKNOWN
    assert snapshot.software_version is None
    assert snapshot.instantaneous_power_w == 875
    assert snapshot.energy_delivered_wh == 40808961
    assert snapshot.energy_received_wh == 1250
    assert len(snapshot.readings) == 3

    power = next(
        item
        for item in snapshot.readings
        if item.kind == ReadingKind.INSTANTANEOUS_DEMAND
    )

    assert power.sample_start_epoch == 1790557488
    assert power.sample_duration_seconds == 1
