# Execution plan — Stage 4 Integrate (Silver merged)

**Stage 4** merges per-source **Silver graph fragments** (`silver/{source}/{run_id}/fragments.jsonl`) into a single reconciled graph under **`silver/merged/{run_id}/`**. It deduplicates nodes and edges by GCKG URI, reconciles attributes, preserves provenance, and (where rules exist) resolves the same real-world entity that appears under different identifiers across sources.

**Implementation reality (read first):** `integrate/` is **implemented**. The package provides CLI, runner, engine, context, errors, and pluggable resolvers (`identity`, `commons_person`). It merges multiple Silver runs into `silver/merged/{run_id}/` with deterministic output.

**Overview:** see [`README.md`](README.md) for current status.

**Three sources** already materialize Silver:

| Source | Scale (latest run) | Notes |
|--------|-------------------|-------|
| `commons_members` | ~30 fragments / MP row | Legacy `RELATIONSHIP` + `rel_type` in older runs; named `PersonHasRoleMemberOfParliament` in newer runs |
| `commons_members_bylaw` | ~1k fragments | Named reified triples (`ByLawHasPartByLawSection`, …) |
| `commons_members_expenditures` | **~2M fragments** | Named reified triples; some nodes have `id: null` (Stage 3 bug — quarantine on ingest to Integrate) |

A **Neo4j dev shortcut** (`tools/neo4j_import/preprocess_silver.py`) loads single-source Silver directly and **bypasses Integrate**. That path is acceptable for per-source dev loads; multi-source graphs and production rebuilds require `silver/merged/`.

**M4 deliverable:** merge platform + exact-URI reconciliation + **Stage-5-ready output shape** (preserve reified `@type`, domain predicate strings, edge slots). Cross-source `Person` resolution (`commons_members` ↔ `commons_members_expenditures`) ships as an optional resolver in Phase 9; the hook is exercised by synthetic fixtures in Phase 7.

**Pilot inputs:** `commons_members` + `commons_members_expenditures` (+ optionally `commons_members_bylaw`, which does not overlap on Person URIs).

Implement files **top to bottom**. Each section: **what it does** → **exact code or schema**.

---

## Implementation status (actual)

| Area | State |
|------|-------|
| `integrate/` package (CLI, runner, engine, context, errors) | **Done** |
| Node merge by GCKG URI | **Done** |
| Edge dedupe by reified `id` or `( @type, subject, predicate, object )` | **Done** |
| Cross-source entity resolution | **Done** — `CommonsPersonResolver` for members ↔ expenditures; identity default |
| `silver/merged/{run_id}/` output + manifest | **Done** |
| Resolution report (merges/conflicts/alternates) | **Done** |
| Tests (`integrate/tests/`) | **Done** — `test_commons_person_resolver.py` + fixtures |
| Packaging (`integrate` console script, `testpaths`) | **Done** in `pyproject.toml` |
| Production-scale integration test in CI | **Not started** |

**Carried-over issues from Stage 3 that Stage 4 must absorb (do not fix in Integrate — quarantine and report):**

- **Heterogeneous edge shapes:** older `commons_members` runs emit `@type: "RELATIONSHIP"` + `rel_type`; newer runs and all expenditures/bylaw runs emit **named reified triple classes** with `predicate` already set. Integrate normalizes legacy `rel_type` → `predicate` only when `predicate` is absent. It does **not** rewrite predicate case — domain model uses uppercase constants (`HAS_ROLE`, `CLAIM`, …).
- **Null node ids:** `TravelExpenseClaim` and some `HospitalityExpenseClaim` fragments arrive with `"id": null`. Route to `quarantine.jsonl`; do not merge or invent ids.
- **Duplicate Person namespaces:** `gckg:Person:Commons:{person_id}` (members) vs `gckg:Commons:MembersExpenditureReport:Person:{member_name}` (expenditures). Identity merge leaves both until a resolver collapses them (Phase 9).
- **MP URI embeds raw `from_date_time`:** treat URIs as opaque identity strings; do not re-parse.

---

## Prerequisites

| Requirement | Status |
|-------------|--------|
| Silver layout | Done — `silver/{source}/{run_id}/fragments.jsonl` + `quarantine.jsonl` + `manifest.json` |
| At least one source materializes Silver | Done — `commons_members`, `commons_members_bylaw`, `commons_members_expenditures` |
| Silver fragment shape documented | Done — see §0 (heterogeneous; classification rule is normative) |
| Domain model with named triple classes | Done — `PersonHasRoleMemberOfParliament`, expenditure claim triples, bylaw triples |
| Two sources for real cross-source ER | **Met** — members + expenditures (Person URIs differ; resolver deferred to Phase 9) |

**Handoff contract:** Integrate reads **Silver only** — never Bronze, staging, or raw publishers. It consumes one or more `(source, silver_run_id)` inputs and writes one merged run.

```text
silver/{source_a}/{run_id_a}/fragments.jsonl  ─┐
silver/{source_b}/{run_id_b}/fragments.jsonl  ─┼─►  Integrate  ─►  silver/merged/{run_id}/nodes.jsonl
silver/{source_c}/{run_id_c}/fragments.jsonl  ─┘                   silver/merged/{run_id}/edges.jsonl
                                                                   silver/merged/{run_id}/manifest.json
                                                                   silver/merged/{run_id}/resolution_report.json
```

Align `--run-id` with prior stages when you want matching directory names (same pattern as `validate`/`transforms`).

---

## Design decisions (locked for M4)

