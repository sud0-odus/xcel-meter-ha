from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class AgentVersion(str, Enum):
    UNKNOWN = "unknown"
    V2 = "2.x"
    V3 = "3.x"


class ReadingKind(str, Enum):
    INSTANTANEOUS_DEMAND = "instantaneous_demand"
    CURRENT_SUMMATION_DELIVERED = "current_summation_delivered"
    CURRENT_SUMMATION_RECEIVED = "current_summation_received"
    TOU_WH_DELIVERED = "tou_wh_delivered"
    TOU_WH_RECEIVED = "tou_wh_received"
    WH_INTERVAL_DELIVERED = "wh_interval_delivered"
    WH_INTERVAL_RECEIVED = "wh_interval_received"
    WH_INTERVAL_NET = "wh_interval_net"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ReadingTypeInfo:
    accumulation_behaviour: int | None
    data_qualifier: int | None
    flow_direction: int | None
    kind: int | None
    phase: int | None
    uom: int | None
    power_of_ten_multiplier: int


@dataclass(frozen=True)
class MeterReadingDescriptor:
    href: str | None
    description: str
    mrid: str | None
    reading_link: str | None
    reading_type_link: str
    reading_set_list_link: str | None
    reading_set_all: int | None
    kind: ReadingKind = ReadingKind.UNKNOWN


@dataclass(frozen=True)
class CoreReading:
    kind: ReadingKind
    value: float
    unit: str
    raw_value: int | float
    multiplier: int
    description: str
    sample_start_epoch: int | None = None
    sample_duration_seconds: int | None = None


@dataclass(frozen=True)
class MeterSnapshot:
    host: str
    port: int
    agent_version: AgentVersion
    software_version: str | None
    usage_point_href: str
    meter_reading_list_href: str
    meter_lfdi: str | None
    instantaneous_power_w: float | None
    energy_delivered_wh: float | None
    energy_received_wh: float | None
    readings: tuple[CoreReading, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["agent_version"] = self.agent_version.value
        for reading in data["readings"]:
            reading["kind"] = reading["kind"].value if hasattr(reading["kind"], "value") else reading["kind"]
        return data
