from __future__ import annotations

from .discovery import (
    XmlClient,
    determine_agent_version,
    discover_meter_readings,
    find_electricity_usage_point,
)
from .models import CoreReading, MeterSnapshot, ReadingKind, ReadingTypeInfo
from .xmlutil import child_text, parse_xml


def _scaled_value(raw: str, info: ReadingTypeInfo) -> tuple[float, int | float]:
    numeric: int | float
    try:
        numeric = int(raw)
    except ValueError:
        numeric = float(raw)
    return float(numeric) * (10 ** info.power_of_ten_multiplier), numeric


def _read_single_value(client: XmlClient, href: str, info: ReadingTypeInfo) -> tuple[float, int | float] | None:
    root = parse_xml(client.get_xml(href))
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


def read_core_snapshot(client: XmlClient, host: str, port: int) -> MeterSnapshot:
    agent_version, software_version, meter_lfdi = determine_agent_version(client)
    usage_href, reading_list_href, count = find_electricity_usage_point(client)
    descriptors = discover_meter_readings(client, reading_list_href, count, agent_version)

    wanted = {
        ReadingKind.INSTANTANEOUS_DEMAND,
        ReadingKind.CURRENT_SUMMATION_DELIVERED,
        ReadingKind.CURRENT_SUMMATION_RECEIVED,
    }
    core: list[CoreReading] = []
    for descriptor, info in descriptors:
        if descriptor.kind not in wanted or not descriptor.reading_link:
            continue
        value = _read_single_value(client, descriptor.reading_link, info)
        if value is None:
            # Official SDK treats an absent value as unsupported/unavailable.
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

    by_kind = {item.kind: item.value for item in core}
    return MeterSnapshot(
        host=host,
        port=port,
        agent_version=agent_version,
        software_version=software_version,
        usage_point_href=usage_href,
        meter_reading_list_href=reading_list_href,
        meter_lfdi=meter_lfdi,
        instantaneous_power_w=by_kind.get(ReadingKind.INSTANTANEOUS_DEMAND),
        energy_delivered_wh=by_kind.get(ReadingKind.CURRENT_SUMMATION_DELIVERED),
        energy_received_wh=by_kind.get(ReadingKind.CURRENT_SUMMATION_RECEIVED),
        readings=tuple(core),
    )
