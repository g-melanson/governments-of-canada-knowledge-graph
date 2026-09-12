"""Stage 1 adapter for Commons Members By-Law XML from ourcommons.ca."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator

from sources.base import BaseAdapter
from sources.xml_utils import WalkContext, walk
from sources.registry import register
from pipeline.ingest.schema import load_source_schema, normalized_fields
from pipeline.ingest.utils import parse_iso_datetime

_SCHEMA = load_source_schema("commons.members_bylaw")
_ROW_CLASSES = tuple(_SCHEMA["classes"].keys())
NORMALIZED_FIELDS = {
    cls: normalized_fields(_SCHEMA, target_class=cls) for cls in _ROW_CLASSES
}
DATE_TIME_FIELDS = {"date_time"}


@register
class CommonsMembersBylawAdapter(BaseAdapter):
    source = "commons.members_bylaw"

    def parse(self, raw_path: Path) -> Iterator[dict]:
        root = ET.parse(raw_path).getroot()
        ctx = WalkContext()
        yield from walk(root, ctx, ())

    def normalize(self, row: dict) -> dict:
        row_class = row["_row_class"]
        out: dict = {"_row_class": row_class}

        for slot in NORMALIZED_FIELDS[row_class]:
            val = row.get(slot)

            if slot in DATE_TIME_FIELDS:
                out[slot] = parse_iso_datetime(val) if isinstance(val, str) else val
                continue

            if isinstance(val, str):
                out[slot] = val.strip() or None
            else:
                out[slot] = val

        return out