1. **Integrate is the first cross-source stage.** Output lands under `silver/merged/{run_id}/` — a sibling of the per-source `silver/{source}/…` trees, not under any single source.
2. **Node merge key = canonical GCKG URI.** Apply `EntityResolver` to each node `id`. Two fragments whose ids resolve to the same canonical id are merged.
3. **Edge merge key = reified edge `id` when present; else `( @type, subject, predicate, object )`.** Named reified triples from Stage 3 carry a unique edge `id`. Legacy `RELATIONSHIP` rows without `id` dedupe on the normalized triple (+ `@type`). Endpoint ids are resolved before grouping.
4. **Preserve reified `@type` and edge slots for Stage 5.** Merged edges keep their LinkML relationship class as `@type` (e.g. `PersonHasRoleMemberOfParliament`), not a generic `RELATIONSHIP`. Extra slots (`expense_date`, `start_date`, …) are merged with the same first-non-empty rule as nodes.
5. **Predicate strings match the domain model.** Copy `predicate` as-is. When only `rel_type` is present (legacy Silver), promote it to `predicate` **without case conversion** (`HAS_ROLE` stays `HAS_ROLE`).
6. **Cross-source entity resolution is rule-driven.** Default resolver is identity. Phase 9 adds `commons_person` resolver for members ↔ expenditures Person stubs.
7. **Deterministic and idempotent.** Stable sorted input order; byte-identical output on re-run.
8. **Provenance is preserved.** `bronze_reference` → `bronze_references` (sorted union); contributing `{source, silver_run_id}` pairs recorded under `sources`.
9. **Nodes and edges in separate files.** `nodes.jsonl` and `edges.jsonl` for Stage 5 validation.
10. **No Gold validation in M4.** Shape normalization only; domain gate is Stage 5.
11. **Invalid fragments quarantine; do not fail the whole run.** Null node ids, malformed edges, and `@type` conflicts on the same canonical node id go to output `quarantine.jsonl` (and `@type` conflicts also to `conflicts.jsonl`). The merge continues.
12. **Memory scales with distinct entities, not fragment rows.** Acceptable for members + bylaw; full members + expenditures (~2M input fragments) may require external/disk-backed merge (§13) — profile before production merge.

---

## Target semantics — merge and resolution

### Node merge

Group node fragments by **canonical id** (`EntityResolver.canonical_id(id, node_type=@type)`). Skip fragments with missing/null `id` → quarantine.

| Field | Merge rule |
|-------|------------|
| `id` | canonical id (post-resolution) |
| `@type` | must agree within a group; mismatch → **conflict** → quarantine (§6) |
| `name`, `labels` | `name`: first non-empty by stable input order; record alternates in `resolution_report.json`. `labels`: set-union (sorted) |
| **All other slots** (`total`, `start_date`, `description`, …) | first non-empty by stable input order; if two non-empty values differ, keep first and record alternates in `resolution_report.json` — do **not** quarantine attribute disagreements in M4 |
| `bronze_reference` | becomes `bronze_references`: sorted, de-duplicated list |
| `sources` | sorted set of `{source, silver_run_id}` |

Reserved keys (never copied as mergeable attrs): `@type`, `id`, `subject`, `object`, `predicate`, `rel_type`, `bronze_reference`, `bronze_references`, `sources`.

### Edge merge

1. Classify as edge (§0).
2. Normalize to `(subject, predicate, object)` — promote `rel_type` → `predicate` when needed; preserve `@type` and all other slots.
3. Resolve `subject` and `object` through `EntityResolver.resolve_endpoint`.
4. Group by merge key: **`id` if present**, else **`( @type, subject, predicate, object )`** after resolution.
5. Merge `bronze_references`, `sources`, and non-reserved slots (same first-non-empty rule as nodes).

### Entity resolution

**Phase 7 (M4):** `IdentityResolver` — exact URI only. Exercised by merging duplicate Silver runs and synthetic two-source fixtures.

**Phase 9 (first real rule):** `commons_person` resolver — collapse expenditure Person stubs onto members Person ids.

| Stub (expenditures) | Canonical (members) | Key |
|---------------------|-------------------|-----|
| `gckg:Commons:MembersExpenditureReport:Person:{member_name}` | `gckg:Person:Commons:{person_id}` | Deterministic crosswalk built from Bronze: match `member_disclosure_uuid` → `person_id` via members Bronze, or normalized name fallback |

Name normalization for fallback: lowercase, strip punctuation, reorder `"Last, First"` → `"first last"`. No fuzzy matching in M4.

| Future rule | Example |
|-------------|---------|
| Same `Agent` across claim types | `"Acme Corp"` under contract vs hospitality URI templates |
| Same `PoliticalParty` by label | deferred |
| `open_canada_federal_election_contribution` | deferred until Stages 1–3 |

---

## Work breakdown

| Phase | Work | Status | Output |
|-------|------|--------|--------|
| **0 — Silver contract** | Lock heterogeneous fragment classification + merge keys (§0) | Done | — |
| **1 — Platform** | `integrate/` package: context, errors, engine, runner, CLI | **Done** | `python -m integrate run …` |
| **2 — Node merge** | Group by canonical id; merge attrs + provenance; quarantine null ids | **Done** | `silver/merged/{run_id}/nodes.jsonl` |
| **3 — Edge normalize + dedupe** | Legacy `rel_type`→`predicate`; preserve reified `@type` + slots; dedupe by edge `id` or triple | **Done** | `silver/merged/{run_id}/edges.jsonl` |
| **4 — Resolver hook** | `IdentityResolver` default + interface for rule-based resolvers | **Done** | pluggable via `--resolver` |
| **5 — Manifest + report** | `manifest.json` + `resolution_report.json` + `quarantine.jsonl` | **Done** | all three |
| **6 — Pilot run** | Merge `commons_members` + `commons_members_expenditures` (+ bylaw) | **Done** | `silver/merged/{run_id}/` |
| **7 — Tests** | Resolver tests incl. synthetic 2-source crosswalk | **Done** | `integrate/tests/` |
| **8 — Packaging** | `integrate` in `pyproject.toml`, console script, `testpaths` | **Done** | `python -m integrate` / `integrate` |
| **9 — Cross-source ER** | `commons_person` resolver (members ↔ expenditures) | **Done** | `integrate/resolvers/commons_person.py` |

---

## 0. Silver input contract

Stage 3 writes one JSON object per line to `fragments.jsonl`. **Shape varies by source and by transform generation.** Integrate must accept all variants below; Stage 3 is **not** frozen for Integrate's benefit — classification and normalization happen here.

### 0.1 Per-source examples

**`commons_members` — nodes**

```json
{"@type": "Person", "id": "gckg:Person:Commons:89156", "name": "Ziad Aboultaif", "bronze_reference": {"source": "commons_members", "bronze_run_id": "2026-07-03T151251Z", "line_number": 1}}
{"@type": "MemberOfParliament", "id": "gckg:MemberOfParliament:89156:2025-04-28T00:00:00Z", "start_date": "2025-04-28T00:00:00Z", "end_date": "None", "bronze_reference": {"source": "commons_members", "bronze_run_id": "2026-07-03T151251Z", "line_number": 1}}
```

