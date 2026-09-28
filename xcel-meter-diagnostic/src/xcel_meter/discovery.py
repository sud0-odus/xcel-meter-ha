from __future__ import annotations

import logging
from dataclasses import replace
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import AgentVersion, MeterReadingDescriptor, ReadingKind, ReadingTypeInfo
from .reading_types import classify_sdk_reading
from .xmlutil import child_text, children_named, first_child, int_text, parse_xml

LOGGER = logging.getLogger("xcel_meter.discovery")


class XmlClient(Protocol):
    def get_xml(self, path: str) -> str: ...


def determine_agent_version(client: XmlClient) -> tuple[AgentVersion, str | None, str | None]:
    root = parse_xml(client.get_xml("/sdev/sdi"))
    software_version = child_text(root, "softwareVersion")
    meter_lfdi = child_text(root, "lFDI")

    # The Xcel SDK notes deployed Itron agent versions 1 and 3, and uses its
    # v1/v2 provider for both older generations. Keep Unknown when the real
    # meter omits softwareVersion rather than guessing.
    if not software_version:
        return AgentVersion.UNKNOWN, None, meter_lfdi

    try:
        major = int(software_version.split(".", 1)[0])
    except ValueError:
        return AgentVersion.UNKNOWN, software_version, meter_lfdi

    if major in {1, 2}:
        return AgentVersion.V1_V2, software_version, meter_lfdi
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
                reading_set_all=(int(set_link.attrib.get("all", "0")) if set_link is not None else None),
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
    # Classification is intentionally based on ReadingType metadata, not only
    # softwareVersion, because production meters may omit softwareVersion.
    del agent_version
    return classify_sdk_reading(info, description)


def _paging_path(href: str, limit: int, start: int) -> str:
    parsed = urlsplit(href)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["l"] = str(limit)
    if start:
        query["s"] = str(start)
    else:
        query.pop("s", None)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def _parse_list_counts(xml_text: str, fallback_results: int) -> tuple[int | None, int]:
    root = parse_xml(xml_text)
    try:
        total = int(root.attrib["all"]) if "all" in root.attrib else None
    except ValueError:
        total = None
    try:
        results = int(root.attrib.get("results", fallback_results))
    except ValueError:
        results = fallback_results
    return total, results


def _fetch_meter_reading_pages(
    client: XmlClient,
    href: str,
    advertised_count: int,
) -> list[MeterReadingDescriptor]:
    # Itron's implementation notes explicitly allow an agent to return fewer
    # list items than requested. Continue from the returned `results` count.
    total = advertised_count if advertised_count > 0 else None
    start = 0
    items: list[MeterReadingDescriptor] = []

    for _page in range(100):
        remaining = (total - start) if total is not None else 255
        if remaining <= 0:
            break
        request_path = _paging_path(href, remaining, start)
        xml_text = client.get_xml(request_path)
        page_items = parse_meter_reading_list(xml_text)
        returned_total, results = _parse_list_counts(xml_text, len(page_items))
        if returned_total is not None:
            total = returned_total

        items.extend(page_items)
        LOGGER.debug(
            "MeterReading page: href=%s start=%s requested=%s results=%s parsed=%s all=%s",
            href,
            start,
            remaining,
            results,
            len(page_items),
            total,
        )

        if results <= 0:
            break
        start += results
        if total is not None and start >= total:
            break
    else:
        raise RuntimeError("MeterReading paging exceeded 100 pages; refusing a possible loop")

    return items


def discover_meter_readings(
    client: XmlClient,
    meter_reading_list_href: str,
    count: int,
    agent_version: AgentVersion,
) -> list[tuple[MeterReadingDescriptor, ReadingTypeInfo]]:
    readings = _fetch_meter_reading_pages(client, meter_reading_list_href, count)

    LOGGER.info(
        "MeterReading discovery: href=%s advertised_count=%s parsed=%s",
        meter_reading_list_href,
        count,
        len(readings),
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
