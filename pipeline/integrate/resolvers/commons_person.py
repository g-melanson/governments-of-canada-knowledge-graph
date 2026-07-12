"""Commons members ↔ expenditures Person entity resolution."""

from __future__ import annotations

import logging
from pathlib import Path

from pipeline.integrate.context import IntegrateContext
from pipeline.integrate.errors import IntegrateError
from pipeline.integrate.resolvers.base import EntityResolver
from pipeline.integrate.resolvers.commons_person_crosswalk import (
    EXPENDITURE_PERSON_PREFIX,
    PersonCrosswalk,
    discover_bronze_records,
    members_person_uri,
    normalize_member_name,
)

log = logging.getLogger(__name__)


class CommonsPersonResolver(EntityResolver):
    """Map expenditure Person stubs onto canonical members Person URIs."""

    def __init__(self, crosswalk: PersonCrosswalk) -> None:
        self._crosswalk = crosswalk
        self._uri_map = crosswalk.expenditure_uri_to_canonical
        self._name_map = crosswalk.normalized_name_to_person_id

    def canonical_id(self, node_id: str, *, node_type: str | None = None) -> str:
        if not node_id.startswith(EXPENDITURE_PERSON_PREFIX):
            return node_id

        mapped = self._uri_map.get(node_id)
        if mapped:
            return mapped

        member_name = node_id[len(EXPENDITURE_PERSON_PREFIX) :]
        norm = normalize_member_name(member_name)
        person_id = self._name_map.get(norm)
        if person_id:
            return members_person_uri(person_id)

        return node_id

    @property
    def crosswalk(self) -> PersonCrosswalk:
        return self._crosswalk


def get_resolver(ctx: IntegrateContext) -> EntityResolver:
    """Factory for `--resolver integrate.resolvers.commons_person.get_resolver`."""
    crosswalk = _load_crosswalk(ctx)
    stats = crosswalk.stats
    log.info(
        "commons_person_crosswalk uuid=%s uri=%s ambiguous_uuids=%s unresolved_uuids=%s",
        stats["uuid_mappings"],
        stats["expenditure_uri_mappings"],
        stats.get("ambiguous_uuids", 0),
        stats.get("unresolved_uuids", 0),
    )
    return CommonsPersonResolver(crosswalk)


def _load_crosswalk(ctx: IntegrateContext) -> PersonCrosswalk:
    if ctx.person_crosswalk_tsv is not None:
        return PersonCrosswalk.from_tsv(ctx.person_crosswalk_tsv)

    members_bronze = ctx.members_bronze_path
    expenditures_bronze = ctx.expenditures_bronze_path

    if members_bronze is None or expenditures_bronze is None:
        discovered_members, discovered_expenditures = discover_bronze_records(
            ctx.sorted_inputs(),
            paths=ctx.paths,
        )
        members_bronze = members_bronze or discovered_members
        expenditures_bronze = expenditures_bronze or discovered_expenditures

    if members_bronze is None or expenditures_bronze is None:
        raise IntegrateError(
            "commons_person resolver requires --person-crosswalk-tsv, or "
            "--members-bronze and --expenditures-bronze, or integrate inputs "
            "whose Silver manifests reference both commons_members and "
            "commons_members_expenditures Bronze runs"
        )

    for label, path in (
        ("members", members_bronze),
        ("expenditures", expenditures_bronze),
    ):
        if not path.exists():
            raise IntegrateError(f"commons_person resolver: {label} bronze not found: {path}")

    return PersonCrosswalk.from_bronze(members_bronze, expenditures_bronze)