**`commons_members` — edges (two generations)**

```json
{"@type": "RELATIONSHIP", "subject": "gckg:Person:Commons:89156", "rel_type": "HAS_ROLE", "object": "gckg:MemberOfParliament:89156:2025-04-28T00:00:00Z", "bronze_reference": {"source": "commons_members", "bronze_run_id": "2026-06-24T172758Z", "line_number": 1}}
{"@type": "PersonHasRoleMemberOfParliament", "subject": "gckg:Person:Commons:89156", "predicate": "HAS_ROLE", "object": "gckg:MemberOfParliament:89156:2025-04-28T00:00:00Z", "bronze_reference": {"source": "commons_members", "bronze_run_id": "2026-07-03T151251Z", "line_number": 1}}
```

**`commons_members_bylaw` — reified edge (also has edge `id`)**

```json
{"@type": "ByLawHasPartByLawSection", "id": "gckg:Commons:MembersByLaw:10000:HAS_PART:Section:1", "subject": "gckg:Commons:MembersByLaw:10000", "predicate": "HAS_PART", "object": "gckg:Commons:MembersByLaw:Section:1", "bronze_reference": {"source": "commons_members_bylaw", "bronze_run_id": "2026-07-03T151251Z", "line_number": 2}}
```

**`commons_members_expenditures` — node + reified edge**

```json
{"@type": "Person", "id": "gckg:Commons:MembersExpenditureReport:Person:Aboultaif, Ziad", "name": "Aboultaif, Ziad", "bronze_reference": {"source": "commons_members_expenditures", "bronze_run_id": "2026-07-07T221600Z", "line_number": 1}}
{"@type": "MembersExpenditureReportHasContractExpenseClaim", "id": "gckg:Commons:MembersExpenditureReportHasContractExpenseClaim:3283699b-5c58-486f-a315-a3f5e175d175:2024:2:0", "subject": "gckg:Commons:MembersExpenditureReport:3283699b-5c58-486f-a315-a3f5e175d175:2024:2", "predicate": "CLAIM", "object": "gckg:Commons:ContractExpenseClaim:3283699b-5c58-486f-a315-a3f5e175d175:2024:2:0", "expense_date": "2023/01/05", "bronze_reference": {"source": "commons_members_expenditures", "bronze_run_id": "2026-07-07T221600Z", "line_number": 38}}
```

**Known bad input (Stage 3 bug — quarantine, do not merge)**

```json
{"@type": "TravelExpenseClaim", "id": null, "total": 324.26, "bronze_reference": {"source": "commons_members_expenditures", "bronze_run_id": "2026-07-07T221600Z", "line_number": 2}}
```

### 0.2 Classification (normative — implement once in `integrate/engine.py`)

```python
def is_edge(fragment: dict) -> bool:
    """Edge iff both subject and object keys are present (values may be resolved later)."""
    return "subject" in fragment and "object" in fragment
```

- Check **`is_edge` first**. Reified triples carry both `id` and `subject`/`object`; they are edges, not nodes.
- Otherwise the fragment is a **node** iff `id` is a non-empty string.
- Otherwise → **quarantine** (`reason: "unclassifiable_fragment"`).

### 0.3 Predicate normalization

| Input | Output `predicate` |
|-------|---------------------|
| `predicate` present | use as-is (e.g. `HAS_ROLE`, `CLAIM`, `HAS_PART`) |
| `rel_type` only (legacy) | copy to `predicate` unchanged |
| neither present | quarantine edge (`reason: "missing_predicate"`) |

**Do not** map `HAS_ROLE` → `hasRole`. `domain_model/schema.yaml` validates `equals_string: HAS_ROLE`.

### 0.4 Merge keys (summary)

| Kind | Key |
|------|-----|
| Node | `EntityResolver.canonical_id(id, node_type=@type)` |
| Edge (has `id`) | edge `id` (opaque; do not rewrite when endpoints resolve) |
| Edge (no `id`) | `( @type, subject, predicate, object )` after endpoint resolution |

### 0.5 Merged output shape (Stage 5 handoff)

**Node row** — same `@type` as input; `bronze_reference` promoted to `bronze_references` list; plus `sources`:

```json
{"@type": "ContractExpenseClaim", "id": "gckg:Commons:ContractExpenseClaim:…", "total": 1500.0, "description": "…", "bronze_references": [{"source": "commons_members_expenditures", "bronze_run_id": "…", "line_number": 38}], "sources": [{"source": "commons_members_expenditures", "silver_run_id": "2026-07-08T024008Z"}]}
```

**Edge row** — preserve reified `@type` and edge slots; always include `subject`, `predicate`, `object`:

```json
{"@type": "PersonHasRoleMemberOfParliament", "id": "gckg:…", "subject": "gckg:Person:Commons:89156", "predicate": "HAS_ROLE", "object": "gckg:MemberOfParliament:89156:2025-04-28T00:00:00Z", "bronze_references": […], "sources": […]}
```

Legacy `RELATIONSHIP` rows without edge `id` may remain `@type: "RELATIONSHIP"` in output until Stage 3 re-materializes them as named triples.

---

## 1. Package manifest

**What:** Register the `integrate` package, console script, and tests.

**File:** `pyproject.toml` — **already present**; verify:

```toml
[project.scripts]
integrate = "integrate.cli:main"

[tool.setuptools.packages.find]
include = ["ingest*", "validate*", "transforms*", "integrate*"]

[tool.pytest.ini_options]
testpaths = ["ingest/tests", "validate/tests", "transforms/tests", "integrate/tests"]
```

Integrate has **no new third-party dependency** — pure stdlib (`json`, `pathlib`, `dataclasses`).

---

## 2. Errors

**File:** `integrate/errors.py`

