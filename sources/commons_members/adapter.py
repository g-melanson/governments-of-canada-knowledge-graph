"""Stage 1 adapter for MemberOfParliament XML from ourcommons.ca."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from sources.base import BaseAdapter
from sources.xml_utils import child_text, iter_member_of_parliament, local_tag
from sources.registry import register

from pipeline.ingest.schema import load_source_schema, publisher_field_map, normalized_fields
from pipeline.ingest.utils import parse_iso_datetime

_SCHEMA = load_source_schema("commons_members")
_TARGET_CLASS = "CommonsMembersRow"
FIELD_MAP = publisher_field_map(_SCHEMA, target_class=_TARGET_CLASS)
NORMALIZED_FIELDS = normalized_fields(_SCHEMA, target_class=_TARGET_CLASS)

@register
class CommonsMembersAdapter(BaseAdapter):
    source = "commons_members"

    def parse(self, raw_path: Path) -> Iterator[dict]:
        for elem in iter_member_of_parliament(raw_path):
            row: dict = {"_row_class": "CommonsMembersRow"}
            for child in elem:
                xml_name = local_tag(child.tag)
                if xml_name not in FIELD_MAP:
                    continue
                row[FIELD_MAP[xml_name]] = child_text(elem, xml_name)
            yield row
        