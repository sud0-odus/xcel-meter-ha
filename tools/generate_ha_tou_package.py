from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

from check_rate_profiles import validate_profile

ROOT = Path(__file__).resolve().parents[1]
SAFE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
ENTITY_ID_RE = re.compile(r"^sensor\.[a-z0-9_]+$")
NAME_RE = re.compile(r"^[a-z0-9_]+$")
SUPPORTED_CYCLES = ("daily", "weekly", "monthly")


def _yaml_string(value: str) -> str:
    """Return a double-quoted scalar that is also valid YAML."""
    return json.dumps(value, ensure_ascii=False)


def _load_profile(path: Path) -> dict:
    errors = validate_profile(path)
    if errors:
        rendered = "\n".join(f"- {error}" for error in errors)
        raise ValueError(f"rate profile validation failed:\n{rendered}")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _validate_generation_constraints(profile: dict) -> None:
    for period in profile["periods"]:
        name = period["name"]
        if not NAME_RE.fullmatch(name):
            raise ValueError(
                f"period name {name!r} is not generator-safe; use lowercase letters, numbers, "
                "and underscores"
            )
        if period.get("fallback") is True:
            continue
        if period["start"] >= period["end"]:
            raise ValueError(
                f"period {name!r} crosses midnight or is empty; the Phase 2 generator does not "
                "guess day-boundary semantics yet"
            )

    for season in profile["seasons"]:
        name = season["name"]
        if not NAME_RE.fullmatch(name):
            raise ValueError(
                f"season name {name!r} is not generator-safe; use lowercase letters, numbers, "
                "and underscores"
            )


def _period_condition(period: dict, *, holiday_entity: str | None) -> str:
    days = repr(period["days"])
    condition = (
        f"day in {days} and hm >= {period['start']!r} and hm < {period['end']!r}"
    )
    if period["exclude_holidays"]:
        if holiday_entity is None:
            raise ValueError("holiday-aware period requires a holiday override entity")
        condition += " and not holiday"
    return condition


def _render_period_state(profile: dict, *, holiday_entity: str | None) -> list[str]:
    periods = profile["periods"]
    explicit = [period for period in periods if period.get("fallback") is not True]
    fallback = next((period for period in periods if period.get("fallback") is True), None)

    lines = [
        "          {% set day = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'][now().weekday()] %}",
        "          {% set hm = now().strftime('%H:%M') %}",
    ]
    if holiday_entity is not None:
        lines.append(
            f"          {{% set holiday = is_state({_yaml_string(holiday_entity)}, 'on') %}}"
        )

    for index, period in enumerate(explicit):
        keyword = "if" if index == 0 else "elif"
        condition = _period_condition(period, holiday_entity=holiday_entity)
        lines.append(f"          {{% {keyword} {condition} %}}")
        lines.append(f"            {period['name']}")

    if fallback is not None:
        if explicit:
            lines.append("          {% else %}")
        else:
            lines.append("          {% if true %}")
        lines.append(f"            {fallback['name']}")
        lines.append("          {% endif %}")
    elif explicit:
        lines.extend(
            [
                "          {% else %}",
                "            unknown",
                "          {% endif %}",
            ]
        )
    else:
        lines.append("          unknown")

    return lines


def _season_condition(season: dict) -> str:
    start = season["start"]
    end = season["end"]
    if start <= end:
        return f"md >= {start!r} and md <= {end!r}"
    return f"md >= {start!r} or md <= {end!r}"


def _render_season_state(profile: dict) -> list[str]:
    lines = ["          {% set md = now().strftime('%m-%d') %}"]
    for index, season in enumerate(profile["seasons"]):
        keyword = "if" if index == 0 else "elif"
        lines.append(f"          {{% {keyword} {_season_condition(season)} %}}")
        lines.append(f"            {season['name']}")
    lines.extend(
        [
            "          {% else %}",
            "            unknown",
            "          {% endif %}",
        ]
    )
    return lines


