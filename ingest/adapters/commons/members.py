"""Stage 1 adapter for MemberOfParliament XML from ourcommons.ca."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from ingest.adapters.base import BaseAdapter
from ingest.adapters.commons.xml_utils import child_text, iter_member_of_parliament, local_tag
from ingest.adapters.registry import register

from ingest.schema import load_source_schema, publisher_field_map, normalized_fields
from ingest.utils import parse_iso_datetime

_SCHEMA = load_source_schema("commons_members")
_TARGET_CLASS = "CommonsMembersRow"
FIELD_MAP = publisher_field_map(_SCHEMA, target_class=_TARGET_CLASS)
NORMALIZED_FIELDS = normalized_fields(_SCHEMA, target_class=_TARGET_CLASS)

@register
class CommonsMembersAdapter(BaseAdapter):
    source = "commons_members"

    def parse(self, raw_path: Path) -> Iterator[dict]:
        for elem in iter_member_of_parliament(raw_path):
            row: dict = {}
            for child in elem:
                xml_name = local_tag(child.tag)
                if xml_name not in FIELD_MAP:
                    continue
                row[FIELD_MAP[xml_name]] = child_text(elem, xml_name)
            yield row

    def normalize(self, row: dict) -> dict:
        out = {}
        DATE_TIME_FIELDS = {"from_date_time", "to_date_time"}
        
        for target_key in FIELD_MAP.values():
            val = row.get(target_key)
            
            if target_key == "person_id" and val is not None:
                out[target_key] = str(val).strip()
                continue

            if target_key in DATE_TIME_FIELDS:
                out[target_key] = parse_iso_datetime(val)
                continue

            if isinstance(val, str):
                out[target_key] = val.strip() or None
            else:
                out[target_key] = val

        return out