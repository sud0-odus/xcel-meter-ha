from __future__ import annotations

from dataclasses import dataclass

from .discovery import (
    XmlClient,
    determine_agent_version,
    discover_meter_readings,
    find_electricity_usage_point,
)
from .models import (
    AgentVersion,
    CoreReading,
    MeterReadingDescriptor,
    MeterSnapshot,
    ReadingKind,
    ReadingTypeInfo,
)
from .xmlutil import child_text, local_name, parse_xml


BASE_CORE_KINDS = {
    ReadingKind.INSTANTANEOUS_DEMAND,
    ReadingKind.CURRENT_SUMMATION_DELIVERED,
}


@dataclass(frozen=True)
class MeterProfile:
    agent_version: AgentVersion
    software_version: str | None
    meter_lfdi: str | None
    usage_point_href: str
    meter_reading_list_href: str
    core_readings: tuple[
        tuple[MeterReadingDescriptor, ReadingTypeInfo],
        ...,
    ]


def _scaled_value(
    raw: str,
    info: ReadingTypeInfo,
) -> tuple[float, int | float]:
    numeric: int | float
    try:
        numeric = int(raw)
    except ValueError:
        numeric = float(raw)

    return (
        float(numeric) * (10 ** info.power_of_ten_multiplier),
        numeric,
    )


@dataclass(frozen=True)
class _ParsedReading:
    value: float
    raw_value: int | float
    sample_start_epoch: int | None
    sample_duration_seconds: int | None


def _optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None

    try:
        return int(value)
    except ValueError:
        return None


def _reading_time_metadata(
    root,
) -> tuple[int | None, int | None]:
    for node in root.iter():
        if local_name(node.tag) != "timePeriod":
            continue

        start = _optional_int(child_text(node, "start"))
        duration = _optional_int(child_text(node, "duration"))

        if duration is not None and duration < 0:
            duration = None

        return start, duration

    return None, None


def _read_single_value(
    client: XmlClient,
    href: str,
    info: ReadingTypeInfo,
) -> _ParsedReading | None:
    root = parse_xml(client.get_xml(href))
    raw = child_text(root, "value")

    if raw is None:
        return None

    scaled, numeric = _scaled_value(raw, info)
    sample_start, sample_duration = _reading_time_metadata(root)

    return _ParsedReading(
        value=scaled,
        raw_value=numeric,
        sample_start_epoch=sample_start,
        sample_duration_seconds=sample_duration,
    )


def _unit_for(kind: ReadingKind) -> str:
    if kind == ReadingKind.INSTANTANEOUS_DEMAND:
        return "W"

    if kind in {
        ReadingKind.CURRENT_SUMMATION_DELIVERED,
        ReadingKind.CURRENT_SUMMATION_RECEIVED,
        ReadingKind.TOU_WH_DELIVERED,
        ReadingKind.TOU_WH_RECEIVED,
        ReadingKind.WH_INTERVAL_DELIVERED,
        ReadingKind.WH_INTERVAL_RECEIVED,
        ReadingKind.WH_INTERVAL_NET,
    }:
        return "Wh"

    return ""


def discover_core_profile(
    client: XmlClient,
    include_received: bool = True,
) -> MeterProfile:
    agent_version, software_version, meter_lfdi = determine_agent_version(
        client
    )

    usage_href, reading_list_href, count = (
        find_electricity_usage_point(client)
    )

    descriptors = discover_meter_readings(
        client,
        reading_list_href,
        count,
        agent_version,
    )

    wanted = set(BASE_CORE_KINDS)

    if include_received:
        wanted.add(
            ReadingKind.CURRENT_SUMMATION_RECEIVED
        )

    core_readings = tuple(
        (descriptor, info)
        for descriptor, info in descriptors
        if descriptor.kind in wanted
        and descriptor.reading_link
    )

    return MeterProfile(
        agent_version=agent_version,
        software_version=software_version,
        meter_lfdi=meter_lfdi,
        usage_point_href=usage_href,
        meter_reading_list_href=reading_list_href,
        core_readings=core_readings,
    )


def read_core_snapshot(
    client: XmlClient,
    host: str,
    port: int,
    profile: MeterProfile | None = None,
) -> MeterSnapshot:
    if profile is None:
        profile = discover_core_profile(client)

    core: list[CoreReading] = []

    for descriptor, info in profile.core_readings:
        if not descriptor.reading_link:
            continue

        parsed = _read_single_value(
            client,
            descriptor.reading_link,
            info,
        )

        if parsed is None:
            # Official SDK treats an absent value as
            # unsupported/unavailable.
            continue

        core.append(
            CoreReading(
                kind=descriptor.kind,
                value=parsed.value,
                unit=_unit_for(descriptor.kind),
                raw_value=parsed.raw_value,
                multiplier=info.power_of_ten_multiplier,
                description=descriptor.description,
                sample_start_epoch=parsed.sample_start_epoch,
                sample_duration_seconds=(
                    parsed.sample_duration_seconds
                ),
            )
        )

    by_kind = {
        item.kind: item.value
        for item in core
    }

    return MeterSnapshot(
        host=host,
        port=port,
        agent_version=profile.agent_version,
        software_version=profile.software_version,
        usage_point_href=profile.usage_point_href,
        meter_reading_list_href=profile.meter_reading_list_href,
        meter_lfdi=profile.meter_lfdi,
        instantaneous_power_w=by_kind.get(
            ReadingKind.INSTANTANEOUS_DEMAND
        ),
        energy_delivered_wh=by_kind.get(
            ReadingKind.CURRENT_SUMMATION_DELIVERED
        ),
        energy_received_wh=by_kind.get(
            ReadingKind.CURRENT_SUMMATION_RECEIVED
        ),
        readings=tuple(core),
    )
