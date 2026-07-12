"""Tests for the YAML-map-driven transform engine."""
from __future__ import annotations

from pathlib import Path

import pytest

from transforms.map_engine import YamlMapEngine, _eval_expr

TRANSFORMS = Path(__file__).resolve().parents[2] / "transforms"
BYLAW_MAP = TRANSFORMS / "commons_members_bylaw_to_gckg.transform.yaml"
MEMBERS_MAP = TRANSFORMS / "commons_members_to_gckg.transform.yaml"


# ---------------------------------------------------------------------------
# _eval_expr unit tests
# ---------------------------------------------------------------------------

def test_eval_expr_simple_concat():
    result = _eval_expr("'prefix:' + str(label)", {"label": "45.1"})
    assert result == "prefix:45.1"


def test_eval_expr_conditional():
    result = _eval_expr(
        "'P:' + str(section) + (':S:' + str(sub) if sub else '')",
        {"section": "3", "sub": None},
    )
    assert result == "P:3"


def test_eval_expr_passthrough_none():
    result = _eval_expr("term_fr", {"term_fr": None})
    assert result is None


# ---------------------------------------------------------------------------
# YamlMapEngine dispatch table construction
# ---------------------------------------------------------------------------

def test_dispatch_table_built_from_bylaw_map():
    engine = YamlMapEngine(BYLAW_MAP)
    assert "ByLawDocumentRow" in engine.dispatch_table
    assert "ByLawSectionRow" in engine.dispatch_table
    assert "ByLawSubsectionRow" in engine.dispatch_table
    assert "ByLawParagraphRow" in engine.dispatch_table
    assert "ByLawSubParagraphRow" in engine.dispatch_table
    assert "ByLawDefinedTermRow" in engine.dispatch_table
    assert "ByLawExternalRefRow" in engine.dispatch_table
    assert "ByLawTermCrossRefRow" in engine.dispatch_table


def test_no_derivation_for_unknown_row_class():
    engine = YamlMapEngine(BYLAW_MAP)
    fragments = list(engine.materialize({"_row_class": "UnknownRow"}, 1))
    assert fragments == []


# ---------------------------------------------------------------------------
# YamlMapEngine.materialize — per-class smoke tests
# ---------------------------------------------------------------------------

def test_materialize_bylaw_document_row():
    engine = YamlMapEngine(BYLAW_MAP)
    row = {
        "_row_class": "ByLawDocumentRow",
        "date_time": "2016-01-01",
        "long_title": "Bylaw No. 1 Respecting the Members of the House",
        "bill_origin": "House",
        "lang": "en",
        "stage": "3R",
    }
    fragments = list(engine.materialize(row, 1))
    assert len(fragments) == 1
    f = fragments[0]
    assert f["@type"] == "ByLaw"
    assert "2016-01-01" in f["id"]
    assert f["name"] == row["long_title"]


def test_materialize_section_row():
    engine = YamlMapEngine(BYLAW_MAP)
    row = {
        "_row_class": "ByLawSectionRow",
        "section_label": "45.1",
        "text": "Some text",
        "marginal_note": "Remuneration",
        "heading_lv1": "PART I",
        "heading_lv2": None,
        "heading_lv3": None,
    }
    fragments = list(engine.materialize(row, 2))
    assert len(fragments) == 1
    f = fragments[0]
    assert f["@type"] == "ByLawSection"
    assert f["id"] == "gckg:Commons:MembersByLaw:Section:45.1"
    assert f["label"] == "45.1"
    assert f["heading_lv1"] == "PART I"


def test_materialize_subsection_row():
    engine = YamlMapEngine(BYLAW_MAP)
    row = {
        "_row_class": "ByLawSubsectionRow",
        "section_label": "3",
        "subsection_label": "(1)",
        "text": "Sub text",
        "marginal_note": None,
    }
    fragments = list(engine.materialize(row, 3))
    f = fragments[0]
    assert f["@type"] == "ByLawSubsection"
    assert f["id"] == "gckg:Commons:MembersByLaw:Section:3:Subsection:(1)"


def test_materialize_paragraph_row_no_subsection():
    engine = YamlMapEngine(BYLAW_MAP)
    row = {
        "_row_class": "ByLawParagraphRow",
        "section_label": "5",
        "subsection_label": None,
        "label": "(a)",
        "text": "Para text",
    }
    fragments = list(engine.materialize(row, 4))
    f = fragments[0]
    assert f["@type"] == "ByLawParagraph"
    assert f["id"] == "gckg:Commons:MembersByLaw:Section:5:Paragraph:(a)"


