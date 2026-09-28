from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import MeterSnapshot, ReadingKind


DEFAULT_MAX_SAMPLE_AGE_SECONDS = 120.0
MAX_FUTURE_CLOCK_SKEW_SECONDS = 5.0


@dataclass(frozen=True)
class ReadingFreshness:
    sample_start_epoch: int
    sample_duration_seconds: int | None
    sample_end_epoch: int
    age_seconds: float
    stale: bool


def instantaneous_power_freshness(
    snapshot: MeterSnapshot,
    observed_at: datetime,
    *,
    max_age_seconds: float = DEFAULT_MAX_SAMPLE_AGE_SECONDS,
    max_future_skew_seconds: float = MAX_FUTURE_CLOCK_SKEW_SECONDS,
) -> ReadingFreshness | None:
    reading = next(
        (
            item
            for item in snapshot.readings
            if item.kind == ReadingKind.INSTANTANEOUS_DEMAND
        ),
        None,
    )

    if reading is None or reading.sample_start_epoch is None:
        return None

    duration = reading.sample_duration_seconds
    sample_end = reading.sample_start_epoch + (
        duration if duration is not None else 0
    )
    raw_age = observed_at.timestamp() - sample_end

    if raw_age < -max_future_skew_seconds:
        raise ValueError(
            "Instantaneous Demand sample timestamp is "
            f"{-raw_age:.1f}s in the future; exceeds "
            f"{max_future_skew_seconds:.1f}s clock-skew tolerance"
        )

    age = max(0.0, raw_age)

    return ReadingFreshness(
        sample_start_epoch=reading.sample_start_epoch,
        sample_duration_seconds=duration,
        sample_end_epoch=sample_end,
        age_seconds=age,
        stale=age > max_age_seconds,
    )
