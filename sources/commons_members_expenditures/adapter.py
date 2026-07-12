from __future__ import annotations

import csv
import io
import logging
import pickle
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from sources.base import BaseAdapter
from sources.registry import register
from pipeline.ingest.schema import load_source_schema, normalized_fields, publisher_field_map

log = logging.getLogger(__name__)

_SCHEMA = load_source_schema("commons_members_expenditures")
_ROW_CLASSES = tuple(_SCHEMA["classes"].keys())
NORMALIZED_FIELDS = {
    cls: normalized_fields(_SCHEMA, target_class=cls) for cls in _ROW_CLASSES
}
# {row_class: {publisher CSV header -> our slot name}}, from schema annotations.
FIELD_MAPS = {
    cls: publisher_field_map(_SCHEMA, target_class=cls) for cls in _ROW_CLASSES
}

_URL_RE = re.compile(
    r"/members/(?P<type>contract|travel|hospitality)"
    r"/(?P<year>\d{4})/(?P<quarter>\d)/(?P<uuid>[0-9a-f-]{36})/csv"
)

_EN_DASH = "\u2013"  # the "–" separating title segments


def _member_name_from_title(title: str) -> str | None:
    """'Members – Detailed ... Report – Zuberi, Sameer – Q2 2021' -> 'Zuberi, Sameer'."""
    parts = [p.strip() for p in title.split(_EN_DASH)]
    return parts[2] if len(parts) >= 4 else None


def fiscal_quarter_bounds(fiscal_year: int, quarter: int) -> tuple[datetime, datetime]:
    """UTC bounds of a federal fiscal quarter.

    Fiscal year N runs Apr 1 (N-1) .. Mar 31 (N); Q1=Apr-Jun ... Q4=Jan-Mar.
    """
    start_month = 4 + 3 * (quarter - 1)
    start_year = fiscal_year - 1
    if start_month > 12:
        start_month -= 12
        start_year += 1
    start = datetime(start_year, start_month, 1, tzinfo=timezone.utc)

    end_month, end_year = start_month + 3, start_year
    if end_month > 12:
        end_month -= 12
        end_year += 1
    end = datetime(end_year, end_month, 1, tzinfo=timezone.utc) - timedelta(microseconds=1)
    return start, end


def _mapped(rec: dict[str, str], row_class: str) -> dict:
    """Rename publisher CSV columns to schema slots, keeping only known columns."""
    return {
        slot: rec.get(header)
        for header, slot in FIELD_MAPS[row_class].items()
        if header in rec
    }


@register
class CommonsMembersExpendituresAdapter(BaseAdapter):
    source = "commons_members_expenditures"

    def parse(self, raw_path: Path) -> Iterator[dict]:
        with raw_path.open("rb") as fh:
            corpus: dict[str, bytes | None] = pickle.load(fh)

        skipped = 0
        for url, payload in corpus.items():
            match = _URL_RE.search(url)
            if match is None or payload is None:
                skipped += 1
                continue

            report_type = match["type"]
            year, quarter = int(match["year"]), int(match["quarter"])
            uuid = match["uuid"]

            rows = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"))))
            if len(rows) < 2:  # need at least title + header
                skipped += 1
                continue
            title, header, data_rows = rows[0][0], rows[1], rows[2:]
            member_name = _member_name_from_title(title)

            report_ctx = {
                "member_disclosure_uuid": uuid,
                "report_year": year,
                "report_quarter": quarter,
            }

            start, end = fiscal_quarter_bounds(year, quarter)
            yield {
                "_row_class": "ExpenseReportRow",
                **report_ctx,
                "report_type": report_type,
                "member_name": member_name,
                "report_start_date": start,
                "report_end_date": end,
            }

            if report_type == "contract":
                yield from self._contract_rows(header, data_rows, report_ctx, member_name)
            elif report_type == "hospitality":
                yield from self._hospitality_rows(header, data_rows, report_ctx)
            else:
                yield from self._travel_rows(header, data_rows, report_ctx)

        if skipped:
            log.warning("expenditures: skipped %d unusable pickle entries", skipped)

    @staticmethod
    def _contract_rows(header, data_rows, report_ctx, member_name) -> Iterator[dict]:
        for idx, cells in enumerate(data_rows):
            rec = dict(zip(header, cells))
            yield {
                "_row_class": "ContractExpenditureRow",
                **report_ctx,
                "row_number": idx,
                "member_name": member_name,
                **_mapped(rec, "ContractExpenditureRow"),
            }

    @staticmethod
    def _hospitality_rows(header, data_rows, report_ctx) -> Iterator[dict]:
        for cells in data_rows:
            rec = dict(zip(header, cells))
            yield {
                "_row_class": "HospitalityExpenditureRow",
                **report_ctx,
                **_mapped(rec, "HospitalityExpenditureRow"),
            }

    @staticmethod
    def _travel_rows(header, data_rows, report_ctx) -> Iterator[dict]:
        segment_index = 0
        for cells in data_rows:
            rec = dict(zip(header, cells))
            is_summary = not (rec.get("Traveller Name") or "").strip()
            if is_summary:
                segment_index = 0
                yield {
                    "_row_class": "TravelExpenditureRow",
                    **report_ctx,
                    **_mapped(rec, "TravelExpenditureRow"),
                }
            else:
                yield {
                    "_row_class": "TravelClaimSegmentRow",
                    **report_ctx,
                    "segment_index": segment_index,
                    **_mapped(rec, "TravelClaimSegmentRow"),
                }
                segment_index += 1

    def normalize(self, row: dict) -> dict:

        row_class = row["_row_class"]
        out: dict = {"_row_class": row_class}
        for slot in NORMALIZED_FIELDS[row_class]:
            val = row.get(slot)
            if isinstance(val, str):
                out[slot] = val.strip() or None
            else:
                out[slot] = val
        return out
