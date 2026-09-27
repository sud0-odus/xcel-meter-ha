from __future__ import annotations

import logging
from dataclasses import replace
from typing import Protocol

from .models import AgentVersion, MeterReadingDescriptor, ReadingKind, ReadingTypeInfo
from .xmlutil import (
    child_text,
    children_named,
    first_child,
    int_text,
    local_name,
    parse_xml,
)

LOGGER = logging.getLogger("xcel_meter.discovery")


class XmlClient(Protocol):
    def get_xml(self, path: str) -> str: ...


def determine_agent_version(
    client: XmlClient,
) -> tuple[AgentVersion, str | None, str | None]:
    root = parse_xml(client.get_xml("/sdev/sdi"))
    software_version = child_text(root, "softwareVersion")
    meter_lfdi = child_text(root, "lFDI")

    if not software_version:
        return AgentVersion.UNKNOWN, None, meter_lfdi

    try:
        major = int(software_version.split(".", 1)[0])
    except ValueError:
        return AgentVersion.UNKNOWN, software_version, meter_lfdi

    if major == 2:
        return AgentVersion.V2, software_version, meter_lfdi
    if major == 3:
        return AgentVersion.V3, software_version, meter_lfdi

    return AgentVersion.UNKNOWN, software_version, meter_lfdi


def find_electricity_usage_point(client: XmlClient) -> tuple[str, str, int]:
    root = parse_xml(client.get_xml("/upt"))
    for usage_point in children_named(root, "UsagePoint"):
        if child_text(usage_point, "status") != "1":
            continue
        if child_text(usage_point, "serviceCategoryKind") != "0":
            continue
        link = first_child(usage_point, "MeterReadingListLink")
        if link is None or not link.attrib.get("href"):
            continue
        return (
            usage_point.attrib.get("href", "/upt"),
            link.attrib["href"],
            int(link.attrib.get("all", "0")),
        )
    raise RuntimeError("No active electricity UsagePoint with a MeterReadingListLink was found")


def parse_meter_reading_list(xml_text: str) -> list[MeterReadingDescriptor]:
    root = parse_xml(xml_text)
    result: list[MeterReadingDescriptor] = []
    for item in children_named(root, "MeterReading"):
        rt = first_child(item, "ReadingTypeLink")
        if rt is None or not rt.attrib.get("href"):
            continue
        reading_link = first_child(item, "ReadingLink")
        set_link = first_child(item, "ReadingSetListLink")
        result.append(
            MeterReadingDescriptor(
                href=item.attrib.get("href"),
                description=child_text(item, "description") or "",
                mrid=child_text(item, "mRID"),
                reading_link=reading_link.attrib.get("href") if reading_link is not None else None,
                reading_type_link=rt.attrib["href"],
                reading_set_list_link=set_link.attrib.get("href") if set_link is not None else None,
                reading_set_all=(
                    int(set_link.attrib.get("all", "0")) if set_link is not None else None
                ),
            )
        )
    return result


def parse_reading_type(xml_text: str) -> ReadingTypeInfo:
    root = parse_xml(xml_text)
    return ReadingTypeInfo(
        accumulation_behaviour=int_text(root, "accumulationBehaviour"),
        data_qualifier=int_text(root, "dataQualifier"),
        flow_direction=int_text(root, "flowDirection"),
        kind=int_text(root, "kind"),
        phase=int_text(root, "phase"),
        uom=int_text(root, "uom"),
        power_of_ten_multiplier=int_text(root, "powerOfTenMultiplier") or 0,
    )


