from datetime import UTC, datetime

import pytest

from xcel_meter.freshness import (
    DEFAULT_MAX_SAMPLE_AGE_SECONDS,
    MAX_FUTURE_CLOCK_SKEW_SECONDS,
    instantaneous_power_freshness,
)
from xcel_meter.models import (
    AgentVersion,
    CoreReading,
    MeterSnapshot,
    ReadingKind,
)


def _snapshot(
    *,
    sample_start_epoch: int | None,
    sample_duration_seconds: int | None,
) -> MeterSnapshot:
    power = CoreReading(
        kind=ReadingKind.INSTANTANEOUS_DEMAND,
        value=1857.0,
        unit="W",
        raw_value=1857,
        multiplier=0,
        description="Instantaneous Demand",
        sample_start_epoch=sample_start_epoch,
        sample_duration_seconds=sample_duration_seconds,
    )

    return MeterSnapshot(
        host="192.0.2.10",
        port=8081,
        agent_version=AgentVersion.UNKNOWN,
        software_version=None,
        usage_point_href="/upt/1",
        meter_reading_list_href="/upt/1/mr",
        meter_lfdi="TEST-METER-LFDI",
        instantaneous_power_w=1857.0,
        energy_delivered_wh=40856243.0,
        energy_received_wh=None,
        readings=(power,),
    )


def test_freshness_uses_end_of_meter_time_period():
    snapshot = _snapshot(
        sample_start_epoch=1790557488,
        sample_duration_seconds=1,
    )
    observed_at = datetime.fromtimestamp(
        1790557489.289,
        UTC,
    )

    freshness = instantaneous_power_freshness(
        snapshot,
        observed_at,
    )

    assert freshness is not None
    assert freshness.sample_end_epoch == 1790557489
    assert freshness.age_seconds == pytest.approx(0.289, abs=0.001)
    assert freshness.stale is False


def test_freshness_marks_old_sample_stale():
    snapshot = _snapshot(
        sample_start_epoch=1790557000,
        sample_duration_seconds=1,
    )
    observed_at = datetime.fromtimestamp(
        1790557001 + DEFAULT_MAX_SAMPLE_AGE_SECONDS + 1,
        UTC,
    )

    freshness = instantaneous_power_freshness(
        snapshot,
        observed_at,
    )

    assert freshness is not None
    assert freshness.stale is True


def test_freshness_is_optional_for_meter_without_timestamp():
    snapshot = _snapshot(
        sample_start_epoch=None,
        sample_duration_seconds=None,
    )

    freshness = instantaneous_power_freshness(
        snapshot,
        datetime.now(UTC),
    )

    assert freshness is None


def test_missing_duration_is_preserved_and_start_is_used_for_age():
    snapshot = _snapshot(
        sample_start_epoch=1790557488,
        sample_duration_seconds=None,
    )
    observed_at = datetime.fromtimestamp(1790557488.5, UTC)

    freshness = instantaneous_power_freshness(
        snapshot,
        observed_at,
    )

    assert freshness is not None
    assert freshness.sample_duration_seconds is None
    assert freshness.sample_end_epoch == 1790557488
    assert freshness.age_seconds == pytest.approx(0.5, abs=0.001)
    assert freshness.stale is False


def test_small_future_clock_skew_is_tolerated_without_negative_age():
    snapshot = _snapshot(
        sample_start_epoch=1000,
        sample_duration_seconds=1,
    )
    observed_at = datetime.fromtimestamp(
        1001 - MAX_FUTURE_CLOCK_SKEW_SECONDS,
        UTC,
    )

    freshness = instantaneous_power_freshness(
        snapshot,
        observed_at,
    )

    assert freshness is not None
    assert freshness.age_seconds == 0.0
    assert freshness.stale is False


def test_large_future_meter_timestamp_is_rejected():
    snapshot = _snapshot(
        sample_start_epoch=2000,
        sample_duration_seconds=1,
    )
    observed_at = datetime.fromtimestamp(1000, UTC)

    with pytest.raises(
        ValueError,
        match="clock-skew tolerance",
    ):
        instantaneous_power_freshness(
            snapshot,
            observed_at,
        )
