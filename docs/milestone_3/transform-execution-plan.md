# Execution plan — Stage 3 Transform (Silver)

**Stage 3** maps Bronze `records.jsonl` to **Silver graph fragments**, materializing domain entities and relationships informed by `domain_model/`.

**Implementation reality (read first):** the transform is driven by **Python materializers** in the `transforms/` package (plural). A LinkML-Map-style spec (`transforms/commons_members_to_gckg.transform.yaml`) exists on disk as a declarative reference but is **not loaded or executed** by the runner. `linkml-map` is **not** a project dependency.

Pilot source: **`commons_members`** (small, well-understood MP semantics).  
Second source: **`open_canada_federal_election_contribution`** (finance/election domain) — **deferred** until the members path is complete and Stage 2 has a source schema for contributions.

Implement **top to bottom**. Each section: **what it does** → design/code guidance, with the current state called out.

---

## Implementation status (actual)

| Area | State |
|------|-------|
| `transforms/` package + CLI + runner + engine | **Done** — `python -m transforms run …` works end-to-end |
| Streaming Bronze → materialize → Silver fragments + manifest | **Done** |
| `commons_members` materializer | **Partial** — emits only `Person`, `MemberOfParliament`, generic `RELATIONSHIP` |
| Deterministic GCKG IDs | **Partial** — inline helpers, colon-delimited URIs, **no slugs**, no district/seat/party IDs |
| LinkML-Map execution | **Not wired** — spec file is reference-only; no `linkml-map` dependency |
| `experimental/` lane + `--map` / `--experimental` flags | **Not implemented** |
| Tests (`transforms/tests/`) | **Not implemented** — directory does not exist |
| Packaging (`.[transform]` extra, console script, `linkml-map` dep) | **Not implemented** |
| Contributions source | **Deferred** (adapter file orphaned — see §12) |

**Known defects to clean up:**

- `transforms/cli.py` sets `argparse` `prog="validate"` (copied from the validate CLI).
- `transforms/utils.py` is incomplete (syntax error at `def make_bronze_reference`, references a non-existent `context.domain_model_path`) and is **not imported** anywhere.
- `transforms/config/get_map_config()` exists but the runner ignores it (calls `load_maps()[ctx.source]` directly), so `map_path` is never path-resolved at runtime.
- `TransformContext.map_path` (a property returning `{silver_dir}/map.json`) is unused.
- No `transforms/__init__.py` or `transforms/materializers/__init__.py`.

---

## Prerequisites

| Requirement | Status |
|-------------|--------|
| Bronze layout | Done — `bronze/{source}/{run_id}/records.jsonl` + `manifest.json` |
| Source schema | Done — `source/commons_members.schema.yaml` (`CommonsMembersRow`) |
| Domain model skeleton | Partial — `domain_model/` with foundation types + `house_of_commons.yaml` classes and root triples in `schema.yaml` |
| Stage 2 validate path | Done for `commons_members` |
| `transforms/` package | Done — runnable; gaps listed above |
| LinkML-Map tooling | Not added — `linkml-map` is not in deps; runtime is pure Python |

**Handoff contract:** Transform reads **Bronze only** — never staging or raw publishers.

```text
bronze/{source}/{bronze_run_id}/records.jsonl
  →  Transform (Python materializer)
  →  silver/{source}/{run_id}/fragments.jsonl
  →  silver/{source}/{run_id}/quarantine.jsonl
  →  silver/{source}/{run_id}/manifest.json
```

Align `--run-id` with prior stages when you want matching directory names (same pattern as `validate`).

---

## Design decisions (M3)

1. **Declarative maps in YAML — aspirational.** The `.transform.yaml` spec is kept as a reference, but field/entity logic currently lives in the Python materializer, not the map.
2. **Silver = per-source graph fragments** — no cross-source merge yet (Stage 4 Integrate). **Implemented.**
3. **GCKG IDs introduced here** — deterministic, source-scoped URIs. **Implemented**, colon-delimited (e.g. `gckg:Person:Commons:{person_id}`).
4. **One Bronze row may emit many Silver objects** — **partially implemented**: today one MP tenure row → `Person` + `MemberOfParliament` + one `RELATIONSHIP` (3 fragments). District/Seat/Party not yet emitted.
5. **Production vs experimental** — **not implemented**; no `experimental/` lane or CLI flag exists.
6. **Stream Bronze JSONL** — **implemented** via `iter_bronze_records` (line-by-line).
7. **Silver output is JSONL of graph objects** — **implemented**; one JSON object per node or edge (see §1); not RDF files yet.
8. **No Gold validation in M3** — **true today**: no structural checks beyond materializer success; full domain gate is Stage 5 Publish.
9. **No provenance domain module** — **true**: traceability is a lightweight `bronze_reference` object on each Silver fragment (JSON metadata), not a LinkML class.