```python
"""Typed exceptions for Stage 4 integrate."""


class IntegrateError(Exception):
    """Base class for integrate-stage failures."""


class SilverInputError(IntegrateError):
    """A Silver fragments file or manifest is missing or unreadable."""


class FragmentShapeError(IntegrateError):
    """A fragment cannot be classified or normalized (handled → quarantine in runner)."""


class MergeConflictError(IntegrateError):
    """Same canonical node id resolves to incompatible @type values."""


class EmptyMergeError(IntegrateError):
    """No nodes or edges survived integration; merged output would be empty."""
```

Quarantine-worthy conditions (`FragmentShapeError`, null id, bad edge) are **caught in the runner** and appended to `quarantine.jsonl` — they do not abort the run unless every fragment quarantines.

---

## 3. Integrate context

**What:** Immutable per-run paths and the list of inputs. Mirrors `TransformContext`.

**File:** `integrate/context.py`

```python
"""Immutable per-run settings for Stage 4 integrate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SilverInput:
    source: str
    silver_run_id: str

    def fragments_path(self, silver_root: Path) -> Path:
        return silver_root / self.source / self.silver_run_id / "fragments.jsonl"

    def manifest_path(self, silver_root: Path) -> Path:
        return silver_root / self.source / self.silver_run_id / "manifest.json"


@dataclass(frozen=True)
class IntegrateContext:
    run_id: str
    inputs: tuple[SilverInput, ...]
    silver_root: Path = Path("silver")
    resolver: str = "integrate.resolvers.identity.get_resolver"

    @property
    def merged_dir(self) -> Path:
        return self.silver_root / "merged" / self.run_id

    @property
    def nodes_path(self) -> Path:
        return self.merged_dir / "nodes.jsonl"

    @property
    def edges_path(self) -> Path:
        return self.merged_dir / "edges.jsonl"

    @property
    def manifest_path(self) -> Path:
        return self.merged_dir / "manifest.json"

    @property
    def resolution_report_path(self) -> Path:
        return self.merged_dir / "resolution_report.json"

    @property
    def quarantine_path(self) -> Path:
        return self.merged_dir / "quarantine.jsonl"

    def sorted_inputs(self) -> tuple[SilverInput, ...]:
        return tuple(sorted(self.inputs, key=lambda i: (i.source, i.silver_run_id)))
```

---

## 4. Resolver hook

**What:** Map node and edge endpoint ids to **canonical ids**. Default is identity. Phase 9 adds members ↔ expenditures Person resolution.

**File:** `integrate/resolvers/base.py`

```python
"""Entity-resolution interface for Stage 4."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EntityResolver(ABC):
    @abstractmethod
    def canonical_id(self, node_id: str, *, node_type: str | None = None) -> str:
        """Return the canonical GCKG URI for a node id."""

    def resolve_endpoint(self, endpoint_id: str, *, node_type: str | None = None) -> str:
        return self.canonical_id(endpoint_id, node_type=node_type)
```

**File:** `integrate/resolvers/identity.py`

```python
"""Default resolver: every id maps to itself (exact-URI merge only)."""

from __future__ import annotations

from integrate.resolvers.base import EntityResolver


class IdentityResolver(EntityResolver):
    def canonical_id(self, node_id: str, *, node_type: str | None = None) -> str:
        return node_id


def get_resolver() -> EntityResolver:
    return IdentityResolver()
```

**Phase 9 — `integrate/resolvers/commons_person.py` (sketch, not M4):**

- Build a deterministic crosswalk at resolver init from configured Bronze paths (or a checked-in TSV derived from members + expenditures Bronze).
- Primary key: `member_disclosure_uuid` → `person_id` where both appear in members Bronze.
- Fallback: normalized name match between expenditure `member_name` and members `Person.name`.
- Map `gckg:Commons:MembersExpenditureReport:Person:*` → `gckg:Person:Commons:{person_id}`.
- Must be **pure and reproducible** — no network, no LLM matching.

Point `--resolver integrate.resolvers.commons_person.get_resolver` when ready.

---

## 5. Engine — read, classify, normalize, merge

**What:** Stream Silver fragments, classify, normalize predicates, accumulate merged nodes/edges, track alternates for the resolution report.

**File:** `integrate/engine.py`

