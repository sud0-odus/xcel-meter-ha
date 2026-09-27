from xcel_meter.models import AgentVersion
from xcel_meter.reader import read_core_snapshot


class FakeClient:
    def __init__(self, responses):
        self.responses = responses

    def get_xml(self, path: str) -> str:
        return self.responses[path]


def test_full_core_snapshot_v3():
    responses = {
        "/sdev/sdi": '<DeviceInformation xmlns="urn:ieee:std:2030.5:ns"><lFDI>METERLFDI</lFDI><softwareVersion>3.2.50</softwareVersion></DeviceInformation>',
        "/upt": '<UsagePointList xmlns="urn:ieee:std:2030.5:ns"><UsagePoint href="/upt/1"><serviceCategoryKind>0</serviceCategoryKind><status>1</status><MeterReadingListLink href="/upt/1/mr" all="3"/></UsagePoint></UsagePointList>',
        "/upt/1/mr?l=3": '<MeterReadingList xmlns="urn:ieee:std:2030.5:ns"><MeterReading href="/upt/1/mr/1"><description>Instantaneous Demand</description><ReadingLink href="/upt/1/mr/1/r"/><ReadingTypeLink href="/rt/1"/></MeterReading><MeterReading href="/upt/1/mr/2"><description>Current Summation Received</description><ReadingLink href="/upt/1/mr/2/r"/><ReadingTypeLink href="/rt/2"/></MeterReading><MeterReading href="/upt/1/mr/3"><description>Current Summation Delivered</description><ReadingLink href="/upt/1/mr/3/r"/><ReadingTypeLink href="/rt/3"/></MeterReading></MeterReadingList>',
        "/rt/1": '<ReadingType xmlns="urn:ieee:std:2030.5:ns"><accumulationBehaviour>12</accumulationBehaviour><dataQualifier>0</dataQualifier><flowDirection>1</flowDirection><kind>8</kind><phase>0</phase><powerOfTenMultiplier>0</powerOfTenMultiplier><uom>38</uom></ReadingType>',
        "/rt/2": '<ReadingType xmlns="urn:ieee:std:2030.5:ns"><accumulationBehaviour>9</accumulationBehaviour><dataQualifier>0</dataQualifier><flowDirection>19</flowDirection><kind>12</kind><phase>0</phase><powerOfTenMultiplier>0</powerOfTenMultiplier><uom>72</uom></ReadingType>',
        "/rt/3": '<ReadingType xmlns="urn:ieee:std:2030.5:ns"><accumulationBehaviour>9</accumulationBehaviour><dataQualifier>0</dataQualifier><flowDirection>1</flowDirection><kind>12</kind><phase>0</phase><powerOfTenMultiplier>0</powerOfTenMultiplier><uom>72</uom></ReadingType>',
        "/upt/1/mr/1/r": '<Reading xmlns="urn:ieee:std:2030.5:ns"><value>875</value></Reading>',
        "/upt/1/mr/2/r": '<Reading xmlns="urn:ieee:std:2030.5:ns"><value>1250</value></Reading>',
        "/upt/1/mr/3/r": '<Reading xmlns="urn:ieee:std:2030.5:ns"><value>40808961</value></Reading>',
    }
    snapshot = read_core_snapshot(FakeClient(responses), "192.168.1.122", 8081)
    assert snapshot.agent_version == AgentVersion.V3
    assert snapshot.software_version == "3.2.50"
    assert snapshot.instantaneous_power_w == 875
    assert snapshot.energy_received_wh == 1250
    assert snapshot.energy_delivered_wh == 40808961
    assert len(snapshot.readings) == 3
