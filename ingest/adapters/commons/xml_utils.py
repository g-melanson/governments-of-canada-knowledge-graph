"""Streaming XML helpers for House of Commons feeds (namespace-safe, xsi:nil)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET

XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(parent: ET.Element, tag: str) -> str | None:
    for child in parent:
        if local_tag(child.tag) == tag:
            if child.get(XSI_NIL) == "true":
                return None
            text = (child.text or "").strip()
            return text or None
    return None


def iter_member_of_parliament(path: Path) -> Iterator[ET.Element]:
    """Stream <MemberOfParliament> elements without loading full tree."""
    for event, elem in ET.iterparse(path, events=("end",)):
        if local_tag(elem.tag) == "MemberOfParliament":
            yield elem
            elem.clear()