---

## Target semantics — `commons_members`

One `CommonsMembersRow` (Bronze) represents one **tenure interval** for an MP. Bronze has **no district or party IDs** — only names.

**Currently materialized (3 fragments per row):**

| Domain object | Actual ID pattern (example) | Bronze fields used |
|---------------|-----------------------------|--------------------|
| `Person` | `gckg:Person:Commons:{person_id}` (e.g. `gckg:Person:Commons:89156`) | `person_id`, `person_official_first_name`, `person_official_last_name` |
| `MemberOfParliament` | `gckg:MemberOfParliament:{person_id}:{from_date_time}` (e.g. `…:89156:2025-04-28T00:00:00Z`) | `person_id`, `from_date_time` |
| `RELATIONSHIP` | `subject`=Person URI, `rel_type`=`HAS_ROLE`, `object`=MP URI | — (links the two above) |

**Planned but NOT yet materialized:**

| Domain object | Intended ID pattern | Notes |
|---------------|---------------------|-------|
| `FederalElectoralDistrict` | `gckg:district/commons/{slug}` | needs slug from `constituency_name` (+ province) |
| `HouseOfCommonsSeat` | `gckg:seat/hoc/{slug}` | one seat per district for this source |
| `PoliticalParty` | `gckg:party/commons/{slug}` | from `caucus_short_name` |
| `PersonAssociatedWithPoliticalParty` | (triple) | Person → party (caucus at tenure) |

Notes on current behaviour:

- **No slug logic exists.** The MP URI embeds the raw `from_date_time` string (e.g. `2025-04-28T00:00:00Z`), not a normalized value.
- The generic `RELATIONSHIP` fragment uses `rel_type` (not `predicate`) and a constant `HAS_ROLE`; it is not a named reified-triple class from `domain_model/schema.yaml`.
- The materializer does **not** emit `start_date`/`end_date` on the `MemberOfParliament` fragment, even though the `.transform.yaml` spec defines those derivations.
- `to_date_time: null` in Bronze is currently ignored (no current-member handling yet).

When district/party/seat materialization is added, implement slugs and document normalization rules in tests. Named triple classes (`PersonHasRoleMemberOfParliament`, `PersonAssociatedWithPoliticalParty`) live in `domain_model/schema.yaml`; domain entity classes live in `domain_model/domains/house_of_commons.yaml`.

---

## Work breakdown

| Phase | Work | Status | Output |
|-------|------|--------|--------|
| **0 — Domain prep** | `house_of_commons.yaml` + root triples for MP tenure | Partial | `cd domain_model && gen-yaml schema.yaml` passes |
| **1 — Platform** | `transforms/` package: context, errors, config registry, engine, runner, CLI | **Done** | `python -m transforms run …` |
| **2 — IDs + bronze_reference** | Deterministic URI builders + `make_bronze_reference()` | Partial | Inline in materializer/base; no `ids.py`, no slugs |
| **3 — Map (members)** | `commons_members_to_gckg.transform.yaml` (LinkML-Map style) | Partial | File exists, **not executed** |
| **4 — Materializer (members)** | `transforms/materializers/commons_members.py` | Partial | 3 fragment types (Person, MP, RELATIONSHIP) |
| **5 — Pilot run** | End-to-end: bronze MP fixture → silver fragments | **Done** | `silver/commons_members/{run_id}/` |
| **6 — Tests** | Map/materializer/integration tests | Not started | `transforms/tests/` does not exist |
| **7 — Packaging** | `transforms` in `pyproject.toml`, deps, console script, README | Not started | — |
| **8 — Experimental lane** | `--map experimental/…` flag | Not started | — |
| **9 — Contributions** | Source schema (M2), finance domain classes, map + materializer | Deferred | Post-pilot |

