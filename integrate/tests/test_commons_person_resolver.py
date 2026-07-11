from __future__ import annotations

from pathlib import Path

import pytest

from integrate.context import IntegrateContext, SilverInput
from integrate.resolvers.commons_person import CommonsPersonResolver, get_resolver
from integrate.resolvers.commons_person_crosswalk import (
    PersonCrosswalk,
    expenditure_person_uri,
    members_person_uri,
    normalize_member_name,
)

FIXTURES = Path(__file__).parent / "fixtures"
MEMBERS_BRONZE = FIXTURES / "members_bronze.jsonl"
EXPENDITURES_BRONZE = FIXTURES / "expenditures_bronze.jsonl"


def test_normalize_member_name_last_first_and_first_last():
    assert normalize_member_name("Aboultaif, Ziad") == normalize_member_name("Ziad Aboultaif")


def test_crosswalk_from_bronze_maps_expenditure_person_uris():
    crosswalk = PersonCrosswalk.from_bronze(MEMBERS_BRONZE, EXPENDITURES_BRONZE)
    assert crosswalk.uuid_to_person_id["3283699b-5c58-486f-a315-a3f5e175d175"] == "89156"
    assert crosswalk.expenditure_uri_to_canonical[
        expenditure_person_uri("Aboultaif, Ziad")
    ] == members_person_uri("89156")


def test_resolver_maps_expenditure_person_id():
    crosswalk = PersonCrosswalk.from_bronze(MEMBERS_BRONZE, EXPENDITURES_BRONZE)
    resolver = CommonsPersonResolver(crosswalk)
    stub = expenditure_person_uri("Aboultaif, Ziad")
    assert resolver.canonical_id(stub, node_type="Person") == members_person_uri("89156")
    assert resolver.resolve_endpoint(stub) == members_person_uri("89156")


def test_resolver_leaves_members_person_unchanged():
    crosswalk = PersonCrosswalk.from_bronze(MEMBERS_BRONZE, EXPENDITURES_BRONZE)
    resolver = CommonsPersonResolver(crosswalk)
    canonical = members_person_uri("89156")
    assert resolver.canonical_id(canonical, node_type="Person") == canonical


def test_resolver_name_fallback_when_uri_not_preindexed():
    crosswalk = PersonCrosswalk.from_bronze(MEMBERS_BRONZE, EXPENDITURES_BRONZE)
    resolver = CommonsPersonResolver(crosswalk)
    # Same normalized name, different punctuation/spacing in URI suffix.
    stub = expenditure_person_uri("Ziad  Aboultaif")
    assert resolver.canonical_id(stub) == members_person_uri("89156")


def test_crosswalk_tsv_roundtrip(tmp_path: Path):
    source = PersonCrosswalk.from_bronze(MEMBERS_BRONZE, EXPENDITURES_BRONZE)
    tsv_path = tmp_path / "crosswalk.tsv"
    source.write_tsv(tsv_path)
    loaded = PersonCrosswalk.from_tsv(tsv_path)
    assert loaded.uuid_to_person_id == source.uuid_to_person_id
    assert loaded.expenditure_uri_to_canonical == source.expenditure_uri_to_canonical


def test_get_resolver_from_explicit_bronze_paths():
    ctx = IntegrateContext(
        run_id="test",
        inputs=(),
        members_bronze_path=MEMBERS_BRONZE,
        expenditures_bronze_path=EXPENDITURES_BRONZE,
    )
    resolver = get_resolver(ctx)
    stub = expenditure_person_uri("Smith, Jane")
    assert resolver.canonical_id(stub) == members_person_uri("12345")


def test_get_resolver_requires_crosswalk_source():
    ctx = IntegrateContext(run_id="test", inputs=())
    with pytest.raises(Exception, match="commons_person resolver requires"):
        get_resolver(ctx)


def test_ambiguous_uuid_excluded(tmp_path: Path):
    members = tmp_path / "members.jsonl"
    members.write_text(
        '{"person_id": "1", "person_official_first_name": "A", "person_official_last_name": "One"}\n',
        encoding="utf-8",
    )
    expenditures = tmp_path / "expenditures.jsonl"
    expenditures.write_text(
        "\n".join(
            [
                '{"member_disclosure_uuid": "uuid-1", "member_name": "One, A"}',
                '{"member_disclosure_uuid": "uuid-1", "member_name": "Different, Name"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    crosswalk = PersonCrosswalk.from_bronze(members, expenditures)
    assert "uuid-1" in crosswalk.ambiguous_uuids
    assert "uuid-1" not in crosswalk.uuid_to_person_id