```python
"""Merge engine for Stage 4 integrate."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from integrate.errors import FragmentShapeError, MergeConflictError, SilverInputError
from integrate.resolvers.base import EntityResolver

RESERVED_NODE_KEYS = frozenset({
    "@type", "id", "subject", "object", "predicate", "rel_type",
    "bronze_reference", "bronze_references", "sources",
})
RESERVED_EDGE_KEYS = RESERVED_NODE_KEYS  # edges use the same reserved set


@dataclass
class MergeSummary:
    input_fragment_count: int = 0
    input_node_count: int = 0
    input_edge_count: int = 0
    merged_node_count: int = 0
    merged_edge_count: int = 0
    node_merges: int = 0
    edge_merges: int = 0
    conflicts: int = 0
    quarantined: int = 0


def iter_fragments(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    if not path.exists():
        raise SilverInputError(f"Silver fragments not found: {path}")
    with path.open(encoding="utf-8") as fin:
        for line_number, line in enumerate(fin, start=1):
            line = line.strip()
            if not line:
                continue
            yield line_number, json.loads(line)


def is_edge(fragment: dict[str, Any]) -> bool:
    return "subject" in fragment and "object" in fragment


def normalize_predicate(fragment: dict[str, Any]) -> str:
    predicate = fragment.get("predicate")
    if predicate:
        return str(predicate)
    rel_type = fragment.get("rel_type")
    if rel_type:
        return str(rel_type)
    raise FragmentShapeError(f"edge missing predicate and rel_type: {fragment}")


def normalize_edge_endpoints(fragment: dict[str, Any]) -> tuple[str, str, str]:
    subject = fragment.get("subject")
    obj = fragment.get("object")
    predicate = normalize_predicate(fragment)
    if not (subject and obj):
        raise FragmentShapeError(f"malformed edge endpoints: {fragment}")
    return str(subject), predicate, str(obj)


def edge_merge_key(
    fragment: dict[str, Any], subject: str, predicate: str, obj: str
) -> tuple:
    edge_id = fragment.get("id")
    if edge_id:
        return ("id", str(edge_id))
    return ("triple", fragment.get("@type") or "RELATIONSHIP", subject, predicate, obj)


def _ref_key(ref: dict[str, Any]) -> tuple:
    return (ref.get("source"), ref.get("bronze_run_id"), ref.get("line_number"))


def _refs(fragment: dict[str, Any]) -> list[dict[str, Any]]:
    ref = fragment.get("bronze_reference")
    return [ref] if ref else list(fragment.get("bronze_references") or [])


def _merge_attrs(existing: dict[str, Any], incoming: dict[str, Any], reserved: frozenset[str]) -> dict[str, list[Any]]:
    """Return newly discovered conflicting alternates (slot -> values)."""
    alternates: dict[str, list[Any]] = {}
    for key, value in incoming.items():
        if key in reserved or value in (None, "", "None"):
            continue
        if key not in existing or existing[key] in (None, "", "None"):
            existing[key] = value
            continue
        if existing[key] != value:
            alternates.setdefault(key, sorted({existing[key], value}, key=str))
    return alternates


@dataclass
class GraphAccumulator:
    resolver: EntityResolver
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: dict[tuple, dict[str, Any]] = field(default_factory=dict)
    summary: MergeSummary = field(default_factory=MergeSummary)
    resolution: dict[str, set[str]] = field(default_factory=dict)
    attribute_alternates: dict[str, dict[str, list[Any]]] = field(default_factory=dict)

    def add_node(self, fragment: dict[str, Any], source: str, silver_run_id: str) -> None:
        node_id = fragment.get("id")
        if not node_id:
            raise FragmentShapeError("node missing id")

        node_type = fragment.get("@type")
        cid = self.resolver.canonical_id(str(node_id), node_type=node_type)
        attrs = {k: v for k, v in fragment.items() if k not in RESERVED_NODE_KEYS}

        existing = self.nodes.get(cid)
        if existing is None:
            self.nodes[cid] = {
                "@type": node_type,
                "id": cid,
                **attrs,
                "labels": set(fragment.get("labels") or []),
                "bronze_references": {_ref_key(r): r for r in _refs(fragment)},
                "sources": {(source, silver_run_id)},
            }
        else:
            if existing["@type"] != node_type:
                self.summary.conflicts += 1
                raise MergeConflictError(
                    f"@type conflict for {cid}: {existing['@type']} vs {node_type}"
                )
            alts = _merge_attrs(existing, fragment, RESERVED_NODE_KEYS)
            if alts:
                self.attribute_alternates.setdefault(cid, {}).update(alts)
            existing["labels"].update(fragment.get("labels") or [])
            for r in _refs(fragment):
                existing["bronze_references"].setdefault(_ref_key(r), r)
            existing["sources"].add((source, silver_run_id))
            self.summary.node_merges += 1

        self.resolution.setdefault(cid, set()).add(str(node_id))

    def add_edge(self, fragment: dict[str, Any], source: str, silver_run_id: str) -> None:
        subject, predicate, obj = normalize_edge_endpoints(fragment)
        subject = self.resolver.resolve_endpoint(subject)
        obj = self.resolver.resolve_endpoint(obj)
        key = edge_merge_key(fragment, subject, predicate, obj)
        edge_type = fragment.get("@type") or "RELATIONSHIP"
        attrs = {k: v for k, v in fragment.items() if k not in RESERVED_EDGE_KEYS}

        existing = self.edges.get(key)
        if existing is None:
            self.edges[key] = {
                "@type": edge_type,
                "id": fragment.get("id"),
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                **attrs,
                "bronze_references": {_ref_key(r): r for r in _refs(fragment)},
                "sources": {(source, silver_run_id)},
            }
        else:
            alts = _merge_attrs(existing, fragment, RESERVED_EDGE_KEYS)
            edge_id = fragment.get("id")
            if edge_id and not existing.get("id"):
                existing["id"] = edge_id
            alt_key = f"edge:{key!r}"
            if alts:
                self.attribute_alternates.setdefault(alt_key, {}).update(alts)
            for r in _refs(fragment):
                existing["bronze_references"].setdefault(_ref_key(r), r)
            existing["sources"].add((source, silver_run_id))
            self.summary.edge_merges += 1
```

Notes:

- Attribute alternates accumulate in `attribute_alternates` for the resolution report — not quarantined in M4.
- `@type` conflict on the same canonical node id raises `MergeConflictError` → runner routes to `conflicts.jsonl` + `quarantine.jsonl`.
- Edge `id` is preserved when present; endpoint resolution updates `subject`/`object` only.

---

## 6. Runner

**What:** Load resolver, stream inputs, accumulate, write merged outputs + sidecars.

**File:** `integrate/runner.py`

