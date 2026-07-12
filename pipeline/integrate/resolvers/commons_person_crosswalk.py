"""Build a deterministic Person crosswalk for commons_members ↔ expenditures."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from pipeline.paths import UniversePaths

EXPENDITURE_PERSON_PREFIX = "gckg:Commons:MembersExpenditureReport:Person:"
MEMBERS_PERSON_PREFIX = "gckg:Person:Commons:"

_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize_member_name(name: str) -> str:
    """Match 'Last, First' and 'First Last' via sorted lowercase tokens."""
    cleaned = _NON_WORD.sub(" ", name.strip().lower())
    tokens = [t for t in _WS.split(cleaned) if t]
    return " ".join(sorted(tokens))


def expenditure_person_uri(member_name: str) -> str:
    return f"{EXPENDITURE_PERSON_PREFIX}{member_name}"


def members_person_uri(person_id: str) -> str:
    return f"{MEMBERS_PERSON_PREFIX}{person_id}"


def _iter_bronze_rows(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8") as fin:
        for line in fin:
            line = line.strip()
            if line:
                yield json.loads(line)


def _members_display_name(row: dict) -> str | None:
    first = (row.get("person_official_first_name") or "").strip()
    last = (row.get("person_official_last_name") or "").strip()
    if first and last:
        return f"{first} {last}"
    if last:
        return last
    if first:
        return first
    return None


@dataclass(frozen=True)
class PersonCrosswalk:
    """Maps expenditure Person stubs to canonical members Person URIs."""

    uuid_to_person_id: dict[str, str]
    uuid_to_member_name: dict[str, str]
    normalized_name_to_person_id: dict[str, str]
    expenditure_uri_to_canonical: dict[str, str]
    ambiguous_uuids: frozenset[str] = frozenset()
    ambiguous_names: frozenset[str] = frozenset()
    unresolved_uuids: frozenset[str] = frozenset()

    @classmethod
    def from_bronze(
        cls,
        members_bronze: Path,
        expenditures_bronze: Path,
    ) -> PersonCrosswalk:
        name_to_person_ids: dict[str, set[str]] = {}
        for row in _iter_bronze_rows(members_bronze):
            person_id = row.get("person_id")
            if not person_id:
                continue
            display = _members_display_name(row)
            if not display:
                continue
            norm = normalize_member_name(display)
            name_to_person_ids.setdefault(norm, set()).add(str(person_id))

        normalized_name_to_person_id: dict[str, str] = {}
        ambiguous_names: set[str] = set()
        for norm, person_ids in sorted(name_to_person_ids.items()):
            if len(person_ids) == 1:
                normalized_name_to_person_id[norm] = next(iter(person_ids))
            else:
                ambiguous_names.add(norm)

        uuid_to_names: dict[str, set[str]] = {}
        for row in _iter_bronze_rows(expenditures_bronze):
            uuid = row.get("member_disclosure_uuid")
            member_name = row.get("member_name")
            if not uuid or not member_name:
                continue
            uuid_to_names.setdefault(str(uuid), set()).add(str(member_name))

        uuid_to_person_id: dict[str, str] = {}
        uuid_to_member_name: dict[str, str] = {}
        ambiguous_uuids: set[str] = set()
        unresolved_uuids: set[str] = set()
        for uuid, names in sorted(uuid_to_names.items()):
            if len(names) != 1:
                ambiguous_uuids.add(uuid)
                continue
            member_name = next(iter(names))
            norm = normalize_member_name(member_name)
            person_id = normalized_name_to_person_id.get(norm)
            if person_id is None:
                unresolved_uuids.add(uuid)
                continue
            uuid_to_person_id[uuid] = person_id
            uuid_to_member_name[uuid] = member_name

        expenditure_uri_to_canonical = _build_expenditure_uri_map(
            uuid_to_person_id=uuid_to_person_id,
            uuid_to_member_name=uuid_to_member_name,
        )
        return cls(
            uuid_to_person_id=uuid_to_person_id,
            uuid_to_member_name=uuid_to_member_name,
            normalized_name_to_person_id=normalized_name_to_person_id,
            expenditure_uri_to_canonical=expenditure_uri_to_canonical,
            ambiguous_uuids=frozenset(ambiguous_uuids),
            ambiguous_names=frozenset(ambiguous_names),
            unresolved_uuids=frozenset(unresolved_uuids),
        )

    @classmethod
    def from_tsv(cls, path: Path) -> PersonCrosswalk:
        uuid_to_person_id: dict[str, str] = {}
        uuid_to_member_name: dict[str, str] = {}
        normalized_name_to_person_id: dict[str, str] = {}

        with path.open(encoding="utf-8", newline="") as fin:
            reader = csv.DictReader(fin, delimiter="\t")
            if reader.fieldnames is None:
                raise ValueError(f"empty crosswalk TSV: {path}")
            for row in reader:
                uuid = (row.get("member_disclosure_uuid") or "").strip()
                person_id = (row.get("person_id") or "").strip()
                member_name = (row.get("member_name") or "").strip()
                if not uuid or not person_id:
                    continue
                uuid_to_person_id[uuid] = person_id
                if member_name:
                    uuid_to_member_name[uuid] = member_name
                    norm = normalize_member_name(member_name)
                    normalized_name_to_person_id.setdefault(norm, person_id)

        expenditure_uri_to_canonical = _build_expenditure_uri_map(
            uuid_to_person_id=uuid_to_person_id,
            uuid_to_member_name=uuid_to_member_name,
        )
        return cls(
            uuid_to_person_id=uuid_to_person_id,
            uuid_to_member_name=uuid_to_member_name,
            normalized_name_to_person_id=normalized_name_to_person_id,
            expenditure_uri_to_canonical=expenditure_uri_to_canonical,
        )

    def write_tsv(self, path: Path) -> None:
        """Serialize uuid → person_id rows (sorted) for checked-in crosswalks."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fout:
            writer = csv.writer(fout, delimiter="\t", lineterminator="\n")
            writer.writerow(
                ["member_disclosure_uuid", "person_id", "member_name", "normalized_name"]
            )
            for uuid, person_id in sorted(self.uuid_to_person_id.items()):
                member_name = self.uuid_to_member_name.get(uuid, "")
                norm = normalize_member_name(member_name) if member_name else ""
                writer.writerow([uuid, person_id, member_name, norm])

    @property
    def stats(self) -> dict[str, int]:
        return {
            "uuid_mappings": len(self.uuid_to_person_id),
            "name_mappings": len(self.normalized_name_to_person_id),
            "expenditure_uri_mappings": len(self.expenditure_uri_to_canonical),
            "ambiguous_uuids": len(self.ambiguous_uuids),
            "ambiguous_names": len(self.ambiguous_names),
            "unresolved_uuids": len(self.unresolved_uuids),
        }


