# GCKG — Canadian Governments Knowledge Graph

A schema-first knowledge graph that unifies Canadian federal parliamentary and open-government data into a single, validated, queryable graph.

**Current focus:** End-to-end pipeline on **`commons_members`** (House of Commons MP XML) — ingest through publish — before adding other sources.

## Background

Federal political data in Canada is published across multiple systems with different formats, update cadences, and identifiers. Each source is authoritative for its domain, but none was designed to interoperate. The same person, district, or organization appears under different names and keys in different datasets. Without a shared domain model and a disciplined ingest pipeline, cross-source analysis requires ad hoc joins, brittle one-off scripts, and manual reconciliation whenever a publisher changes shape.

GCKG addresses that fragmentation by treating the knowledge graph as a product: typed entities and relationships, explicit provenance, and validation at every boundary.

## Objective

Build a reproducible pipeline that ingests heterogeneous Canadian government sources and produces a **domain-conformant knowledge graph** suitable for research, civic tooling, and downstream applications (SPARQL, graph databases, API layers).

## Success criteria

The project succeeds when:

1. **End-to-end members path** — `commons_members` flows through all five stages (ingest → validate → transform → integrate → publish) and produces Gold-tier graph output.
2. **Schema discipline** — Every record is validated against LinkML schemas at ingest (source shape) and publish (domain shape); drift is caught early and rejected records are quarantined with a report.
3. **Declarative transforms** — Field remapping from source to domain is defined in LinkML-Map YAML, not buried in procedural code.
4. **Integrated graph** — Entity resolution and merge produce a single reconciled graph where the same person, district, or organization resolves to one identifier across sources.
5. **Gold-tier output** — Published data passes domain validation and contains only graph-native, domain-conformant assertions.
6. **Reproducibility** — A run can be repeated with the same inputs and schemas to produce an auditable, versioned output.

Additional source families (Open Canada, Urban Data Centre, other Commons datasets) extend the same pipeline once the members path is complete.

## Getting started

