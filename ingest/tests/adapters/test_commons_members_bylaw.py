"""Tests for the commons_members_bylaw adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingest.adapters.commons.members_bylaw import CommonsMembersBylawAdapter


class TestCommonsMembersBylawAdapter:
    FIXTURE = (
        Path(__file__).resolve().parents[1] / "fixtures/raw/commons_members_bylaw_sample.xml"
    )

    @pytest.fixture
    def adapter(self) -> CommonsMembersBylawAdapter:
        return CommonsMembersBylawAdapter()

    def test_parse_yields_mixed_row_classes(self, adapter: CommonsMembersBylawAdapter) -> None:
        rows = list(adapter.parse(self.FIXTURE))
        classes = {row["_row_class"] for row in rows}
        assert "ByLawDocumentRow" in classes
        assert "ByLawSectionRow" in classes
        assert "ByLawSubsectionRow" in classes
        assert "ByLawDefinedTermRow" in classes
        assert "ByLawTermCrossRefRow" in classes
        assert "ByLawParagraphRow" in classes
        assert "ByLawSubParagraphRow" in classes
        assert "ByLawExternalRefRow" in classes

    def test_section_carries_heading_context(self, adapter: CommonsMembersBylawAdapter) -> None:
        rows = list(adapter.parse(self.FIXTURE))
        section = next(r for r in rows if r["_row_class"] == "ByLawSectionRow")
        assert section["section_label"] == "1"
        assert section["heading_lv1"] == "General Provisions"

    def test_subparagraph_links_to_paragraph(self, adapter: CommonsMembersBylawAdapter) -> None:
        rows = list(adapter.parse(self.FIXTURE))
        subpara = next(r for r in rows if r["_row_class"] == "ByLawSubParagraphRow")
        assert subpara["paragraph_label"] == "(a)"
        assert subpara["label"] == "(i)"
        assert subpara["section_label"] == "1"
        assert subpara["subsection_label"] == "(1)"

    def test_defined_term_deduped(self, adapter: CommonsMembersBylawAdapter) -> None:
        rows = [r for r in adapter.parse(self.FIXTURE) if r["_row_class"] == "ByLawDefinedTermRow"]
        assert len(rows) == 1
        assert rows[0]["term_en"] == "Board"
        assert rows[0]["defined_in_section_label"] == "1"
        assert rows[0]["defined_in_subsection_label"] == "(1)"

    def test_normalize_parses_document_datetime(self, adapter: CommonsMembersBylawAdapter) -> None:
        raw = next(adapter.parse(self.FIXTURE))
        row = adapter.normalize(raw)
        assert isinstance(row["date_time"], datetime)
        assert row["date_time"].tzinfo == timezone.utc

    def test_normalize_preserves_row_class(self, adapter: CommonsMembersBylawAdapter) -> None:
        for raw in adapter.parse(self.FIXTURE):
            row = adapter.normalize(raw)
            assert row["_row_class"] == raw["_row_class"]