def _build_expenditure_uri_map(
    *,
    uuid_to_person_id: dict[str, str],
    uuid_to_member_name: dict[str, str],
) -> dict[str, str]:
    uri_map: dict[str, str] = {}
    for uuid, person_id in uuid_to_person_id.items():
        member_name = uuid_to_member_name.get(uuid)
        if not member_name:
            continue
        uri_map[expenditure_person_uri(member_name)] = members_person_uri(person_id)
    return uri_map


def discover_bronze_records(
    inputs: tuple,
    *,
    paths: UniversePaths,
) -> tuple[Path | None, Path | None]:
    """Resolve members/expenditures Bronze paths from Silver run manifests."""
    members_path: Path | None = None
    expenditures_path: Path | None = None

    for inp in sorted(inputs, key=lambda i: (i.source, i.silver_run_id)):
        manifest_path = paths.silver_manifest(inp.source, inp.silver_run_id)
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        bronze_run_id = manifest.get("bronze_run_id")
        if not bronze_run_id and manifest.get("inputs"):
            bronze_run_id = manifest["inputs"][0].get("bronze_run_id")
        if not bronze_run_id:
            continue
        records = paths.bronze_records(inp.source, bronze_run_id)
        if inp.source == "commons_members" and records.exists():
            members_path = records
        elif inp.source == "commons_members_expenditures" and records.exists():
            expenditures_path = records

    return members_path, expenditures_path
