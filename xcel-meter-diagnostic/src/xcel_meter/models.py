from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class AgentVersion(str, Enum):
    UNKNOWN = "unknown"
    V1_V2 = "1.x/2.x"
    V2 = "1.x/2.x"  # compatibility alias for pre-0.4.5 callers
    V3 = "3.x"


class ReadingKind(str, Enum):
    INSTANTANEOUS_DEMAND = "instantaneous_demand"
    CURRENT_SUMMATION_DELIVERED = "current_summation_delivered"
    CURRENT_SUMMATION_RECEIVED = "current_summation_received"
    VAH_DELIVERED = "vah_delivered"
    VAH_RECEIVED = "vah_received"
    VARH_DELIVERED = "varh_delivered"
    VARH_RECEIVED = "varh_received"
    MAX_DEMAND_DELIVERED = "max_demand_delivered"
    MAX_DEMAND_RECEIVED = "max_demand_received"
    TOU_WH_DELIVERED = "tou_wh_delivered"
    TOU_WH_RECEIVED = "tou_wh_received"
    WH_INTERVAL_DELIVERED = "wh_interval_delivered"
    WH_INTERVAL_RECEIVED = "wh_interval_received"
    WH_INTERVAL_NET = "wh_interval_net"
    VAH_INTERVAL_DELIVERED = "vah_interval_delivered"
    VAH_INTERVAL_RECEIVED = "vah_interval_received"
    VARH_INTERVAL_DELIVERED = "varh_interval_delivered"
    VARH_INTERVAL_RECEIVED = "varh_interval_received"
    POWER_FACTOR_ABC = "power_factor_abc"
    POWER_FACTOR_A = "power_factor_a"
    POWER_FACTOR_B = "power_factor_b"
    POWER_FACTOR_C = "power_factor_c"
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
            value = reading["kind"]
            reading["kind"] = value.value if hasattr(value, "value") else value
        return data
