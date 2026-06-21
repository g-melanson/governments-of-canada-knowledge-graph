"""Tests for the commons_members adapter using a trimmed offline XML fixture."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingest.adapters.commons.members import CommonsMembersAdapter, FIELD_MAP


class TestCommonsMembersAdapter:

    FIELD_MAP = FIELD_MAP
    FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/raw/commons_members_sample.xml"

    @pytest.fixture
    def adapter(self) -> CommonsMembersAdapter:
        return CommonsMembersAdapter()

    def test_parse_yields_dicts(self, adapter: CommonsMembersAdapter) -> None:
        rows = list(adapter.parse(self.FIXTURE))
        assert type(rows) == list
        assert len(rows) >= 1
        assert all(isinstance(row, dict) for row in rows)

    def test_parse_yields_expected_keys(self, adapter: CommonsMembersAdapter) -> None:
        rows = list(adapter.parse(self.FIXTURE))
        assert all(set(row.keys()) == set(self.FIELD_MAP.values()) for row in rows)

    def test_normalize_yields_string_ids(self, adapter: CommonsMembersAdapter) -> None:
        rows = [adapter.normalize(r) for r in adapter.parse(self.FIXTURE)]
        assert all(isinstance(r["person_id"], str) for r in rows if r["person_id"] is not None)

    def test_normalize_yields_datetime_fields(self, adapter: CommonsMembersAdapter) -> None:
        rows = [adapter.normalize(r) for r in adapter.parse(self.FIXTURE)]
        for row in rows:
            assert isinstance(row["from_date_time"], datetime)
            assert row["from_date_time"].tzinfo == timezone.utc
            assert row["to_date_time"] is None or isinstance(row["to_date_time"], datetime)