---

## 0. Domain model — current state and gaps

**What:** Materialization targets should exist in LinkML before broadening maps.

**Already in repo:**

- `domain_model/foundation/types.yaml` — `Person`, `Organization`, `Role`, `Membership`, …
- `domain_model/domains/house_of_commons.yaml` — `FederalElectoralDistrict`, `HouseOfCommonsSeat`, `MemberOfParliament` (Role with `start_date` / `end_date`), `PoliticalParty`
- `domain_model/schema.yaml` — reified triples `PersonHasRoleMemberOfParliament`, `PersonAssociatedWithPoliticalParty`

**Current gap:** the materializer only references `Person` and `MemberOfParliament` (and emits a generic `RELATIONSHIP`). `FederalElectoralDistrict`, `HouseOfCommonsSeat`, and `PoliticalParty` are defined in the domain model but **unused** by Stage 3 so far. The emitted `RELATIONSHIP` does not yet correspond to the named `PersonHasRoleMemberOfParliament` triple class.

**Do not add** `domains/provenance.yaml` — Bronze traceability stays in Silver JSON (`bronze_reference`), not the domain schema.

**Build check:**

```bash
cd domain_model && gen-yaml schema.yaml
```

---

## 1. Silver output format

**What:** JSONL shape for graph fragments (one object per line). Below are the **actual** shapes emitted today.

```json
{"@type": "MemberOfParliament", "bronze_reference": {"source": "commons_members", "bronze_run_id": "2026-06-17T173917Z", "line_number": 1}, "id": "gckg:MemberOfParliament:89156:2025-04-28T00:00:00Z"}
{"@type": "Person", "bronze_reference": {"source": "commons_members", "bronze_run_id": "2026-06-17T173917Z", "line_number": 1}, "id": "gckg:Person:Commons:89156", "name": "Ziad Aboultaif"}
{"@type": "RELATIONSHIP", "bronze_reference": {"source": "commons_members", "bronze_run_id": "2026-06-17T173917Z", "line_number": 1}, "subject": "gckg:Person:Commons:89156", "rel_type": "HAS_ROLE", "object": "gckg:MemberOfParliament:89156:2025-04-28T00:00:00Z"}
```

Conventions (as implemented):

| Field | Purpose |
|-------|---------|
| `@type` | Domain class name, or the literal `RELATIONSHIP` for edges |
| `id` | GCKG URI for nodes |
| `subject` / `rel_type` / `object` | Edge-shaped rows (note: `rel_type`, not `predicate`) |
| `name` | Present on `Person` only |
| `bronze_reference` | Pointer to Bronze `source`, `bronze_run_id`, and `line_number` (every fragment) |

**File layout (actual):**

```text
silver/{source}/{run_id}/
├── fragments.jsonl      # accepted graph objects (JSONL)
├── quarantine.jsonl     # raw Bronze rows that failed materialization (may be empty)
└── manifest.json        # counts, inputs, map/materializer refs, bronze_run_id
```

---

## 2. Transform config registry

**What:** Maps ingest source name → spec path + source class + materializer factory.

**File:** `transforms/config/maps.yaml` (actual contents):

```yaml
commons_members:
  map_path: transforms/commons_members_to_gckg.transform.yaml
  source_class: CommonsMembersRow
  source_schema: source/commons_members.schema.yaml
  materializer: transforms.materializers.commons_members.get_materializer
```

Notes:

- `materializer` points at a **factory** (`get_materializer`), not `…materialize`.
- `source_schema` is recorded but **not loaded** by the runner.
- `map_path` is recorded into the manifest as a string; the spec file itself is **not applied**.

**File:** `transforms/config/__init__.py` — provides `load_maps()` (cached YAML load) and `get_map_config(source, *, map_path=None)`. The runner uses `load_maps()[ctx.source]` directly; `get_map_config()` is currently unused.

---

## 3. Package structure (actual)

```text
transforms/
├── __main__.py                              # → transforms.cli.main
├── cli.py
├── runner.py                                # run_transform(ctx) -> dict
├── engine.py                                # iter_bronze_records, _load_factory, Outcome/Summary dataclasses
├── context.py                               # TransformContext
├── errors.py                                # BronzeInputError, RowMaterializationError
├── utils.py                                 # INCOMPLETE / broken, unused
├── commons_members_to_gckg.transform.yaml   # LinkML-Map-style spec (reference only)
├── config/
│   ├── __init__.py                          # load_maps(), get_map_config()
│   └── maps.yaml
└── materializers/
    ├── base.py                              # FragmentMaterializer ABC + make_bronze_reference()
    └── commons_members.py
```

