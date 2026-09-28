from __future__ import annotations

import pytest

from xcel_meter.discovery import classify_reading_type
from xcel_meter.models import AgentVersion, ReadingKind, ReadingTypeInfo


@pytest.mark.parametrize(
    ("signature", "description", "kind"),
    [
        ((12, 2, 1, 8, 0, 38), "Instantaneous Demand", ReadingKind.INSTANTANEOUS_DEMAND),
        ((9, 2, 1, 12, 0, 71), "VAh Delivered", ReadingKind.VAH_DELIVERED),
        ((9, 2, 19, 12, 0, 73), "VARh Received", ReadingKind.VARH_RECEIVED),
        ((12, 0, 1, 8, 0, 38), "Instantaneous Demand", ReadingKind.INSTANTANEOUS_DEMAND),
        ((12, 8, 1, 8, 0, 38), "Max Demand Delivered", ReadingKind.MAX_DEMAND_DELIVERED),
        ((12, 8, 19, 8, 0, 38), "Max Demand Received", ReadingKind.MAX_DEMAND_RECEIVED),
        ((4, 0, 1, 12, 0, 71), "VAh Interval Delivered", ReadingKind.VAH_INTERVAL_DELIVERED),
        ((4, 0, 19, 12, 0, 73), "VARh Interval Received", ReadingKind.VARH_INTERVAL_RECEIVED),
        ((12, 0, 0, 0, 224, 65), "Power Factor", ReadingKind.POWER_FACTOR_ABC),
        ((12, 0, 0, 0, 128, 65), "Power Factor Phase A", ReadingKind.POWER_FACTOR_A),
    ],
)
def test_sdk_reading_signatures(signature, description, kind) -> None:
    info = ReadingTypeInfo(
        accumulation_behaviour=signature[0],
        data_qualifier=signature[1],
        flow_direction=signature[2],
        kind=signature[3],
        phase=signature[4],
        uom=signature[5],
        power_of_ten_multiplier=0,
    )
    assert classify_reading_type(info, description, AgentVersion.UNKNOWN) == kind


def test_v3_tou_is_disambiguated_from_current_summation_by_description() -> None:
    info = ReadingTypeInfo(9, 0, 1, 12, 0, 72, 0)
    assert classify_reading_type(info, "Current Summation Delivered", AgentVersion.V3) == (
        ReadingKind.CURRENT_SUMMATION_DELIVERED
    )
    assert classify_reading_type(info, "TOU Wh Delivered", AgentVersion.V3) == ReadingKind.TOU_WH_DELIVERED