```python
"""Orchestrate Stage 4 integrate → merged Silver."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from integrate.context import IntegrateContext
from integrate.engine import GraphAccumulator, is_edge, iter_fragments
from integrate.errors import EmptyMergeError, FragmentShapeError, MergeConflictError
from integrate.resolvers.base import EntityResolver

log = logging.getLogger(__name__)


def _load_resolver(dotted_path: str) -> EntityResolver:
    import importlib

    module_path, fn_name = dotted_path.rsplit(".", 1)
    factory = getattr(importlib.import_module(module_path), fn_name)
    return factory()


def _quarantine_entry(
    *, source: str, silver_run_id: str, line: int, fragment: dict, reason: str, error: str = ""
) -> dict:
    return {
        "source": source,
        "silver_run_id": silver_run_id,
        "line": line,
        "reason": reason,
        "error": error,
        "fragment": fragment,
    }


def run_integrate(ctx: IntegrateContext) -> dict:
    ctx.merged_dir.mkdir(parents=True, exist_ok=True)
    resolver = _load_resolver(ctx.resolver)
    acc = GraphAccumulator(resolver)
    quarantine: list[dict] = []
    conflicts: list[dict] = []
    started_at = datetime.now(timezone.utc)

    for inp in ctx.sorted_inputs():
        path = inp.fragments_path(ctx.silver_root)
        for line_number, fragment in iter_fragments(path):
            acc.summary.input_fragment_count += 1
            try:
                if is_edge(fragment):
                    acc.summary.input_edge_count += 1
                    acc.add_edge(fragment, inp.source, inp.silver_run_id)
                elif fragment.get("id"):
                    acc.summary.input_node_count += 1
                    acc.add_node(fragment, inp.source, inp.silver_run_id)
                else:
                    raise FragmentShapeError("unclassifiable or null-id fragment")
            except MergeConflictError as e:
                acc.summary.conflicts += 1
                entry = _quarantine_entry(
                    source=inp.source,
                    silver_run_id=inp.silver_run_id,
                    line=line_number,
                    fragment=fragment,
                    reason="type_conflict",
                    error=str(e),
                )
                quarantine.append(entry)
                conflicts.append(entry)
            except FragmentShapeError as e:
                acc.summary.quarantined += 1
                quarantine.append(
                    _quarantine_entry(
                        source=inp.source,
                        silver_run_id=inp.silver_run_id,
                        line=line_number,
                        fragment=fragment,
                        reason="fragment_shape",
                        error=str(e),
                    )
                )

    acc.summary.merged_node_count = len(acc.nodes)
    acc.summary.merged_edge_count = len(acc.edges)

    if acc.summary.merged_node_count == 0 and acc.summary.merged_edge_count == 0:
        raise EmptyMergeError("no nodes or edges survived integration")

    _write_nodes(ctx, acc)
    _write_edges(ctx, acc)

    if quarantine:
        with ctx.quarantine_path.open("w", encoding="utf-8") as fq:
            for entry in quarantine:
                fq.write(json.dumps(entry, ensure_ascii=False) + "\n")
    if conflicts:
        with (ctx.merged_dir / "conflicts.jsonl").open("w", encoding="utf-8") as fc:
            for entry in conflicts:
                fc.write(json.dumps(entry, ensure_ascii=False) + "\n")

    finished_at = datetime.now(timezone.utc)
    manifest = _build_manifest(ctx, acc, started_at, finished_at, len(quarantine), len(conflicts))
    ctx.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_resolution_report(ctx, acc)

    log.info(
        "integrate_complete run_id=%s nodes=%s edges=%s quarantined=%s",
        ctx.run_id,
        acc.summary.merged_node_count,
        acc.summary.merged_edge_count,
        acc.summary.quarantined,
    )
    return manifest


def _serialize_node(node: dict) -> dict:
    out: dict = {"@type": node["@type"], "id": node["id"]}
    for key, value in sorted(node.items()):
        if key in RESERVED_NODE_KEYS or key in {"labels", "bronze_references", "sources"}:
            continue
        if value not in (None, "", "None"):
            out[key] = value
    if node.get("labels"):
        out["labels"] = sorted(node["labels"])
    out["bronze_references"] = sorted(
        node["bronze_references"].values(),
        key=lambda r: (r.get("source", ""), r.get("bronze_run_id", ""), r.get("line_number", 0)),
    )
    out["sources"] = [{"source": s, "silver_run_id": r} for s, r in sorted(node["sources"])]
    return out


def _serialize_edge(edge: dict) -> dict:
    out: dict = {
        "@type": edge["@type"],
        "subject": edge["subject"],
        "predicate": edge["predicate"],
        "object": edge["object"],
    }
    if edge.get("id"):
        out["id"] = edge["id"]
    for key, value in sorted(edge.items()):
        if key in RESERVED_EDGE_KEYS or key in {"bronze_references", "sources"}:
            continue
        if value not in (None, "", "None"):
            out[key] = value
    out["bronze_references"] = sorted(
        edge["bronze_references"].values(),
        key=lambda r: (r.get("source", ""), r.get("bronze_run_id", ""), r.get("line_number", 0)),
    )
    out["sources"] = [{"source": s, "silver_run_id": r} for s, r in sorted(edge["sources"])]
    return out


RESERVED_NODE_KEYS = frozenset({
    "@type", "id", "subject", "object", "predicate", "rel_type",
    "bronze_reference", "bronze_references", "sources", "labels",
})
RESERVED_EDGE_KEYS = RESERVED_NODE_KEYS


def _write_nodes(ctx: IntegrateContext, acc: GraphAccumulator) -> None:
    with ctx.nodes_path.open("w", encoding="utf-8") as fout:
        for nid in sorted(acc.nodes):
            fout.write(json.dumps(_serialize_node(acc.nodes[nid]), ensure_ascii=False) + "\n")


def _write_edges(ctx: IntegrateContext, acc: GraphAccumulator) -> None:
    with ctx.edges_path.open("w", encoding="utf-8") as fout:
        for key in sorted(acc.edges):
            fout.write(json.dumps(_serialize_edge(acc.edges[key]), ensure_ascii=False) + "\n")


def _build_manifest(ctx, acc, started_at, finished_at, quarantine_count, conflict_count) -> dict:
    s = acc.summary
    return {
        "run_id": ctx.run_id,
        "stage": "integrate",
        "tier": "silver-merged",
        "resolver": ctx.resolver,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "status": "success",
        "inputs": [
            {
                "source": i.source,
                "silver_run_id": i.silver_run_id,
                "fragments_path": str(i.fragments_path(ctx.silver_root)),
            }
            for i in ctx.sorted_inputs()
        ],
        "output": {
            "nodes_path": str(ctx.nodes_path),
            "edges_path": str(ctx.edges_path),
            "quarantine_path": str(ctx.quarantine_path),
            "input_fragment_count": s.input_fragment_count,
            "input_node_count": s.input_node_count,
            "input_edge_count": s.input_edge_count,
            "merged_node_count": s.merged_node_count,
            "merged_edge_count": s.merged_edge_count,
            "node_merges": s.node_merges,
            "edge_merges": s.edge_merges,
            "quarantine_count": quarantine_count,
            "conflict_count": conflict_count,
        },
    }


def _write_resolution_report(ctx: IntegrateContext, acc: GraphAccumulator) -> None:
    merges = {
        cid: sorted(originals)
        for cid, originals in acc.resolution.items()
        if len(originals) > 1 or (originals and next(iter(originals)) != cid)
    }
    report = {
        "run_id": ctx.run_id,
        "resolver": ctx.resolver,
        "merged_groups": merges,
        "attribute_alternates": acc.attribute_alternates,
        "node_merges": acc.summary.node_merges,
        "edge_merges": acc.summary.edge_merges,
        "conflicts": acc.summary.conflicts,
        "quarantined": acc.summary.quarantined,
    }
    ctx.resolution_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
```

**Behavior notes:**

