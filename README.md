# GCKG — Canadian Governments Knowledge Graph

A schema-first knowledge graph that unifies Canadian federal parliamentary and open-government data into a single, validated, queryable graph.

## Background

Federal political data in Canada is published across multiple systems with different formats, update cadences, and identifiers. Each source is authoritative for its domain, but none was designed to interoperate. The same person, district, or organization appears under different names and keys in different datasets. Without a shared domain model and a disciplined ingest pipeline, cross-source analysis requires ad hoc joins, brittle one-off scripts, and manual reconciliation whenever a publisher changes shape.

GCKG addresses that fragmentation by treating the knowledge graph as a product: typed entities and relationships, explicit provenance, and validation at every boundary.

## Objective

Build a reproducible pipeline that ingests heterogeneous Canadian government sources and produces a **domain-conformant knowledge graph** suitable for research, civic tooling, and downstream applications (SPARQL, graph databases, API layers).

## Success criteria

The project succeeds when:

1. **Multi-source coverage** — At least the Commons, Open Canada, and Urban Data Centre source families flow through the pipeline and land in a merged working graph.
2. **Schema discipline** — Every record is validated against LinkML schemas at ingest (source shape) and publish (domain shape); drift is caught early and rejected records are quarantined with a report.
3. **Declarative transforms** — Field remapping from source to domain is defined in LinkML-Map YAML, not buried in procedural code.
4. **Integrated graph** — Entity resolution and merge produce a single reconciled graph where the same person, district, or organization resolves to one identifier across sources.
5. **Gold-tier output** — Published data passes domain validation and contains only graph-native, domain-conformant assertions.
6. **Reproducibility** — A run can be repeated with the same inputs and schemas to produce an auditable, versioned output.

## Proposed solution

GCKG uses a five-stage medallion pipeline driven by LinkML blueprints at build time and `linkml-validate` at runtime.

![GCKG pipeline architecture](docs/milestone_1/gckg.png)

Diagram source: [`gckg.mmd`](docs/milestone_1/gckg.mmd).

### Build time — LinkML blueprints

Source schemas, domain model, and experimental schemas are compiled and linted with `gen-yaml`. These blueprints define what valid source rows and domain entities look like before any data moves through the pipeline.

### Runtime stages

| Stage | Purpose | Tier |
|-------|---------|------|
| **1 — Ingest** | Parse, normalize, and filter raw publisher data | — |
| **2 — Validate** | `linkml-validate` against source schema; fail-fast on drift | Bronze |
| **3 — Transform** | LinkML-Map declarative translation (production or experimental) | Silver |
| **4 — Integrate** | Graph merge, dedupe, entity resolution, cross-source linking | Silver (merged) |
| **5 — Publish** | `linkml-validate` against domain schema | Gold |

Records that fail validation at Stage 2 or Stage 5 are routed to **quarantine** with a drift report rather than silently corrupting downstream tiers.

### Design principles

- **Schema-first** — LinkML is the contract between sources, transforms, and the domain model.
- **Fail-fast gates** — Validate at Bronze (source) and Gold (domain); do not propagate bad rows.
- **Separation of concerns** — Adapters handle publisher format; LinkML-Map handles remapping; Integrate handles cross-source reconciliation.
- **Experimental lane** — New transforms can be tested alongside production mappings before promotion to the domain schema.

## Milestone 1 — Ingestion pipeline

### Workflow

![Source ingestion workflow](docs/milestone_1/gckg-sources.png)

**Goal:** Implement Stage 1 (Ingest) end-to-end — a Python runner and one adapter per federal source family, each emitting source-shaped `records.jsonl` and a provenance `manifest.json` under `staging/`.

**Out of scope for M1:** Validate (Bronze), Transform (Silver), Integrate, Publish (Gold). Those follow once staging handoff is stable.