**Not present (despite earlier plans):** `transforms/__init__.py`, `materializers/__init__.py`, `transforms/ids.py`, `transforms/tests/`, `experimental/`, any singular `transform/` package.

---

## 4. TransformContext (actual)

`transforms/context.py`:

```python
@dataclass(frozen=True)
class TransformContext:
    source: str
    run_id: str
    bronze_run_id: str
    bronze_root: Path = Path("bronze")
    silver_root: Path = Path("silver")
```

Properties: `bronze_dir`, `silver_dir`, `bronze_manifest_path`, `bronze_records_path`, `silver_fragments_path`, `silver_manifest_path`, `quarantine_path`, and an unused `map_path` (→ `{silver_dir}/map.json`).

There is **no** `map_path` override field or `experimental` flag on the context (unlike earlier plans). `run_id` defaults to a UTC timestamp (`%Y-%m-%dT%H%M%SZ`) in `transforms/cli.py` when `--run-id` is omitted.

---

## 5. Mapping spec — `commons_members` (reference only)

**What:** A LinkML-Map-style declarative spec, kept for documentation. **It is not executed** — no `linkml-map` import, no `validate-spec`/`map-data` calls, and `linkml-map` is not a dependency.

**File:** `transforms/commons_members_to_gckg.transform.yaml` (actual):

```yaml
id: https://w3id.org/gckg/transforms/commons_members_to_gckg
name: commons_members_to_gckg
title: Commons members Bronze → GCKG domain
class_derivations:
  Person:
    populated_from: CommonsMembersRow
    slot_derivations:
      id:
        expr: "'gckg:Person:Commons:' + str(person_id)"
      name:
        expr: >-
          (person_official_first_name or '') + ' ' +
          (person_official_last_name or '')
  MemberOfParliament:
    populated_from: CommonsMembersRow
    slot_derivations:
      id:
        expr: >-
          'gckg:MemberOfParliament:' + str(person_id) + ':' + str(from_date)
      start_date:
        expr: str(from_date_time)
      end_date:
        expr: str(to_date_time)
```

Spec drift to reconcile if/when this is wired up: it references `from_date` (Bronze field is `from_date_time`), and defines `start_date`/`end_date` that the Python materializer does not emit.

**Pragmatic split (current):**

| Concern | Where |
|---------|--------|
| All entity/edge logic | Python materializer |
| Deterministic IDs | Inline helpers in `materializers/commons_members.py` |
| Bronze line pointer | `make_bronze_reference()` on `FragmentMaterializer` (base) |
| Declarative slot copies | `.transform.yaml` (not yet executed) |

---

## 6. Materializer — `commons_members` (actual)

**File:** `transforms/materializers/commons_members.py`

```python
def get_materializer(ctx: TransformContext) -> CommonsMembersMaterializer:
    return CommonsMembersMaterializer(ctx)

class CommonsMembersMaterializer(FragmentMaterializer):
    def materialize(self, row, line_number) -> Iterator[dict]:
        bronze_ref = self.make_bronze_reference(line_number)
        mp_id = commons_member_of_parliament_id(row["person_id"], row["from_date_time"])
        person_id = commons_person_id(row["person_id"])
        person_name = person_full_name(row)
        yield {"@type": "MemberOfParliament", "bronze_reference": bronze_ref, "id": mp_id}
        yield {"@type": "Person", "bronze_reference": bronze_ref, "id": person_id, "name": person_name}
        yield {"@type": "RELATIONSHIP", "bronze_reference": bronze_ref,
               "subject": person_id, "rel_type": "HAS_ROLE", "object": mp_id}
```

Inline ID helpers (no `ids.py`):

```python
def commons_member_of_parliament_id(person_id, from_date):
    return f"gckg:MemberOfParliament:{person_id}:{from_date}"

def commons_person_id(person_id):
    return f"gckg:Person:Commons:{person_id}"

def person_full_name(row: dict) -> str:
    return f"{row['person_official_first_name']} {row['person_official_last_name']}"
```

