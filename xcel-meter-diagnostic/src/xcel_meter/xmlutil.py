from __future__ import annotations

from xml.etree import ElementTree as ET


def parse_xml(xml_text: str) -> ET.Element:
    return ET.fromstring(xml_text)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def children_named(node: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(node) if local_name(child.tag) == name]


def first_child(node: ET.Element, name: str) -> ET.Element | None:
    for child in list(node):
        if local_name(child.tag) == name:
            return child
    return None


def child_text(node: ET.Element, name: str) -> str | None:
    child = first_child(node, name)
    if child is None or child.text is None:
        return None
    return child.text.strip()


def int_text(node: ET.Element, name: str) -> int | None:
    text = child_text(node, name)
    if text is None or text == "":
        return None
    return int(text)
