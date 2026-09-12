"""Tests for the TEMPLATE adapter.

Copy to pipeline/ingest/tests/adapters/test_TEMPLATE.py and fix imports.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sources.TEMPLATE.adapter import TemplateAdapter  # noqa: F401 — fix path after copy
from pipeline.ingest.normalize import SchemaNormalizer

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/raw/TEMPLATE_sample.xml"
SCHEMA = Path(__file__).resolve().parents[3] / "sources/TEMPLATE/TEMPLATE.schema.yaml"


@pytest.fixture
def adapter() -> TemplateAdapter:
    return TemplateAdapter()


@pytest.fixture
def normalizer() -> SchemaNormalizer:
    return SchemaNormalizer(SCHEMA)


class TestParse:
    def test_yields_row_class(self, adapter: TemplateAdapter) -> None:
        rows = list(adapter.parse(FIXTURE))
        assert rows, "add a tiny fixture and implement parse()"
        assert all(row["_row_class"] == "TEMPLATERow" for row in rows)


class TestNormalize:
    def test_string_blanks_become_none(
        self, adapter: TemplateAdapter, normalizer: SchemaNormalizer
    ) -> None:
        raw = next(adapter.parse(FIXTURE))
        row = normalizer.normalize(raw["_row_class"], raw)
        assert row["_row_class"] == "TEMPLATERow"
        # assert row["example_text_field"] == "expected"