From the repo root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,validate]"
```

Run CLIs as modules (`python -m ingest`, `python -m validate`) or via console scripts (`ingest`, `validate`) after install. Schema paths resolve relative to the repo root — run commands from there.

Lint LinkML blueprints manually when editing schemas:

```bash
cd source && gen-yaml commons_members.schema.yaml
cd domain_model && gen-yaml schema.yaml
```

## Proposed solution

GCKG uses a five-stage medallion pipeline driven by LinkML blueprints at build time and the LinkML validator at runtime.

Pipeline diagram: [`docs/milestone_1/gckg.mmd`](docs/milestone_1/gckg.mmd) (render to PNG for docs if needed).

### Build time — LinkML blueprints

Source schemas, domain model, and experimental schemas are compiled and linted with `gen-yaml`. These blueprints define what valid source rows and domain entities look like before any data moves through the pipeline.

### Runtime stages

| Stage | Purpose | Tier |
|-------|---------|------|
| **1 — Ingest** | Parse and normalize raw publisher data | — |
| **2 — Validate** | LinkML validation against source schema; optional fail-fast on drift | Bronze |
| **3 — Transform** | Python materializers emit graph fragments (LinkML-Map spec kept as reference) | Silver |
| **4 — Integrate** | Graph merge, dedupe, entity resolution, cross-source linking | Silver (merged) |
| **5 — Publish** | LinkML validation against domain schema | Gold |

Records that fail validation at Stage 2 or Stage 5 are routed to **quarantine** with a drift report rather than silently corrupting downstream tiers.

Stage 2 uses `linkml.validator.Validator` (JSON Schema plugin, closed world) — not a shell-out to the `linkml-validate` CLI.

### Design principles

- **Schema-first** — LinkML is the contract between sources, transforms, and the domain model.
- **Fail-fast gates** — Validate at Bronze (source) and Gold (domain); do not propagate bad rows.
- **Separation of concerns** — Adapters handle publisher format; LinkML-Map handles remapping; Integrate handles cross-source reconciliation.
- **Experimental lane** — New transforms can be tested alongside production mappings before promotion to the domain schema.

## Milestone 1 — Ingestion pipeline (Stage 1)

Source workflow diagram: [`docs/milestone_1/gckg-sources.mmd`](docs/milestone_1/gckg-sources.mmd).

**Goal:** Stage 1 (Ingest) — a Python runner and adapters that emit source-shaped `records.jsonl` and a provenance `manifest.json` under `staging/`.

**Status:** Platform and `commons_members` adapter are implemented. Other sources are deferred until the members path is complete end-to-end.

Execution plan: [`docs/milestone_1/commons-members-execution-plan.md`](docs/milestone_1/commons-members-execution-plan.md)

| Phase | Work | Status | Output |
|-------|------|--------|--------|
| **1 — Platform** | `pyproject.toml`, `python -m ingest`, adapter protocol + registry, fetch/cache, `ingest/config/sources.yaml`, staging layout, pytest | Done | `python -m ingest run --source …` |
| **2 — MPs** | `commons_members`: HTTP/local-file fetch, XML parse, schema-driven field map, normalize | Done | `staging/commons_members/{run_id}/` |
| **3 — Hardening** | `run-all`, additional adapters | Deferred | — |

### Registered sources (today)

```bash
python -m ingest list-sources
# commons_members
```

| Source | Module | Fetch | Notes |
|--------|--------|-------|-------|
| `commons_members` | `ingest/adapters/commons/members.py` | HTTP (`default`/`refresh`) or `local-file` | Field map from `source/commons_members.schema.yaml` via `gckg:publisher_header` |

### Done when (members)

- [x] Ingest platform: CLI, registry, fetch policies, staging layout
- [x] `commons_members` adapter + unit tests (`ingest/tests/adapters/test_commons_members.py`)
- [x] Source schema for members: `source/commons_members.schema.yaml`
- [x] Schema-driven field map helper: `ingest/schema.py`
- [x] No GCKG domain IDs or cross-entity joins in Stage 1 output

## Milestone 2 — Validate pipeline (Stage 2 / Bronze)

**Goal:** Validate Stage 1 `records.jsonl` against LinkML **source schemas** (`source/*.schema.yaml`), write **Bronze** (source-validated records), and route failures to **quarantine** with a drift report.

**Status:** Validate platform, `commons_members` gate, tests, and packaging are implemented. Catalog validation and progress logging for large files remain.

Execution plan: [`docs/milestone_2/validate-execution-plan.md`](docs/milestone_2/validate-execution-plan.md)

| Phase | Work | Status | Output |
|-------|------|--------|--------|
| **1 — Platform** | `validate/` package: CLI, runner, engine, context, errors, `validate/config/schemas.yaml` | Done | `python -m validate run …` |
| **2 — Members gate** | `source/commons_members.schema.yaml` (`CommonsMembersRow`), validate staging → Bronze | Done | `bronze/commons_members/{run_id}/` |
| **3 — Tests** | Engine unit tests, staging→Bronze integration on fixtures | Done | `validate/tests/` (12 tests) |
| **4 — Packaging** | `validate` in `pyproject.toml`, `linkml` optional dep, `validate` console script | Done | `pip install -e ".[validate]"` |
| **5 — Hardening** | Catalog validation (ingest sources ∩ schema registry), progress logging for large JSONL | Partial | `--fail-fast` supported |

### How Stage 2 works

1. Read `staging/{source}/{staging_run_id}/records.jsonl` and `manifest.json` (no re-fetch from publishers).
2. Load LinkML source schema from `validate/config/schemas.yaml`.
3. Stream JSONL line-by-line; validate each record with `linkml.validator.Validator`.
4. **Accepted rows** → `bronze/{source}/{validate_run_id}/records.jsonl` + `manifest.json`
5. **Rejected rows** → `quarantine/{source}/{validate_run_id}/rejects.jsonl` + `drift_report.json`

Bronze records are identical to accepted staging rows — no domain IDs, no transform (that is Stage 3).

**Behavior notes:**

- Validate assigns its own `run_id` (defaults to a UTC timestamp). Use `--run-id` to align Bronze paths with a chosen id.
- If every row is rejected, validate raises `EmptyBronzeError`.
- With `--fail-fast`, processing stops on the first reject and raises `ValidationFailedError`.
- `drift_report.json` is written even when there are zero rejects.

### Handoff

```text
staging/{source}/{staging_run_id}/records.jsonl
  →  python -m validate run --source … --staging-run-id … [--run-id …]
  →  bronze/{source}/{validate_run_id}/records.jsonl
  →  quarantine/{source}/{validate_run_id}/rejects.jsonl + drift_report.json  (if any rejects)
```

### Example

```bash
# Stage 1
python -m ingest run --source commons_members \
  --fetch-policy local-file \
  --input ingest/tests/fixtures/raw/commons_members_sample.xml \
  --run-id m2-test

# Stage 2 (Bronze lands under bronze/commons_members/m2-test/ when --run-id matches)
python -m validate run --source commons_members \
  --staging-run-id m2-test \
  --run-id m2-test
```

### Validatable sources (today)

```bash
python -m validate list-sources
# commons_members
```

Requires the validate extra: `pip install -e ".[validate]"`. Run from repo root so `source/` schema paths resolve.

### Done when (members)

- [x] `source/commons_members.schema.yaml` defines `CommonsMembersRow`
- [x] Staging rows validate; accepted records land in `bronze/`
- [x] Rejected rows and `drift_report.json` land in `quarantine/`
- [x] `pyproject.toml` includes `validate` package and LinkML dependency
- [x] `validate/tests/` with offline fixtures

## Milestone 3 — Transform pipeline (Stage 3 / Silver)

**Goal:** Transform Bronze records into **Silver graph fragments**, introducing GCKG domain IDs and typed entities/relationships.

**Status:** Platform and a first `commons_members` materializer are implemented and run end-to-end. Transformation is currently driven by **Python materializers** in the `transforms/` package; a LinkML-Map-style spec (`transforms/commons_members_to_gckg.transform.yaml`) is kept as a reference but is **not executed** (no `linkml-map` dependency). Broader entity coverage, tests, and packaging remain.

Execution plan: [`docs/milestone_3/transform-execution-plan.md`](docs/milestone_3/transform-execution-plan.md)

| Phase | Work | Status | Output |
|-------|------|--------|--------|
| **0 — Domain prep** | `house_of_commons.yaml` + root triples for MP tenure | Partial | `gen-yaml` passes |
| **1 — Platform** | `transforms/` package: CLI, runner, engine, context, config registry, silver layout | Done | `python -m transforms run …` |
| **2 — IDs + bronze_reference** | Deterministic URI builders + `make_bronze_reference()` | Partial | Inline in materializer/base (no `ids.py`, no slugs) |
| **3 — Members materializer** | `transforms/materializers/commons_members.py` (+ reference `.transform.yaml`) | Partial | Person, MemberOfParliament, generic RELATIONSHIP per Bronze row |
| **4 — Experimental lane** | Opt-in experimental maps via CLI flag | Not started | — |
| **5 — Tests + packaging** | Materializer/integration tests, `pyproject.toml` extra | Not started | `transforms/tests/` (does not exist yet) |

### How Stage 3 works

1. Read `bronze/{source}/{bronze_run_id}/records.jsonl`.
2. Look up the source in `transforms/config/maps.yaml` and load its materializer factory.
3. Stream Bronze JSONL; for each row, the **Python materializer** emits one or more graph fragments.
4. Write **`silver/{source}/{run_id}/fragments.jsonl`** — one graph object per line (Person, MemberOfParliament, RELATIONSHIP).
5. Write **`silver/{source}/{run_id}/quarantine.jsonl`** (raw Bronze rows that failed materialization) and **`manifest.json`** with counts and a Bronze reference.

Silver is **per-source** graph fragments. Cross-source merge is Stage 4 (Integrate).

### Handoff

```text
bronze/{source}/{run_id}/records.jsonl
  →  python -m transforms run --source … --bronze-run-id … [--run-id …]
  →  silver/{source}/{run_id}/fragments.jsonl + quarantine.jsonl + manifest.json
```

### Example

```bash
python -m transforms run --source commons_members --bronze-run-id m3-test --run-id m3-test
```

There is no `transforms` console script or `.[transform]` extra yet — invoke via `python -m transforms` from the repo root.

### Done when (members)

- [x] `commons_members` Bronze row materializes graph fragments (Person + MemberOfParliament + RELATIONSHIP)
- [x] GCKG IDs are deterministic and source-scoped (e.g. `gckg:Person:Commons:{id}`)
- [x] Every Silver fragment carries a `bronze_reference` back to Bronze
- [ ] Materialize District + Seat + Party + named tenure triples (with name-based slugs)
- [ ] `transforms/tests/` with offline fixtures; wired into `pyproject.toml`

## File layout

```
gckg/
├── pyproject.toml                          package: gckg-ingest (ingest + validate)
│
├── domain_model/                           LinkML domain schema · Stage 5 Publish gate
│   ├── schema.yaml                         root import
│   ├── foundation/
│   │   ├── prefixes.yaml
│   │   └── types.yaml                      Person, Organization, Role, …
│   └── domains/
│       └── house_of_commons.yaml           MPs, districts, caucus
│
├── source/                                 LinkML source schemas · Stage 2 Validate gate
│   └── commons_members.schema.yaml         CommonsMembersRow (+ publisher_header annotations)
│
├── ingest/                                 Python package · Stage 1 Ingest
│   ├── __main__.py                         python -m ingest
│   ├── cli.py
│   ├── runner.py
│   ├── context.py                          RunContext
│   ├── errors.py
│   ├── schema.py                           load source schemas; publisher_header → slot map
│   ├── utils.py                            shared helpers (e.g. ISO datetime parsing)
│   │
│   ├── fetch/
│   │   ├── client.py                       HTTP, conditional GET, local-file
│   │   └── cache.py                        TTL, sha256, url_hash paths
│   │
│   ├── adapters/
│   │   ├── base.py                         Adapter protocol
│   │   ├── registry.py                     source name → adapter class
│   │   └── commons/
│   │       ├── members.py                  MPs XML (implemented)
│   │       └── xml_utils.py                shared XML helpers
│   │
│   ├── config/
│   │   └── sources.yaml                    URLs, TTL, raw filenames
│   │
│   └── tests/
│       ├── fixtures/raw/                   checked-in samples (no network in CI)
│       └── adapters/                       per-adapter unit tests
│
├── validate/                               Python package · Stage 2 Validate
│   ├── __main__.py                         python -m validate
│   ├── cli.py
│   ├── runner.py
│   ├── engine.py                           stream JSONL + linkml Validator
│   ├── context.py                          ValidateContext
│   ├── errors.py
│   ├── config/
│   │   └── schemas.yaml                    source → schema_path + target_class
│   └── tests/
│
├── transforms/                             Python package · Stage 3 Transform
│   ├── __main__.py                         python -m transforms
│   ├── cli.py
│   ├── runner.py                           run_transform → fragments + quarantine + manifest
│   ├── engine.py                           stream Bronze JSONL, load materializer factory
│   ├── context.py                          TransformContext
│   ├── errors.py
│   ├── commons_members_to_gckg.transform.yaml   LinkML-Map-style spec (reference only)
│   ├── config/
│   │   └── maps.yaml                        source → materializer + spec/source-class refs
│   └── materializers/
│       ├── base.py                         FragmentMaterializer + make_bronze_reference()
│       └── commons_members.py              Bronze row → Person, MP, RELATIONSHIP
│
├── staging/                                gitignored · Stage 1 output
│   └── {source}/
│       ├── cache/
│       └── {run_id}/
│           ├── raw/{filename}
│           ├── records.jsonl               → Validate
│           └── manifest.json
│
├── bronze/                                 gitignored · Stage 2 output
│   └── {source}/{run_id}/
│       ├── records.jsonl
│       └── manifest.json
│
├── quarantine/                             gitignored · Stage 2 rejects
│   └── {source}/{run_id}/
│       ├── rejects.jsonl
│       └── drift_report.json
│
├── silver/                                 gitignored · Stage 3 output
│   └── {source}/{run_id}/
│       ├── fragments.jsonl
│       ├── quarantine.jsonl                 raw Bronze rows that failed materialization
│       └── manifest.json
│
└── gold/                                   gitignored · Stage 5 (future)
```