Base class (`materializers/base.py`) provides `make_bronze_reference(line_number)` →
`{"source", "bronze_run_id", "line_number"}`.

**Next steps to reach target semantics:** emit `FederalElectoralDistrict`, `HouseOfCommonsSeat`, `PoliticalParty`, and a party-association edge; add slug helpers; carry `start_date`/`end_date`; handle `to_date_time: null` (current member).

---

## 7. Runner (actual)

**File:** `transforms/runner.py` — `run_transform(ctx: TransformContext) -> dict`

Flow:

1. Create `ctx.silver_dir` if missing.
2. `map_cfg = load_maps()[ctx.source]`; `factory = _load_factory(map_cfg["materializer"])`; `materializer = factory(ctx)`.
3. Stream `iter_bronze_records(ctx.bronze_records_path)` (yields `(line_number, record)`).
4. Per row: `list(materializer.materialize(record, line_number))`.
   - On `RowMaterializationError`: increment `rejected_count`, record an outcome with `accepted=False`.
5. Write `fragments.jsonl` (accepted fragments) and `quarantine.jsonl` (**raw rejected Bronze records**, not error objects).
6. Build and write `manifest.json` **inline** (no separate `write_silver_manifest` helper).
7. Return the manifest dict.

Serialization uses `json.dumps(fragment, ensure_ascii=False)` — there is **no** custom `default=`/datetime serializer (Bronze date fields are already ISO strings).

**Actual manifest fields:** `run_id`, `bronze_run_id`, `source`, `stage` (`"transform"`), `tier` (`"silver"`), `transform_map`, `source_class`, `materializer`, `started_at`, `finished_at`, `status`, `inputs[]` (`bronze_run_id`, `bronze_manifest_path`), and `output` (`fragments_path`, `quarantine_path`, `fragment_count`, `record_count`, `accepted_count`, `rejected_count`).

Not yet implemented (noted as comments in `runner.py`): progress tracker; reading/validating the Bronze manifest.

---

## 8. CLI (actual)

```bash
python -m transforms run \
  --source commons_members \
  --bronze-run-id 2026-06-17T173917Z \
  --run-id 2026-06-24T172758Z
```

Flags on `run`: `--source` (required), `--bronze-run-id` (required), `--run-id` (default: UTC timestamp), `--bronze-root` (default `bronze`), `--silver-root` (default `silver`).

After the run, the CLI prints `manifest["output"]` as JSON to stdout.

**Not implemented:** `list-sources`, `--map`, `--experimental`.
**Defect:** the argument parser is created with `prog="validate"` (copy/paste from the validate CLI).

**Packaging:** there is **no** `transforms` console script and **no** `.[transform]` optional extra in `pyproject.toml`; `transforms` is also excluded from `[tool.setuptools.packages.find]` (`include = ["ingest*", "validate*"]`). Invoke via `python -m transforms` from the repo root.

---

## 9. End-to-end example

```bash
# Stage 1
python -m ingest run --source commons_members \
  --fetch-policy local-file \
  --input ingest/tests/fixtures/raw/commons_members_sample.xml \
  --run-id m3-test

# Stage 2
python -m validate run --source commons_members \
  --staging-run-id m3-test \
  --run-id m3-test

# Stage 3
python -m transforms run --source commons_members --bronze-run-id m3-test --run-id m3-test

# Inspect (do not open large files in editor)
head -n 5 silver/commons_members/m3-test/fragments.jsonl | python -m json.tool
cat silver/commons_members/m3-test/manifest.json
```

---

## 10. Tests (not implemented)

There is **no** `transforms/tests/` directory and **no** transform tests; `pyproject.toml` `testpaths` only covers `ingest/tests` and `validate/tests`.

Proposed coverage when tests are added:

| Test | What it proves |
|------|----------------|
| `test_ids_deterministic` | Same inputs → same URIs across runs |
| `test_materialize_one_row` | One Bronze row → expected 3 fragment types |
| `test_relationship_links_person_to_role` | `RELATIONSHIP` subject/object match Person/MP URIs |
| `test_bronze_reference_on_every_fragment` | Each object has `bronze_reference` with source, run, line_number |
| `test_integration_bronze_to_silver` | Temp bronze dir → transform → manifest counts |
| `test_quarantine_on_bad_row` | A row raising `RowMaterializationError` lands in `quarantine.jsonl` |