def test_materialize_defined_term_row():
    engine = YamlMapEngine(BYLAW_MAP)
    row = {
        "_row_class": "ByLawDefinedTermRow",
        "term_en": "Speaker",
        "term_fr": "Président",
        "defined_in_section_label": "2",
        "defined_in_subsection_label": "(1)",
        "text": "the Speaker of the House",
    }
    fragments = list(engine.materialize(row, 5))
    f = fragments[0]
    assert f["@type"] == "ByLawDefinedTerm"
    assert f["id"] == "gckg:Commons:MembersByLaw:DefinedTerm:Speaker"
    assert f["term_fr"] == "Président"


# ---------------------------------------------------------------------------
# commons_members YAML map — target_type / RELATIONSHIP
# ---------------------------------------------------------------------------

def test_commons_members_emits_three_fragments():
    engine = YamlMapEngine(MEMBERS_MAP)
    row = {
        "_row_class": "CommonsMembersRow",
        "person_id": "42",
        "person_official_first_name": "Jane",
        "person_official_last_name": "Doe",
        "from_date_time": "2015-10-20",
        "to_date_time": "2019-09-11",
    }
    fragments = list(engine.materialize(row, 1))
    types = [f["@type"] for f in fragments]
    assert "Person" in types
    assert "MemberOfParliament" in types
    assert "RELATIONSHIP" in types


def test_commons_members_relationship_uses_target_type():
    engine = YamlMapEngine(MEMBERS_MAP)
    row = {
        "_row_class": "CommonsMembersRow",
        "person_id": "7",
        "person_official_first_name": "A",
        "person_official_last_name": "B",
        "from_date_time": "2020-01-01",
        "to_date_time": None,
    }
    fragments = list(engine.materialize(row, 2))
    rel = next(f for f in fragments if f["@type"] == "RELATIONSHIP")
    assert rel["rel_type"] == "HAS_ROLE"
    assert "gckg:Person:Commons:7" == rel["subject"]
    assert "gckg:MemberOfParliament:7:2020-01-01" == rel["object"]


def test_commons_members_person_full_name():
    engine = YamlMapEngine(MEMBERS_MAP)
    row = {
        "_row_class": "CommonsMembersRow",
        "person_id": "1",
        "person_official_first_name": "John",
        "person_official_last_name": "Smith",
        "from_date_time": "2010-05-02",
        "to_date_time": "2015-10-18",
    }
    fragments = list(engine.materialize(row, 3))
    person = next(f for f in fragments if f["@type"] == "Person")
    assert person["name"] == "John Smith"


def test_default_row_class_used_when_no_row_class_in_record():
    """Rows without _row_class fall back to default_row_class (single-class sources)."""
    engine = YamlMapEngine(MEMBERS_MAP, default_row_class="CommonsMembersRow")
    row = {
        # no _row_class key
        "person_id": "5",
        "person_official_first_name": "X",
        "person_official_last_name": "Y",
        "from_date_time": "2021-01-01",
        "to_date_time": None,
    }
    fragments = list(engine.materialize(row, 1))
    assert len(fragments) == 3


# ---------------------------------------------------------------------------
# when: guard — YamlMapEngine skips derivations whose guard evaluates falsy
# ---------------------------------------------------------------------------

def _engine_from_spec(spec_text: str, tmp_path) -> YamlMapEngine:
    """Write an inline spec to a temp file and return an engine over it."""
    p = tmp_path / "spec.yaml"
    p.write_text(spec_text, encoding="utf-8")
    return YamlMapEngine(p)


def test_when_guard_absent_emits_fragment(tmp_path):
    """A derivation with no when: key always emits (C2 — existing behavior unchanged)."""
    spec = """
class_derivations:
  MyNode:
    populated_from: MyRow
    slot_derivations:
      val:
        expr: "x"
"""
    engine = _engine_from_spec(spec, tmp_path)
    fragments = list(engine.materialize({"_row_class": "MyRow", "x": "hello"}, 1))
    assert len(fragments) == 1
    assert fragments[0]["val"] == "hello"


def test_when_guard_true_emits_fragment(tmp_path):
    """when: expression that evaluates truthy → fragment is emitted."""
    spec = """
class_derivations:
  MyNode:
    populated_from: MyRow
    when: "source_term_en is not None"
    slot_derivations:
      val:
        expr: "source_term_en"
"""
    engine = _engine_from_spec(spec, tmp_path)
    fragments = list(engine.materialize({"_row_class": "MyRow", "source_term_en": "Board"}, 1))
    assert len(fragments) == 1
    assert fragments[0]["val"] == "Board"


def test_when_guard_false_skips_fragment(tmp_path):
    """when: expression that evaluates falsy → no fragment emitted."""
    spec = """
class_derivations:
  MyNode:
    populated_from: MyRow
    when: "source_term_en is not None"
    slot_derivations:
      val:
        expr: "source_term_en"
"""
    engine = _engine_from_spec(spec, tmp_path)
    fragments = list(engine.materialize({"_row_class": "MyRow", "source_term_en": None}, 1))
    assert fragments == []


