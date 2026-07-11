"""Tests for the commons_members_expenditures adapter."""

from __future__ import annotations

import pickle
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingest.adapters.commons.members_expenditures import (
    CommonsMembersExpendituresAdapter,
    fiscal_quarter_bounds,
)

UUID = "2bbb3585-824f-4411-9f76-c75f226a8c06"


def _url(kind: str, year: int = 2021, quarter: int = 2) -> str:
    return (
        "https://www.ourcommons.ca/ProactiveDisclosure/en/members/"
        f"{kind}/{year}/{quarter}/{UUID}/csv"
    )


CONTRACT_CSV = (
    '\ufeff"Members \u2013 Detailed Contract Expenditures Report \u2013 Smith, Jane \u2013 Q2 2021"\r\n'
    "Supplier,Description,Date,Total\r\n"
    "Acme Signs,Advertising,2020/07/15,100.00\r\n"
    "Acme Signs,Advertising,2020/07/15,100.00\r\n"  # duplicate on purpose
).encode("utf-8")

TRAVEL_CSV = (
    '\ufeff"Members \u2013 Detailed Travel Expenditures Report \u2013 Smith, Jane \u2013 Q2 2021"\r\n'
    "Claim,Travel start date,Travel end date,Traveller Name,Traveller Type,"
    "Purpose of Travel,Dates,Departure,Destination,Transportation,Accommodations,"
    "Meals and Incidentals,Points Reg.,Points Spec.,Points U.S.A.,Total\r\n"
    "T0001,2020/07/09,2020/07/09,,,,,,,161.05,0.00,98.30,1,0,0,259.35\r\n"
    'T0001,2020/07/09,2020/07/09,"Smith, Jane",Member,To travel,2020/07/09,Hometown,Ottawa,,,,,,,\r\n'
    'T0001,2020/07/09,2020/07/09,"Smith, Jane",Member,To travel,2020/07/09,Ottawa,Hometown,,,,,,,\r\n'
).encode("utf-8")

HOSPITALITY_CSV = (
    '\ufeff"Members \u2013 Detailed Hospitality Expenditures Report \u2013 Smith, Jane \u2013 Q2 2021"\r\n'
    "Date,Location,Total of Attendees,Purpose of Hospitality,Type of Event,Claim,Supplier,Total\r\n"
    "2020/07/09,Ottawa,4,To meet constituents,Hosting a meeting,M0001,Cafe One, 87.64\r\n"
).encode("utf-8")


@pytest.fixture
def raw_pickle(tmp_path: Path) -> Path:
    corpus = {
        _url("contract"): CONTRACT_CSV,
        _url("travel"): TRAVEL_CSV,
        _url("hospitality"): HOSPITALITY_CSV,
        _url("contract", year=2022, quarter=1): None,       # failed download
        "https://example.com/not-a-report": b"junk",         # unrecognized URL
    }
    path = tmp_path / "expense_claims.pkl"
    path.write_bytes(pickle.dumps(corpus))
    return path


@pytest.fixture
def adapter() -> CommonsMembersExpendituresAdapter:
    return CommonsMembersExpendituresAdapter()


class TestParse:
    def test_one_report_row_per_usable_file(self, adapter, raw_pickle) -> None:
        rows = list(adapter.parse(raw_pickle))
        reports = [r for r in rows if r["_row_class"] == "ExpenseReportRow"]
        assert {r["report_type"] for r in reports} == {"contract", "travel", "hospitality"}
        assert all(r["member_disclosure_uuid"] == UUID for r in reports)
        assert all(r["member_name"] == "Smith, Jane" for r in reports)

    def test_contract_duplicates_kept_distinct_by_row_index(self, adapter, raw_pickle) -> None:
        rows = [
            r for r in adapter.parse(raw_pickle)
            if r["_row_class"] == "ContractExpenditureRow"
        ]
        assert len(rows) == 2
        assert [r["row_index"] for r in rows] == [0, 1]
        assert rows[0]["supplier"] == "Acme Signs"
        assert rows[0]["date_time"] == "2020/07/15"  # publisher string, untouched

    def test_travel_splits_summary_from_segments(self, adapter, raw_pickle) -> None:
        rows = list(adapter.parse(raw_pickle))
        summaries = [r for r in rows if r["_row_class"] == "TravelExpenditureRow"]
        segments = [r for r in rows if r["_row_class"] == "TravelClaimSegmentRow"]
        assert len(summaries) == 1 and summaries[0]["total"] == "259.35"
        assert [s["segment_index"] for s in segments] == [0, 1]
        assert segments[0]["traveller_name"] == "Smith, Jane"
        assert segments[1]["destination"] == "Hometown"

    def test_hospitality_columns_mapped_via_schema(self, adapter, raw_pickle) -> None:
        row = next(
            r for r in adapter.parse(raw_pickle)
            if r["_row_class"] == "HospitalityExpenditureRow"
        )
        assert row["claim_id"] == "M0001"
        assert row["supplier"] == "Cafe One"
        assert row["expense_date"] == "2020/07/09"

    def test_unusable_entries_skipped_not_fatal(self, adapter, raw_pickle) -> None:
        reports = [
            r for r in adapter.parse(raw_pickle) if r["_row_class"] == "ExpenseReportRow"
        ]
        assert len(reports) == 3  # None payload and junk URL both skipped


class TestFiscalQuarters:
    def test_q2_2021_is_july_to_september_2020(self) -> None:
        start, end = fiscal_quarter_bounds(2021, 2)
        assert start == datetime(2020, 7, 1, tzinfo=timezone.utc)
        assert (end.year, end.month, end.day) == (2020, 9, 30)

    def test_q4_wraps_into_the_fiscal_years_own_calendar_year(self) -> None:
        start, end = fiscal_quarter_bounds(2021, 4)
        assert start == datetime(2021, 1, 1, tzinfo=timezone.utc)
        assert (end.month, end.day) == (3, 31)


class TestNormalize:
    def test_strips_whitespace_and_blanks_to_none(self, adapter, raw_pickle) -> None:
        raw = next(
            r for r in adapter.parse(raw_pickle)
            if r["_row_class"] == "HospitalityExpenditureRow"
        )
        row = adapter.normalize(raw)
        assert row["total"] == "87.64"  # leading space stripped

        # empty publisher cells become None, not ""
        seg = next(
            r for r in adapter.parse(raw_pickle)
            if r["_row_class"] == "TravelClaimSegmentRow"
        )
        assert adapter.normalize(seg)["transportation"] is None

    def test_row_class_and_ints_preserved(self, adapter, raw_pickle) -> None:
        for raw in adapter.parse(raw_pickle):
            row = adapter.normalize(raw)
            assert row["_row_class"] == raw["_row_class"]
            assert row["report_year"] == 2021 and row["report_quarter"] == 2