def _render_rate_state(profile: dict, period_entity: str, season_entity: str) -> list[str]:
    lines = [
        f"          {{% set period = states({_yaml_string(period_entity)}) %}}",
        f"          {{% set season = states({_yaml_string(season_entity)}) %}}",
    ]
    branch = 0
    for season in profile["seasons"]:
        for period_name, rate in season["rates"].items():
            keyword = "if" if branch == 0 else "elif"
            lines.append(
                f"          {{% {keyword} season == {season['name']!r} "
                f"and period == {period_name!r} %}}"
            )
            lines.append(f"            {rate!r}")
            branch += 1
    lines.extend(
        [
            "          {% else %}",
            "            0",
            "          {% endif %}",
        ]
    )
    return lines


def render_package(
    profile: dict,
    *,
    source_entity: str,
    namespace: str = "xcel_tou",
    cycle: str = "monthly",
) -> str:
    if not ENTITY_ID_RE.fullmatch(source_entity):
        raise ValueError("source entity must look like sensor.some_entity")
    if not SAFE_ID_RE.fullmatch(namespace):
        raise ValueError("namespace must start with a letter and contain only a-z, 0-9, and _")
    if cycle not in SUPPORTED_CYCLES:
        raise ValueError(f"cycle must be one of {SUPPORTED_CYCLES}")

    _validate_generation_constraints(profile)

    profile_id = profile["profile_id"]
    periods = profile["periods"]
    period_names = [period["name"] for period in periods]
    season_names = [season["name"] for season in profile["seasons"]]
    needs_holiday_override = any(period["exclude_holidays"] for period in periods)

    meter_key = f"{namespace}_{cycle}_energy"
    meter_select = f"select.{meter_key}"
    period_key = f"{namespace}_current_period"
    season_key = f"{namespace}_current_season"
    rate_key = f"{namespace}_current_rate"
    period_entity = f"sensor.{period_key}"
    season_entity = f"sensor.{season_key}"
    holiday_key = f"{namespace}_provider_holiday"
    holiday_entity = f"input_boolean.{holiday_key}" if needs_holiday_override else None
    rate_unit = f"{profile['currency']}/{profile['unit']}"

    lines = [
        "# Generated by xcel-meter-ha tools/generate_ha_tou_package.py",
        f"# Profile: {profile_id}",
        f"# Status: {profile['status']} | Evidence: {profile['evidence_level']}",
        f"# Profile timezone: {profile['timezone']}",
        "#",
        "# This is an energy-use helper, not an authoritative bill calculator.",
        "# Verify the rate profile and Home Assistant timezone before relying on it.",
        "# Keep the Xcel Meter HA add-on rate-agnostic; this package consumes its HA sensor.",
        "",
        "utility_meter:",
        f"  {meter_key}:",
        f"    name: {_yaml_string(f'Xcel TOU {cycle.title()} Energy')}",
        f"    source: {_yaml_string(source_entity)}",
        f"    cycle: {cycle}",
        "    tariffs:",
    ]
    lines.extend(f"      - {_yaml_string(name)}" for name in period_names)

    if needs_holiday_override:
        lines.extend(
            [
                "",
                "input_boolean:",
                f"  {holiday_key}:",
                f"    name: {_yaml_string('Xcel TOU Provider Holiday Today')}",
                "    icon: mdi:calendar-alert",
            ]
        )

    lines.extend(
        [
            "",
            "template:",
            "  - sensor:",
            f"      - name: {_yaml_string('Xcel TOU Current Period')}",
            f"        unique_id: {_yaml_string(period_key)}",
            "        icon: mdi:clock-outline",
            "        state: >-",
        ]
    )
    lines.extend(_render_period_state(profile, holiday_entity=holiday_entity))
    lines.extend(
        [
            "        attributes:",
            f"          profile_id: {_yaml_string(profile_id)}",
            f"          rate_plan: {_yaml_string(profile['rate_plan_name'])}",
            f"          rate_code: {_yaml_string(profile.get('rate_code', ''))}",
            f"          profile_status: {_yaml_string(profile['status'])}",
            f"          evidence_level: {_yaml_string(profile['evidence_level'])}",
            "",
            f"      - name: {_yaml_string('Xcel TOU Current Season')}",
            f"        unique_id: {_yaml_string(season_key)}",
            "        icon: mdi:calendar-range",
            "        state: >-",
        ]
    )
    lines.extend(_render_season_state(profile))
    lines.extend(
        [
            "",
            f"      - name: {_yaml_string('Xcel TOU Current Rate')}",
            f"        unique_id: {_yaml_string(rate_key)}",
            f"        unit_of_measurement: {_yaml_string(rate_unit)}",
            "        state_class: measurement",
            "        icon: mdi:currency-usd",
            "        availability: >-",
            f"          {{{{ states({_yaml_string(period_entity)}) in {period_names!r}",
            f"             and states({_yaml_string(season_entity)}) in {season_names!r} }}}}",
            "        state: >-",
        ]
    )
    lines.extend(_render_rate_state(profile, period_entity, season_entity))

    lines.extend(
        [
            "",
            "automation:",
            f"  - id: {_yaml_string(f'{namespace}_sync_utility_meter_tariff')}",
            f"    alias: {_yaml_string('Xcel TOU - Sync Utility Meter Tariff')}",
            "    mode: restart",
            "    triggers:",
            "      - trigger: homeassistant",
            "        event: start",
            "      - trigger: state",
            f"        entity_id: {_yaml_string(period_entity)}",
            "      - trigger: state",
            f"        entity_id: {_yaml_string(meter_select)}",
        ]
    )
    if holiday_entity is not None:
        lines.extend(
            [
                "      - trigger: state",
                f"        entity_id: {_yaml_string(holiday_entity)}",
            ]
        )
    lines.extend(
        [
            "    actions:",
            "      - delay: \"00:00:02\"",
            "      - condition: template",
            "        value_template: >-",
            f"          {{{{ states({_yaml_string(period_entity)}) in "
            f"state_attr({_yaml_string(meter_select)}, 'options') | default([], true) }}}}",
            "      - condition: template",
            "        value_template: >-",
            f"          {{{{ states({_yaml_string(meter_select)}) != "
            f"states({_yaml_string(period_entity)}) }}}}",
            "      - action: select.select_option",
            "        target:",
            f"          entity_id: {_yaml_string(meter_select)}",
            "        data:",
            f"          option: \"{{{{ states('{period_entity}') }}}}\"",
            "",
        ]
    )

    if needs_holiday_override:
        lines.extend(
            [
                f"  - id: {_yaml_string(f'{namespace}_reset_provider_holiday')}",
                f"    alias: {_yaml_string('Xcel TOU - Reset Provider Holiday')}",
                "    mode: single",
                "    triggers:",
                "      - trigger: time",
                "        at: \"00:00:00\"",
                "    conditions:",
                "      - condition: state",
                f"        entity_id: {_yaml_string(holiday_entity)}",
                "        state: \"on\"",
                "    actions:",
                "      - action: input_boolean.turn_off",
                "        target:",
                f"          entity_id: {_yaml_string(holiday_entity)}",
                "",
                "# This profile excludes one or more provider-defined holidays from a TOU period.",
                f"# Turn on {holiday_entity} only for a provider-defined holiday.",
                "# A generated midnight automation turns the override back off for the next day.",
                "# The profile currently stores holiday guidance as text, not a machine-readable calendar.",
                "",
            ]
        )

    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an opt-in Home Assistant TOU package from a repository rate profile."
    )
    parser.add_argument("profile", type=Path, help="Path to a rate_profiles/profiles/*.toml file")
    parser.add_argument(
        "--source-entity",
        required=True,
        help="Home Assistant cumulative Energy Delivered sensor entity_id",
    )
    parser.add_argument(
        "--namespace",
        default="xcel_tou",
        help="Entity namespace for generated helpers (default: xcel_tou)",
    )
    parser.add_argument(
        "--cycle",
        choices=SUPPORTED_CYCLES,
        default="monthly",
        help="Utility Meter reset cycle (default: monthly)",
    )
    parser.add_argument("--output", type=Path, help="Write YAML to this file instead of stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        profile = _load_profile(args.profile)
        rendered = render_package(
            profile,
            source_entity=args.source_entity,
            namespace=args.namespace,
            cycle=args.cycle,
        )
    except (OSError, tomllib.TOMLDecodeError, ValueError) as exc:
        print(f"TOU package generation failed: {exc}", file=sys.stderr)
        return 1

    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Generated Home Assistant TOU package: {args.output}")

    if profile["status"] != "current-example":
        print(
            f"WARNING: profile {profile['profile_id']} is marked {profile['status']}; "
            "verify rates before using it.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
