from xcel_meter.discovery import (
    classify_reading_type,
    determine_agent_version,
    find_electricity_usage_point,
    parse_meter_reading_list,
    parse_reading_type,
)
from xcel_meter.models import AgentVersion, ReadingKind


class FakeClient:
    def __init__(self, responses):
        self.responses = responses

    def get_xml(self, path: str) -> str:
        return self.responses[path]


DEVICE_V3 = """<DeviceInformation xmlns="urn:ieee:std:2030.5:ns"><lFDI>ABCDEF</lFDI><softwareVersion>3.2.50</softwareVersion></DeviceInformation>"""
USAGE = """<UsagePointList xmlns="urn:ieee:std:2030.5:ns" href="/upt" all="1" results="1"><UsagePoint href="/upt/1"><serviceCategoryKind>0</serviceCategoryKind><status>1</status><MeterReadingListLink href="/upt/1/mr" all="3"/></UsagePoint></UsagePointList>"""
LIST = """<MeterReadingList xmlns="urn:ieee:std:2030.5:ns" href="/upt/1/mr" all="1" results="1"><MeterReading href="/upt/1/mr/1"><mRID>1</mRID><description>Instantaneous Demand</description><ReadingLink href="/upt/1/mr/1/r"/><ReadingTypeLink href="/rt/1"/></MeterReading></MeterReadingList>"""
RT_V3_DEMAND = """<ReadingType xmlns="urn:ieee:std:2030.5:ns"><accumulationBehaviour>12</accumulationBehaviour><dataQualifier>0</dataQualifier><flowDirection>1</flowDirection><kind>8</kind><phase>0</phase><powerOfTenMultiplier>0</powerOfTenMultiplier><uom>38</uom></ReadingType>"""
RT_V3_SUM_DEL = """<ReadingType xmlns="urn:ieee:std:2030.5:ns"><accumulationBehaviour>9</accumulationBehaviour><dataQualifier>0</dataQualifier><flowDirection>1</flowDirection><kind>12</kind><phase>0</phase><powerOfTenMultiplier>0</powerOfTenMultiplier><uom>72</uom></ReadingType>"""
RT_V2_SUM_REC = """<ReadingType xmlns="urn:ieee:std:2030.5:ns"><accumulationBehaviour>9</accumulationBehaviour><dataQualifier>2</dataQualifier><flowDirection>19</flowDirection><kind>12</kind><phase>0</phase><powerOfTenMultiplier>0</powerOfTenMultiplier><uom>72</uom></ReadingType>"""


def test_agent_version_uses_device_information():
    version, software, lfdi = determine_agent_version(FakeClient({"/sdev/sdi": DEVICE_V3}))
    assert version == AgentVersion.V3
    assert software == "3.2.50"
    assert lfdi == "ABCDEF"


def test_find_electricity_usage_point():
    assert find_electricity_usage_point(FakeClient({"/upt": USAGE})) == (
        "/upt/1",
        "/upt/1/mr",
        3,
    )


def test_parse_meter_reading_list():
    reading = parse_meter_reading_list(LIST)[0]
    assert reading.description == "Instantaneous Demand"
    assert reading.reading_link == "/upt/1/mr/1/r"
    assert reading.reading_type_link == "/rt/1"


def test_classify_v3_and_v2_core_types():
    demand = parse_reading_type(RT_V3_DEMAND)
    summation = parse_reading_type(RT_V3_SUM_DEL)
    received_v2 = parse_reading_type(RT_V2_SUM_REC)
    assert classify_reading_type(demand, "Instantaneous Demand", AgentVersion.V3) == ReadingKind.INSTANTANEOUS_DEMAND
    assert classify_reading_type(summation, "Current Summation Delivered", AgentVersion.V3) == ReadingKind.CURRENT_SUMMATION_DELIVERED
    assert classify_reading_type(summation, "TOU Wh Delivered", AgentVersion.V3) == ReadingKind.TOU_WH_DELIVERED
    assert classify_reading_type(received_v2, "Current Summation Received", AgentVersion.V2) == ReadingKind.CURRENT_SUMMATION_RECEIVED


def test_agent_version_1_uses_shared_v1_v2_family():
    xml = """<DeviceInformation><lFDI>ABCDEF</lFDI><softwareVersion>1.9.0</softwareVersion></DeviceInformation>"""
    version, software, _ = determine_agent_version(FakeClient({"/sdev/sdi": xml}))
    assert version == AgentVersion.V1_V2
    assert software == "1.9.0"