def classify_reading_type(
    info: ReadingTypeInfo,
    description: str,
    agent_version: AgentVersion,
) -> ReadingKind:
    # Some real Itron meters omit <phase> for aggregate readings instead
    # of explicitly returning phase=0. Normalize only for classification.
    phase = 0 if info.phase is None else info.phase

    t = (
        info.accumulation_behaviour,
        info.data_qualifier,
        info.flow_direction,
        info.kind,
        phase,
        info.uom,
    )
    description_lower = description.lower()

    # Agent v2 signatures from the Xcel Launchpad SDK reference.
    v2_mapping = {
        (12, 2, 1, 8, 0, 38): ReadingKind.INSTANTANEOUS_DEMAND,
        (9, 2, 1, 12, 0, 72): ReadingKind.CURRENT_SUMMATION_DELIVERED,
        (9, 2, 19, 12, 0, 72): ReadingKind.CURRENT_SUMMATION_RECEIVED,
    }

    if t in v2_mapping:
        return v2_mapping[t]

    # Newer Itron/Launchpad-style signatures use dataQualifier=0.
    #
    # These are classified from the ReadingType itself rather than trusting
    # a software-version label. This matters because real meters may omit
    # softwareVersion from /sdev/sdi.
    if t == (12, 0, 1, 8, 0, 38):
        return ReadingKind.INSTANTANEOUS_DEMAND

    if t == (4, 0, 1, 12, 0, 72):
        return ReadingKind.WH_INTERVAL_DELIVERED

    if t == (4, 0, 19, 12, 0, 72):
        return ReadingKind.WH_INTERVAL_RECEIVED

    if t == (4, 0, 4, 12, 0, 72):
        return ReadingKind.WH_INTERVAL_NET

    # Current summation and TOU Wh can share the same ReadingType tuple.
    # MeterReading.description is therefore needed to distinguish them.
    if t == (9, 0, 1, 12, 0, 72):
        return (
            ReadingKind.TOU_WH_DELIVERED
            if "tou" in description_lower
            else ReadingKind.CURRENT_SUMMATION_DELIVERED
        )

    if t == (9, 0, 19, 12, 0, 72):
        return (
            ReadingKind.TOU_WH_RECEIVED
            if "tou" in description_lower
            else ReadingKind.CURRENT_SUMMATION_RECEIVED
        )

    return ReadingKind.UNKNOWN


def discover_meter_readings(
    client: XmlClient,
    meter_reading_list_href: str,
    count: int,
    agent_version: AgentVersion,
) -> list[tuple[MeterReadingDescriptor, ReadingTypeInfo]]:
    suffix = f"?l={count}" if count > 0 else ""
    request_path = f"{meter_reading_list_href}{suffix}"
    xml_text = client.get_xml(request_path)
    readings = parse_meter_reading_list(xml_text)

    LOGGER.info(
        "MeterReading discovery: href=%s advertised_count=%s parsed=%s",
        meter_reading_list_href,
        count,
        len(readings),
    )

    if not readings:
        root = parse_xml(xml_text)
        direct_readings = children_named(root, "MeterReading")
        first_children = (
            [local_name(child.tag) for child in list(direct_readings[0])]
            if direct_readings
            else []
        )
        LOGGER.warning(
            "MeterReading list diagnostics: root=%s all=%s results=%s "
            "direct_children=%s meter_reading_children=%s first_entry_children=%s",
            local_name(root.tag),
            root.attrib.get("all"),
            root.attrib.get("results"),
            [local_name(child.tag) for child in list(root)],
            len(direct_readings),
            first_children,
        )

    result: list[tuple[MeterReadingDescriptor, ReadingTypeInfo]] = []
    for reading in readings:
        info = parse_reading_type(client.get_xml(reading.reading_type_link))
        kind = classify_reading_type(info, reading.description, agent_version)

        type_tuple = (
            info.accumulation_behaviour,
            info.data_qualifier,
            info.flow_direction,
            info.kind,
            info.phase,
            info.uom,
        )

        LOGGER.debug(
            "MeterReading candidate: description=%r reading=%s type=%s tuple=%s classified=%s",
            reading.description,
            reading.reading_link,
            reading.reading_type_link,
            type_tuple,
            kind.value,
        )

        result.append((replace(reading, kind=kind), info))

    return result
