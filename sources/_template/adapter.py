"""Stage 1 adapter for TEMPLATE publisher data.

Replace this module docstring with: input format, encoding quirks, row shapes,
and any structural rules that are not simple field renames.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from sources.base import BaseAdapter
from sources.registry import register
from pipeline.ingest.schema import load_source_schema, publisher_field_map

log = logging.getLogger(__name__)

_SOURCE = "TEMPLATE"  # must match --source, sources.yaml key, and directory name
_TARGET_CLASS = "TEMPLATERow"

_SCHEMA = load_source_schema(_SOURCE)
FIELD_MAP = publisher_field_map(_SCHEMA, target_class=_TARGET_CLASS)


@register
class TemplateAdapter(BaseAdapter):
    source = _SOURCE

    def parse(self, raw_path: Path) -> Iterator[dict]:
        """Yield publisher-shaped dicts from the staged raw snapshot.

        Rules:
        - Always read raw_path (never hardcode repo data paths).
        - Yield dicts with schema slot names, not publisher names.
        - Set "_row_class" on every row (required even for single-class sources).
        - Use yield / yield from — do not accumulate the full corpus in memory.
        - Skip bad records with a counter + log warning; do not crash on dirt.
        """
        skipped = 0

        # TODO: open raw_path and decode publisher format (XML, CSV, JSON, etc.)
        #
        # for record in publisher_records(raw_path):
        #     if not usable(record):
        #         skipped += 1
        #         continue
        #     row: dict = {"_row_class": _TARGET_CLASS}
        #     for publisher_name, slot_name in FIELD_MAP.items():
        #         row[slot_name] = record.get(publisher_name)
        #     yield row

        if skipped:
            log.warning("%s: skipped %d unusable records", _SOURCE, skipped)

        # Stub: replace with real yields above; remove this line when implemented.
        yield from ()