def test_when_guard_equality_check(tmp_path):
    """when: can filter to a specific field value — the R4 use case."""
    spec = """
class_derivations:
  SeedEdge:
    populated_from: ByLawDefinedTermRow
    target_type: RELATIONSHIP
    when: "term_en == 'Member'"
    slot_derivations:
      subject:
        expr: "'gckg:Commons:MembersByLaw:DefinedTerm:' + str(term_en)"
      rel_type:
        expr: "'ALIGNS_TO_CLASS'"
      object:
        expr: "'gckg:MemberOfParliament'"
"""
    engine = _engine_from_spec(spec, tmp_path)

    member_row = {"_row_class": "ByLawDefinedTermRow", "term_en": "Member", "term_fr": "député"}
    party_row  = {"_row_class": "ByLawDefinedTermRow", "term_en": "recognized party", "term_fr": "parti reconnu"}

    assert len(list(engine.materialize(member_row, 1))) == 1
    assert len(list(engine.materialize(party_row, 2))) == 0


def test_when_guard_selects_one_of_two_derivations(tmp_path):
    """Two derivations on the same row class with complementary guards each fire once."""
    spec = """
class_derivations:
  TermEdge:
    populated_from: CrossRefRow
    target_type: RELATIONSHIP
    when: "source_term_en is not None"
    slot_derivations:
      subject:
        expr: "'gckg:Term:' + str(source_term_en)"
      object:
        expr: "'gckg:Term:' + str(cited_term_en)"
  ProvisionEdge:
    populated_from: CrossRefRow
    target_type: RELATIONSHIP
    when: "source_term_en is None"
    slot_derivations:
      subject:
        expr: "'gckg:Section:' + str(section_label)"
      object:
        expr: "'gckg:Term:' + str(cited_term_en)"
"""
    engine = _engine_from_spec(spec, tmp_path)

    term_row = {"_row_class": "CrossRefRow", "source_term_en": "Board", "cited_term_en": "Member", "section_label": "1"}
    prov_row = {"_row_class": "CrossRefRow", "source_term_en": None,    "cited_term_en": "Member", "section_label": "1"}

    term_fragments = list(engine.materialize(term_row, 1))
    prov_fragments = list(engine.materialize(prov_row, 2))

    assert len(term_fragments) == 1
    assert term_fragments[0]["subject"] == "gckg:Term:Board"

    assert len(prov_fragments) == 1
    assert prov_fragments[0]["subject"] == "gckg:Section:1"


def test_when_guard_error_skips_fragment(tmp_path):
    """If the when: expression raises, the derivation is skipped rather than crashing."""
    spec = """
class_derivations:
  MyNode:
    populated_from: MyRow
    when: "undefined_name + 1"
    slot_derivations:
      val:
        expr: "'x'"
"""
    engine = _engine_from_spec(spec, tmp_path)
    fragments = list(engine.materialize({"_row_class": "MyRow"}, 1))
    assert fragments == []


def test_when_guard_empty_string_skips_fragment(tmp_path):
    """when: expression that evaluates to empty string is falsy → skip."""
    spec = """
class_derivations:
  MyNode:
    populated_from: MyRow
    when: "field_val"
    slot_derivations:
      val:
        expr: "field_val"
"""
    engine = _engine_from_spec(spec, tmp_path)
    fragments = list(engine.materialize({"_row_class": "MyRow", "field_val": ""}, 1))
    assert fragments == []


def test_when_guard_does_not_affect_other_derivations(tmp_path):
    """A guarded derivation that skips does not suppress unguarded derivations on the same row."""
    spec = """
class_derivations:
  AlwaysEmit:
    populated_from: MyRow
    slot_derivations:
      val:
        expr: "'always'"
  ConditionalEmit:
    populated_from: MyRow
    when: "flag"
    slot_derivations:
      val:
        expr: "'conditional'"
"""
    engine = _engine_from_spec(spec, tmp_path)

    # flag=False → only AlwaysEmit fires
    fragments = list(engine.materialize({"_row_class": "MyRow", "flag": False}, 1))
    assert len(fragments) == 1
    assert fragments[0]["val"] == "always"

    # flag=True → both fire
    fragments = list(engine.materialize({"_row_class": "MyRow", "flag": True}, 2))
    assert len(fragments) == 2


def test_materialize_injects_bronze_reference():
    calls: list[int] = []

    def factory(line_number: int) -> dict:
        calls.append(line_number)
        return {"source": "test", "line_number": line_number}

    engine = YamlMapEngine(BYLAW_MAP, bronze_reference_factory=factory)
    row = {
        "_row_class": "ByLawSectionRow",
        "section_label": "1",
        "text": "",
        "marginal_note": None,
        "heading_lv1": None,
        "heading_lv2": None,
        "heading_lv3": None,
    }
    fragments = list(engine.materialize(row, 99))
    assert calls == [99]
    assert fragments[0]["bronze_reference"]["line_number"] == 99
