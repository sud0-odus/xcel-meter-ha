from __future__ import annotations

from xcel_meter.discovery import discover_meter_readings
from xcel_meter.models import AgentVersion, ReadingKind


RT = """<ReadingType><accumulationBehaviour>12</accumulationBehaviour><dataQualifier>0</dataQualifier><flowDirection>1</flowDirection><kind>8</kind><phase>0</phase><uom>38</uom><powerOfTenMultiplier>0</powerOfTenMultiplier></ReadingType>"""


def _page(start: int, count: int, total: int = 5) -> str:
    entries = "".join(
        f'<MeterReading href="/mr/{i}"><description>Instantaneous Demand</description><ReadingLink href="/mr/{i}/r"/><ReadingTypeLink href="/rt/{i}"/></MeterReading>'
        for i in range(start, start + count)
    )
    return f'<MeterReadingList all="{total}" results="{count}">{entries}</MeterReadingList>'


class PagingClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_xml(self, path: str) -> str:
        self.calls.append(path)
        if path == "/mr?l=5":
            return _page(0, 2)
        if path == "/mr?l=3&s=2":
            return _page(2, 2)
        if path == "/mr?l=1&s=4":
            return _page(4, 1)
        if path.startswith("/rt/"):
            return RT
        raise KeyError(path)


def test_meter_reading_discovery_pages_using_returned_results_count() -> None:
    client = PagingClient()
    readings = discover_meter_readings(client, "/mr", 5, AgentVersion.V3)

    assert len(readings) == 5
    assert all(item[0].kind == ReadingKind.INSTANTANEOUS_DEMAND for item in readings)
    assert client.calls[:3] == ["/mr?l=5", "/mr?l=3&s=2", "/mr?l=1&s=4"]