No network in CI.

---

## 11. Experimental lane (not implemented)

There is no `experimental/` directory and no `--map`/`--experimental` flag. When added: allow maps/materializers under `experimental/` only with an explicit flag; promotion = move to `transforms/` + update golden tests.

---

## 12. Contributions (deferred)

Bronze row → finance/election fragments (after members pilot and M2 source schema):

| Object | Notes |
|--------|-------|
| `Person` or `Organization` | recipient vs contributor depending on `contributor_type` |
| `PoliticalParty` | `political_party_of_recipient` |
| `FederalElectoralDistrict` | `electoral_district` |
| Contribution event node | amount, date, form_id — requires new finance domain classes |
| `bronze_reference` on every fragment | link to Bronze line |

**Blockers today:**

- The Stage 1 adapter file still exists (`ingest/adapters/open_canada/contribution.py`) but is **no longer registered**: it is not imported in `ingest/cli.py` and the source is not in `ingest/config/sources.yaml`. It is effectively orphaned code.
- No `source/open_canada_federal_election_contribution.schema.yaml` (Stage 2).
- No `domain_model/domains/finance.yaml` (or election) extensions.
- Bulk-safe streaming materializer needed (millions of Bronze rows).

---

## 13. Done criteria

- [x] `transforms/` package with CLI and runner
- [x] `transforms/config/maps.yaml` registers `commons_members`
- [~] `transforms/commons_members_to_gckg.transform.yaml` exists — but is reference-only and not validated by `linkml-map`
- [~] Materializer emits fragments from one Bronze MP row — currently Person + MemberOfParliament + generic RELATIONSHIP only (no District/Seat/Party/named tenure triple)
- [~] Deterministic GCKG IDs — implemented, but no name-based slugs yet
- [x] `silver/commons_members/{run_id}/fragments.jsonl` + `manifest.json` written (plus `quarantine.jsonl`)
- [x] `bronze_reference` on every Silver fragment
- [ ] `pytest transforms/tests` passes offline — no tests exist
- [x] README Milestone 3 section reflects the actual `transforms/` implementation
- [x] Contributions path documented as deferred

---

## 14. Follow-on (Stage 4 — Integrate)

Not this milestone:

- Merge `silver/*/fragments.jsonl` across sources
- Entity resolution (same Person from commons + contributions)
- Dedupe districts/parties by label/URI rules
- Output merged Silver under `silver/merged/{run_id}/`

---

## 15. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Map spec drifts from materializer (and from Bronze fields like `from_date_time`) | Treat `.transform.yaml` as documentation until wired; add a test that fails on field-name drift |
| No district/party IDs in Bronze | Add and test slug rules before emitting those entities |
| Domain model vs materializer drift | Reconcile generic `RELATIONSHIP` with named triple classes; check against `house_of_commons.yaml` |
| Silver fragment schema undocumented | Keep §1 in sync with the materializer; add golden fixtures |
| No tests | Add `transforms/tests/` and wire into `pyproject.toml` `testpaths` |
| Scope creep into Integrate | M3 explicitly per-source fragments only |

---

## 16. File layout (current)

```text
gckg/
├── domain_model/                    # house_of_commons + root triples (no provenance domain)
├── source/                          # Bronze row shapes (Stage 2)
├── transforms/                      # Python package · Stage 3 (incl. reference .transform.yaml)
├── bronze/                          # input
└── silver/                          # output
    └── {source}/{run_id}/
        ├── fragments.jsonl
        ├── quarantine.jsonl
        └── manifest.json
```

---

## 17. Relationship to other stages

| Stage | Input | Output | Schema |
|-------|-------|--------|--------|
| 1 Ingest | raw publisher | staging JSONL | — |
| 2 Validate | staging | Bronze JSONL | `source/*.schema.yaml` |
| **3 Transform** | **Bronze** | **Silver fragments** | **Python materializer (+ `domain_model/` reference)** |
| 4 Integrate | Silver fragments | merged Silver | — |
| 5 Publish | merged Silver | Gold | `domain_model/schema.yaml` validation |

**Domain IDs appear in Stage 3.** Stage 2 Bronze must remain free of `gckg:` entity URIs.
