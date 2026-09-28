from __future__ import annotations

import logging

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


LOGGER = logging.getLogger(__name__)


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


def _log_reading_time_metadata(
    root,
    href: str,
) -> None:
    time_period = None

    for node in root.iter():
        if local_name(node.tag) == "timePeriod":
            time_period = node
            break

    if time_period is not None:
        LOGGER.info(
            "Instantaneous reading time metadata: "
            "href=%s timePeriod.start=%s "
            "timePeriod.duration=%s",
            href,
            child_text(time_period, "start"),
            child_text(time_period, "duration"),
        )
        return

    timestamp_fields: list[str] = []

    interesting_names = {
        "start",
        "duration",
        "dateTime",
        "createdDateTime",
        "localTime",
        "timeStamp",
        "timestamp",
    }

    for node in root.iter():
        name = local_name(node.tag)

        if (
            name in interesting_names
            and node.text is not None
            and node.text.strip()
        ):
            timestamp_fields.append(
                f"{name}={node.text.strip()}"
            )

    if timestamp_fields:
        LOGGER.info(
            "Instantaneous reading time metadata: "
            "href=%s fields=%s",
            href,
            ", ".join(timestamp_fields),
        )
    else:
        LOGGER.info(
            "Instantaneous reading time metadata: "
            "href=%s NOT REPORTED",
            href,
        )


def _read_single_value(
    client: XmlClient,
    href: str,
    info: ReadingTypeInfo,
    *,
    log_time_metadata: bool = False,
) -> tuple[float, int | float] | None:
    root = parse_xml(client.get_xml(href))

    if log_time_metadata:
        _log_reading_time_metadata(
            root,
            href,
        )

    raw = child_text(root, "value")

    if raw is None:
        return None

    return _scaled_value(raw, info)


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

        value = _read_single_value(
            client,
            descriptor.reading_link,
            info,
            log_time_metadata=(
                descriptor.kind
                == ReadingKind.INSTANTANEOUS_DEMAND
            ),
        )

        if value is None:
            # Official SDK treats an absent value as
            # unsupported/unavailable.
            continue

        scaled, raw = value

        core.append(
            CoreReading(
                kind=descriptor.kind,
                value=scaled,
                unit=_unit_for(descriptor.kind),
                raw_value=raw,
                multiplier=info.power_of_ten_multiplier,
                description=descriptor.description,
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
