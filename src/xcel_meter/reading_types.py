"""Itron ReadingType signatures derived from Xcel/Itron Launchpad SDK providers."""

from __future__ import annotations

from .models import ReadingKind, ReadingTypeInfo


def normalized_signature(info: ReadingTypeInfo) -> tuple[int | None, ...]:
    # Production Itron meters may omit phase for aggregate/not-applicable values.
    phase = 0 if info.phase is None else info.phase
    return (
        info.accumulation_behaviour,
        info.data_qualifier,
        info.flow_direction,
        info.kind,
        phase,
        info.uom,
    )


# Version 1/2-compatible provider from the SDK.
V1_V2_SIGNATURES = {
    (12, 2, 1, 8, 0, 38): ReadingKind.INSTANTANEOUS_DEMAND,
    (9, 2, 1, 12, 0, 72): ReadingKind.CURRENT_SUMMATION_DELIVERED,
    (9, 2, 19, 12, 0, 72): ReadingKind.CURRENT_SUMMATION_RECEIVED,
    (9, 2, 1, 12, 0, 71): ReadingKind.VAH_DELIVERED,
    (9, 2, 19, 12, 0, 71): ReadingKind.VAH_RECEIVED,
    (9, 2, 1, 12, 0, 73): ReadingKind.VARH_DELIVERED,
    (9, 2, 19, 12, 0, 73): ReadingKind.VARH_RECEIVED,
}

# Version 3 provider from the SDK. Current Summation Wh and TOU Wh share the
# same ReadingType signature; MeterReading.description disambiguates those.
V3_SIGNATURES = {
    (12, 0, 1, 8, 0, 38): ReadingKind.INSTANTANEOUS_DEMAND,
    (9, 0, 1, 12, 0, 72): ReadingKind.CURRENT_SUMMATION_DELIVERED,
    (9, 0, 19, 12, 0, 72): ReadingKind.CURRENT_SUMMATION_RECEIVED,
    (9, 0, 1, 12, 0, 71): ReadingKind.VAH_DELIVERED,
    (9, 0, 19, 12, 0, 71): ReadingKind.VAH_RECEIVED,
    (9, 0, 1, 12, 0, 73): ReadingKind.VARH_DELIVERED,
    (9, 0, 19, 12, 0, 73): ReadingKind.VARH_RECEIVED,
    (12, 8, 1, 8, 0, 38): ReadingKind.MAX_DEMAND_DELIVERED,
    (12, 8, 19, 8, 0, 38): ReadingKind.MAX_DEMAND_RECEIVED,
    (4, 0, 1, 12, 0, 72): ReadingKind.WH_INTERVAL_DELIVERED,
    (4, 0, 19, 12, 0, 72): ReadingKind.WH_INTERVAL_RECEIVED,
    (4, 0, 4, 12, 0, 72): ReadingKind.WH_INTERVAL_NET,
    (4, 0, 1, 12, 0, 71): ReadingKind.VAH_INTERVAL_DELIVERED,
    (4, 0, 19, 12, 0, 71): ReadingKind.VAH_INTERVAL_RECEIVED,
    (4, 0, 1, 12, 0, 73): ReadingKind.VARH_INTERVAL_DELIVERED,
    (4, 0, 19, 12, 0, 73): ReadingKind.VARH_INTERVAL_RECEIVED,
    (12, 0, 0, 0, 224, 65): ReadingKind.POWER_FACTOR_ABC,
    (12, 0, 0, 0, 128, 65): ReadingKind.POWER_FACTOR_A,
    (12, 0, 0, 0, 64, 65): ReadingKind.POWER_FACTOR_B,
    (12, 0, 0, 0, 32, 65): ReadingKind.POWER_FACTOR_C,
}


def classify_sdk_reading(info: ReadingTypeInfo, description: str) -> ReadingKind:
    signature = normalized_signature(info)
    description_lower = description.lower()

    if signature == (9, 0, 1, 12, 0, 72) and "tou" in description_lower:
        return ReadingKind.TOU_WH_DELIVERED
    if signature == (9, 0, 19, 12, 0, 72) and "tou" in description_lower:
        return ReadingKind.TOU_WH_RECEIVED

    return V3_SIGNATURES.get(signature, V1_V2_SIGNATURES.get(signature, ReadingKind.UNKNOWN))
