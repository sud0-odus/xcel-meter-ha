from __future__ import annotations

import copy
import sys
import tomllib
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from generate_ha_tou_package import render_package  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "rate_profiles" / "profiles" / "us-mn-xcel-a72-a74-2022.toml"


def _profile() -> dict:
    return tomllib.loads(PROFILE.read_text(encoding="utf-8"))


def test_historical_profile_generates_ha_utility_meter_package() -> None:
    rendered = render_package(
        _profile(),
        source_entity="sensor.example_energy_delivered",
    )

    assert "utility_meter:" in rendered
    assert 'source: "sensor.example_energy_delivered"' in rendered
    assert 'select.xcel_tou_monthly_energy' in rendered
    assert 'sensor.xcel_tou_current_period' in rendered
    assert 'sensor.xcel_tou_current_season' in rendered
    assert 'unique_id: "xcel_tou_current_rate"' in rendered
    assert 'input_datetime.xcel_tou_provider_holiday' in rendered
    assert 'action: select.select_option' in rendered

    for tariff in ("off_peak", "on_peak", "mid_peak"):
        assert f'- "{tariff}"' in rendered

    for rate in ("0.22576", "0.09013", "0.02784", "0.19266", "0.07515"):
        assert rate in rendered


def test_generator_allows_custom_namespace_and_cycle() -> None:
    rendered = render_package(
        _profile(),
        source_entity="sensor.grid_import_total",
        namespace="garage_rate",
        cycle="daily",
    )

    assert "garage_rate_daily_energy:" in rendered
    assert 'select.garage_rate_daily_energy' in rendered
    assert 'sensor.garage_rate_current_period' in rendered
    assert 'input_datetime.garage_rate_provider_holiday' in rendered


def test_generator_rejects_cross_midnight_period_until_semantics_are_defined() -> None:
    profile = copy.deepcopy(_profile())
    period = next(item for item in profile["periods"] if item["name"] == "off_peak")
    period["start"] = "22:00"
    period["end"] = "06:00"

    with pytest.raises(ValueError, match="crosses midnight"):
        render_package(
            profile,
            source_entity="sensor.example_energy_delivered",
        )


def test_generator_rejects_non_sensor_source_entity() -> None:
    with pytest.raises(ValueError, match="source entity"):
        render_package(
            _profile(),
            source_entity="input_number.not_energy",
        )