- `quarantine.jsonl` is written whenever any fragment fails classification, has null id, or hits `@type` conflict.
- `EmptyMergeError` only when **zero** nodes and **zero** edges survive — a run that quarantines all travel claims but merges contracts still succeeds.
- Sort keys before write → byte-identical output on re-run.
- `tools/neo4j_import/preprocess_silver.py` remains a **single-source dev shortcut**; production multi-source loads should preprocess **`silver/merged/`** instead.

---

## 7. CLI

**File:** `integrate/cli.py`

```python
"""CLI for Stage 4 integrate."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from integrate.context import IntegrateContext, SilverInput
from integrate.runner import run_integrate


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def _parse_input(token: str) -> SilverInput:
    # Format: source:silver_run_id  (e.g. commons_members:2026-06-24T172758Z)
    source, _, run_id = token.partition(":")
    if not source or not run_id:
        raise argparse.ArgumentTypeError(
            f"--input must be 'source:silver_run_id', got: {token!r}"
        )
    return SilverInput(source=source, silver_run_id=run_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="integrate")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Merge Silver fragments → silver/merged/")
    run_p.add_argument(
        "--input", action="append", required=True, type=_parse_input,
        metavar="SOURCE:SILVER_RUN_ID",
        help="A Silver run to merge; repeatable.",
    )
    run_p.add_argument("--run-id", default=_default_run_id())
    run_p.add_argument("--silver-root", type=Path, default=Path("silver"))
    run_p.add_argument(
        "--resolver", default="integrate.resolvers.identity.get_resolver",
        help="Dotted path to an EntityResolver factory.",
    )

    args = parser.parse_args()
    ctx = IntegrateContext(
        run_id=args.run_id,
        inputs=tuple(args.input),
        silver_root=args.silver_root,
        resolver=args.resolver,
    )
    manifest = run_integrate(ctx)
    print(json.dumps(manifest["output"], indent=2))
```

**File:** `integrate/__main__.py`

```python
from integrate.cli import main

if __name__ == "__main__":
    main()
```

Add `integrate/__init__.py` and `integrate/resolvers/__init__.py` (avoid the M3 omission of package `__init__.py` files).

---

## 8. Package structure (target)

```text
integrate/
├── __init__.py
├── __main__.py                  # → integrate.cli.main
├── cli.py
├── runner.py                    # run_integrate(ctx) -> dict
├── engine.py                    # iter_fragments, is_edge, normalize_edge, GraphAccumulator
├── context.py                   # IntegrateContext, SilverInput
├── errors.py
├── resolvers/
│   ├── __init__.py
│   ├── base.py                  # EntityResolver ABC
│   └── identity.py              # IdentityResolver + get_resolver()
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── fixtures/                # synthetic single- and two-source Silver
    ├── test_engine_merge.py
    ├── test_edge_normalize.py
    ├── test_resolver_identity.py
    └── test_integration_merge.py
```

---

## 9. End-to-end example

```bash
pip install -e ".[dev,validate]"

# Stages 1–3 — members (small fixture)
python -m ingest run --source commons_members \
  --fetch-policy local-file \
  --input ingest/tests/fixtures/raw/commons_members_sample.xml \
  --run-id m4-test
python -m validate run --source commons_members --staging-run-id m4-test --run-id m4-test
python -m transforms run --source commons_members --bronze-run-id m4-test --run-id m4-test

# Stage 4 — identity merge (single source; counts == distinct ids / edge ids)
python -m integrate run --input commons_members:m4-test --run-id m4-test

# Multi-source merge (identity resolver — two Person namespaces remain separate)
python -m integrate run \
  --input commons_members:2026-07-03T151251Z \
  --input commons_members_expenditures:2026-07-08T024008Z \
  --input commons_members_bylaw:2026-07-03T151251Z \
  --run-id m4-full

# With Person resolution (Phase 9 — after commons_person resolver exists)
python -m integrate run \
  --input commons_members:2026-07-03T151251Z \
  --input commons_members_expenditures:2026-07-08T024008Z \
  --resolver integrate.resolvers.commons_person.get_resolver \
  --run-id m4-resolved

# Idempotency — same input twice
python -m integrate run \
  --input commons_members:m4-test \
  --input commons_members:m4-test \
  --run-id m4-dupe

# Inspect (do not open large files in the editor)
head -n 3 silver/merged/m4-test/nodes.jsonl | python -m json.tool
head -n 3 silver/merged/m4-test/edges.jsonl | python -m json.tool
cat silver/merged/m4-full/manifest.json
cat silver/merged/m4-full/resolution_report.json
wc -l silver/merged/m4-full/quarantine.jsonl   # expect ~73k null-id travel/hospitality claims
```

**Expected (10-row members fixture, single input):** `merged_node_count == 20`, `merged_edge_count == 10`, `node_merges == 0`, edges retain `@type: PersonHasRoleMemberOfParliament` (or `RELATIONSHIP` for older Silver), `predicate: "HAS_ROLE"`.

**Expected (multi-source, identity resolver):** merged graph contains both Person URI namespaces; `quarantine.jsonl` lists null-id expenditure claim nodes; manifest `quarantine_count` > 0.

---

## 10. Tests (offline, no network)

| Test | What it proves |
|------|----------------|
| `test_is_edge_classification` | `subject`+`object` → edge even when `id` present; node only when not edge and `id` set |
| `test_normalize_legacy_rel_type` | `rel_type: HAS_ROLE` → `predicate: HAS_ROLE` (no case change) |
| `test_preserve_reified_edge_type` | Output edge `@type` stays `PersonHasRoleMemberOfParliament`, not `RELATIONSHIP` |
| `test_edge_dedupe_by_id` | Two fragments with same reified edge `id` collapse to one |
| `test_edge_dedupe_by_triple_without_id` | Legacy `RELATIONSHIP` rows without `id` dedupe on `( @type, s, p, o )` |
| `test_node_merge_same_id` | Two identical-id nodes collapse; `node_merges == 1` |
| `test_node_merge_unions_provenance` | Merged node has both `bronze_references`; sorted, de-duplicated |
| `test_node_merge_preserves_typed_attrs` | `total`, `description`, etc. survive merge (first-non-empty) |
| `test_null_id_quarantined` | `"id": null` node → `quarantine.jsonl`, not merged |
| `test_node_type_conflict_quarantined` | Same canonical id, different `@type` → `conflicts.jsonl` |
| `test_attribute_alternate_recorded` | Conflicting non-empty attrs → `resolution_report.json` alternates, first wins |
| `test_resolver_identity` | `IdentityResolver.canonical_id(x) == x` |
| `test_two_source_resolver_merges_person` | Synthetic fixture + stub resolver merges two Person ids |
| `test_output_deterministic` | Re-run → byte-identical `nodes.jsonl`/`edges.jsonl` |
| `test_integration_silver_to_merged` | Temp Silver dirs → `run_integrate` → manifest counts |
| `test_empty_merge_raises` | No surviving nodes/edges → `EmptyMergeError` |

