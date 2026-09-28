from __future__ import annotations

import re
import sys
import tomllib
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "rate_profiles" / "profiles"
VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
VALID_STATUSES = {"current-example", "historical-example", "submitted"}
VALID_EVIDENCE_LEVELS = {
    "official-publication",
    "community-submitted",
    "maintainer-reviewed",
}
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$|^24:00$")
MONTH_DAY_RE = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


def _require_text(data: dict, key: str, errors: list[str]) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"missing or empty string: {key}")
        return ""
    return value.strip()


def _validate_date(value: str, key: str, errors: list[str], *, allow_empty: bool = False) -> None:
    if allow_empty and value == "":
        return
    try:
        date.fromisoformat(value)
    except ValueError:
        errors.append(f"{key} must be YYYY-MM-DD")


def _validate_url(value: str, key: str, errors: list[str]) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append(f"{key} must be an http(s) URL")


def validate_profile(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        return [f"invalid TOML: {exc}"]

    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    required_text = [
        "profile_id",
        "provider",
        "country",
        "state",
        "service_region",
        "rate_plan_name",
        "timezone",
        "currency",
        "unit",
        "status",
        "evidence_level",
        "effective_from",
        "last_verified",
        "billing_scope",
        "notes",
    ]
    for key in required_text:
        _require_text(data, key, errors)

    if data.get("status") not in VALID_STATUSES:
        errors.append(f"status must be one of {sorted(VALID_STATUSES)}")
    if data.get("evidence_level") not in VALID_EVIDENCE_LEVELS:
        errors.append(f"evidence_level must be one of {sorted(VALID_EVIDENCE_LEVELS)}")
    if data.get("billing_scope") != "energy-only":
        errors.append('billing_scope must currently be "energy-only"')
    if data.get("currency") != "USD":
        errors.append('currency must currently be "USD"')
    if data.get("unit") != "kWh":
        errors.append('unit must currently be "kWh"')

    effective_from = data.get("effective_from")
    if isinstance(effective_from, str):
        _validate_date(effective_from, "effective_from", errors)
    effective_to = data.get("effective_to", "")
    if not isinstance(effective_to, str):
        errors.append("effective_to must be a string")
    else:
        _validate_date(effective_to, "effective_to", errors, allow_empty=True)
    last_verified = data.get("last_verified")
    if isinstance(last_verified, str):
        _validate_date(last_verified, "last_verified", errors)

    source = data.get("source")
    if not isinstance(source, dict):
        errors.append("missing [source] table")
    else:
        for key in ("kind", "url", "reference"):
            _require_text(source, key, errors)
        if isinstance(source.get("url"), str) and source["url"]:
            _validate_url(source["url"], "source.url", errors)

    periods = data.get("periods")
    period_names: set[str] = set()
    if not isinstance(periods, list) or not periods:
        errors.append("at least one [[periods]] entry is required")
    else:
        fallback_count = 0
        for index, period in enumerate(periods, start=1):
            prefix = f"periods[{index}]"
            if not isinstance(period, dict):
                errors.append(f"{prefix} must be a table")
                continue
            name = period.get("name")
            if not isinstance(name, str) or not name.strip():
                errors.append(f"{prefix}.name is required")
            elif name in period_names:
                errors.append(f"duplicate period name: {name}")
            else:
                period_names.add(name)
            days = period.get("days")
            if not isinstance(days, list) or not days:
                errors.append(f"{prefix}.days must be a non-empty list")
            elif any(day not in VALID_DAYS for day in days):
                errors.append(f"{prefix}.days contains an invalid day")
            for key in ("start", "end"):
                value = period.get(key)
                if not isinstance(value, str) or not TIME_RE.fullmatch(value):
                    errors.append(f"{prefix}.{key} must be HH:MM (24:00 allowed only as an end)")
                elif key == "start" and value == "24:00":
                    errors.append(f"{prefix}.start cannot be 24:00")
            if not isinstance(period.get("exclude_holidays"), bool):
                errors.append(f"{prefix}.exclude_holidays must be true or false")
            if period.get("fallback") is True:
                fallback_count += 1
        if fallback_count > 1:
            errors.append("only one period may set fallback = true")

    seasons = data.get("seasons")
    if not isinstance(seasons, list) or not seasons:
        errors.append("at least one [[seasons]] entry is required")
    else:
        season_names: set[str] = set()
        for index, season in enumerate(seasons, start=1):
            prefix = f"seasons[{index}]"
            if not isinstance(season, dict):
                errors.append(f"{prefix} must be a table")
                continue
            name = season.get("name")
            if not isinstance(name, str) or not name.strip():
                errors.append(f"{prefix}.name is required")
            elif name in season_names:
                errors.append(f"duplicate season name: {name}")
            else:
                season_names.add(name)
            for key in ("start", "end"):
                value = season.get(key)
                if not isinstance(value, str) or not MONTH_DAY_RE.fullmatch(value):
                    errors.append(f"{prefix}.{key} must be MM-DD")
            rates = season.get("rates")
            if not isinstance(rates, dict) or not rates:
                errors.append(f"{prefix}.rates is required")
                continue
            unknown = set(rates) - period_names
            missing = period_names - set(rates)
            if unknown:
                errors.append(f"{prefix}.rates has unknown periods: {sorted(unknown)}")
            if missing:
                errors.append(f"{prefix}.rates is missing periods: {sorted(missing)}")
            for period_name, rate in rates.items():
                if isinstance(rate, bool) or not isinstance(rate, (int, float)) or rate < 0:
                    errors.append(f"{prefix}.rates.{period_name} must be a non-negative number")

    return errors


def main() -> int:
    profiles = sorted(PROFILE_DIR.glob("*.toml"))
    if not profiles:
        location = PROFILE_DIR.relative_to(ROOT)
        print(f"Rate profile validation failed: no profiles found in {location}")
        return 1

    errors: list[str] = []
    seen_ids: dict[str, Path] = {}
    for path in profiles:
        profile_errors = validate_profile(path)
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            profile_id = data.get("profile_id")
        except (tomllib.TOMLDecodeError, UnicodeDecodeError):
            profile_id = None
        if isinstance(profile_id, str) and profile_id:
            other = seen_ids.get(profile_id)
            if other is not None:
                profile_errors.append(
                    f"duplicate profile_id {profile_id!r}; also used by {other.relative_to(ROOT)}"
                )
            else:
                seen_ids[profile_id] = path
        errors.extend(f"{path.relative_to(ROOT)}: {error}" for error in profile_errors)

    if errors:
        print("Rate profile validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Rate profile validation PASS: {len(profiles)} profile(s) checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