| Phase | Work | Output |
|-------|------|--------|
| **1 — Platform** | `pyproject.toml`, `python -m ingest`, adapter protocol + registry, fetch/cache layer, `sources.yaml`, staging layout, structured logging, pytest scaffold | `ingest run --source …` runs (even if adapter is stub) |
| **2 — MPs** | `commons_members` adapter: HTTP fetch, XML parse, normalize, emit | First real `staging/commons_members/{run_id}/` |
| **3 — Open Canada** | `open_canada_expenditure` (local-file), `open_canada_contributions` (HTTP) | Two CSV adapters + shared patterns |
| **4 — Commons** | `commons_votes`, `commons_petitions` (reuse XML utils) | Remaining Commons sources |
| **5 — Districts** | Port `normalize_districts.py` → `udc_districts` | Parity with legacy script output |
| **6 — Hardening** | `run-all`, cache-only CI fixtures, error paths, relocate legacy `ingest/source/` → `source/` | All six sources in one command |

### Adapter order

```
commons_members → open_canada_expenditure → open_canada_contributions
  → commons_votes → commons_petitions → udc_districts
```

### Done when

- [ ] All six adapters registered; `python -m ingest list-sources` lists them
- [ ] Each adapter writes `staging/{source}/{run_id}/records.jsonl` + `manifest.json` + `raw/` snapshot
- [ ] Fetch policies work: default, refresh, cache-only, local-file
- [ ] Unit tests use checked-in fixtures — no network in CI
- [ ] No GCKG domain IDs or cross-entity joins in Stage 1 output
- [ ] Legacy `ingest/scripts/`, `ingest/source/`, `ingest/transforms/` retired or relocated per file layout

## File layout

```
gckg/
├── pyproject.toml
│
├── domain_model/                           LinkML domain schema · Publish gate
│   ├── schema.yaml                         root import
│   ├── foundation/
│   │   └── types.yaml                      NamedEntity, Triple, …
│   └── domains/
│       ├── parliament.yaml                 MPs, districts, caucus
│       ├── finance.yaml                    expenditures, contributions
│       └── provenance.yaml                 Attribution, …
│
├── source/                                 LinkML source schemas · Validate gate
│   └── *.schema.yaml                       per-publisher row shapes
│
├── experimental/                           draft LinkML schemas and maps
│   └── *.yaml
│
├── transforms/                             LinkML-Map · Transform stage
│   └── *_to_gckg.yaml
│
├── ingest/                                 Python package · Stage 1 Ingest
│   ├── __init__.py
│   ├── __main__.py                         python -m ingest
│   ├── cli.py
│   ├── runner.py
│   ├── context.py                          RunContext, run_id
│   ├── errors.py                           FetchError, ParseError, …
│   │
│   ├── fetch/
│   │   ├── client.py                       HTTP, retries, conditional GET
│   │   └── cache.py                        TTL, sha256, url_hash paths
│   │
│   ├── adapters/
│   │   ├── base.py                         Adapter protocol
│   │   ├── registry.py                     source name → adapter class
│   │   ├── commons/
│   │   │   ├── members.py                  MPs XML
│   │   │   ├── votes.py                    votes XML
│   │   │   ├── petitions.py                petitions XML
│   │   │   └── xml_utils.py                shared XML helpers
│   │   ├── open_canada/
│   │   │   ├── expenditure.py              CSV (local-file)
│   │   │   └── contributions.py            CSV (HTTP)
│   │   └── udc/
│   │       └── districts.py                
│   │
│   ├── config/
│   │   └── sources.yaml                    URLs, TTL, rate limits
│   │
│   ├── tests/
│   │   ├── fixtures/raw/                   checked-in samples (no network in CI)
│   │   └── adapters/                       per-adapter unit tests
│
├── staging/                                gitignored
│   └── {source}/
│       ├── cache/
│       │   └── {url_hash}.{xml|csv}
│       └── {run_id}/
│           ├── raw/{filename}
│           ├── records.jsonl               → Validate
│           └── manifest.json
│
├── bronze/                                 gitignored
├── silver/                                 gitignored
├── gold/                                   gitignored
└── quarantine/                             gitignored
```