Use small hand-written Silver fixtures under `integrate/tests/fixtures/` (no dependency on a real Stage 3 run). Include a **two-source** fixture pair plus a one-off stub resolver to exercise the ER hook without a second real source.

---

## 11. Done criteria

- [ ] `integrate/` package installable; `python -m integrate run --input …` works
- [ ] Multi-source run writes:
  - `silver/merged/{run_id}/nodes.jsonl`
  - `silver/merged/{run_id}/edges.jsonl`
  - `silver/merged/{run_id}/manifest.json`
  - `silver/merged/{run_id}/resolution_report.json`
  - `silver/merged/{run_id}/quarantine.jsonl` (when inputs include null-id fragments)
- [ ] Nodes with the same canonical GCKG URI collapse; typed attrs + provenance merged
- [ ] Edges preserve reified `@type`; `rel_type` promoted to `predicate` without case change; dedupe by edge `id` or triple
- [ ] Same inputs → byte-identical merged output
- [ ] Null-id nodes and `@type` conflicts quarantined, not silently dropped or merged
- [ ] `EntityResolver` hook with identity default; synthetic two-source test merges across ids
- [ ] `pytest integrate/tests` passes offline
- [x] `pyproject.toml` registers `integrate` (package, console script, `testpaths`)
- [ ] README Milestone 4 section links to this plan and notes Neo4j shortcut vs merged Silver

---

## 12. Follow-on (Stage 5 — Publish / Gold)

Not this milestone:

- Validate merged `nodes.jsonl` / `edges.jsonl` against `domain_model/schema.yaml` (closed-world LinkML validator, as in Stage 2).
- Reified-triple validation: edges validated as named classes (`PersonHasRoleMemberOfParliament`, `MembersExpenditureReportHasContractExpenseClaim`, …) with `slot_usage` on subject/object ranges and `equals_string` / `ifabsent` predicate constraints.
- Emit Gold under `gold/{run_id}/` (graph-native, domain-conformant assertions only).
- Route domain-invalid nodes/edges to quarantine with a domain drift report.

Stage 4 preserves reified `@type`, domain predicate strings, and edge slots so Publish can validate merged Silver directly — it does not collapse edges to generic `RELATIONSHIP` rows.

---

## 13. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Heterogeneous Silver shapes across sources/generations | §0 classification matrix; tests per variant; legacy `rel_type` promotion only |
| Null-id expenditure claim nodes (~73k rows) | Quarantine in Integrate; fix Stage 3 transform separately; merge still succeeds |
| Predicate case drift (`hasRole` vs `HAS_ROLE`) | Never rewrite predicate case in Integrate; match domain model literals |
| Reified edge metadata lost on merge | Preserve `@type`, edge `id`, and non-reserved slots; dedupe by edge `id` |
| Cross-source Person URIs not collapsed with identity resolver | Document expected behavior; Phase 9 `commons_person` resolver |
| In-memory index too large for ~2M expenditure fragments | Profile full merge; external sort-merge if needed (§13 note below) |
| Neo4j shortcut bypasses Integrate | Document in README/SOP; multi-source production loads use `silver/merged/` |
| `@type` conflict silently merges bad data | Quarantine + `conflicts.jsonl`; never coerce |
| Non-deterministic output | Sort inputs, ids, edge keys, attrs, refs before write |
| Provenance lost on merge | Union `bronze_references` + `sources`; test both survive |
| Scope creep into Publish | M4 does **no** domain validation |
| MP URI embeds raw `from_date_time` | Treat URIs as opaque; fix URI scheme in Stage 3 if needed |

---

## 14. File layout (after M4)

```text
gckg/
├── domain_model/                    # Stage 5 gate (Publish) — unchanged by M4
├── source/                          # Stage 2 gate
├── ingest/   validate/   transforms/
├── integrate/                       # Python package · Stage 4 (new)
│   ├── cli.py  runner.py  engine.py  context.py  errors.py
│   ├── resolvers/{base,identity}.py
│   └── tests/
│
├── silver/                          # Stage 3 (per-source) + Stage 4 (merged)
│   ├── {source}/{run_id}/           # per-source fragments (Stage 3)
│   │   ├── fragments.jsonl
│   │   ├── quarantine.jsonl
│   │   └── manifest.json
│   └── merged/{run_id}/             # Stage 4 output (new)
│       ├── nodes.jsonl
│       ├── edges.jsonl
│       ├── quarantine.jsonl          # null ids, bad shapes, type conflicts
│       ├── conflicts.jsonl           # subset of quarantine (@type conflicts)
│       ├── manifest.json
│       └── resolution_report.json
│
└── gold/                            # Stage 5 (future)
```

---

## 15. Relationship to other stages

| Stage | Input | Output | Schema |
|-------|-------|--------|--------|
| 1 Ingest | raw publisher | staging JSONL | — |
| 2 Validate | staging | Bronze JSONL | `source/*.schema.yaml` |
| 3 Transform | Bronze | Silver fragments (per source) | YAML transform maps (+ `domain_model/` reference) |
| **4 Integrate** | **Silver fragments (1+ sources)** | **merged Silver (`nodes.jsonl` + `edges.jsonl`)** | **none (URI merge + shape normalization + resolver hook)** |
| 5 Publish | merged Silver | Gold | `domain_model/schema.yaml` validation |

**Integrate introduces no new GCKG IDs.** It only reconciles the IDs Stage 3 already minted. Domain validation is Stage 5's job.
