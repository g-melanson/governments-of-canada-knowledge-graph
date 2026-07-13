# GCKG — Canadian Governments Knowledge Graph

A schema-first knowledge graph that unifies Canadian federal parliamentary and open-government data into a single, validated, queryable graph.

**Current focus:** End-to-end pipeline on three House of Commons sources — **`commons_members`**, **`commons_members_bylaw`**, and **`commons_members_expenditures`** — from ingest through publish. Justice Canada and Open Canada sources have LinkML schemas or investigation docs but are not wired into the runtime pipeline yet.

## Background

Federal political data in Canada is published across multiple systems with different formats, update cadences, and identifiers. Each source is authoritative for its domain, but none was designed to interoperate. The same person, district, or organization appears under different names and keys in different datasets. Without a shared domain model and a disciplined ingest pipeline, cross-source analysis requires ad hoc joins, brittle one-off scripts, and manual reconciliation whenever a publisher changes shape.

GCKG addresses that fragmentation by treating the knowledge graph as a product: typed entities and relationships, explicit provenance, and validation at every boundary.

## Objective

Build a reproducible pipeline that ingests heterogeneous Canadian government sources and produces a **domain-conformant knowledge graph** suitable for research, civic tooling, and downstream applications (SPARQL, graph databases, API layers).

## Success criteria

The project succeeds when:

1. **End-to-end Commons path** — All three registered Commons sources flow through all five stages (ingest → validate → transform → integrate → publish) and produce Gold-tier graph output.
2. **Schema discipline** — Every record is validated against LinkML schemas at Bronze (source shape) and Gold (domain shape); drift is caught early and rejected records are quarantined with a report.
3. **Declarative transforms** — Bronze-to-domain remapping is defined in YAML transform specs under `sources/`, executed by `YamlMapEngine` — not buried in per-source Python.
4. **Integrated graph** — Entity resolution and merge produce a single reconciled graph where the same person resolves to one identifier across sources.
5. **Gold-tier output** — Published data passes domain validation and contains only graph-native, domain-conformant assertions.
6. **Reproducibility** — A run can be repeated with the same inputs and schemas to produce an auditable, versioned output.

Additional source families (Justice legislation, Open Canada, Urban Data Centre) extend the same pipeline once the Commons path is stable.

## Getting started

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,validate]"
```

Run each stage as a module (`python3 -m pipeline.<stage>`). Full documentation, E2E commands, and universe layout: **[`pipeline/README.md`](pipeline/README.md)**.

| Stage | Module | README |
|-------|--------|--------|
| 1 — Ingest | `python3 -m pipeline.ingest` | [`pipeline/ingest/README.md`](pipeline/ingest/README.md) |
| 2 — Validate | `python3 -m pipeline.validate` | [`pipeline/validate/README.md`](pipeline/validate/README.md) |
| 3 — Transform | `python3 -m pipeline.transforms` | [`pipeline/transforms/README.md`](pipeline/transforms/README.md) |
| 4 — Integrate | `python3 -m pipeline.integrate` | [`pipeline/integrate/README.md`](pipeline/integrate/README.md) |
| 5 — Publish | `python3 -m pipeline.publish` | [`pipeline/publish/README.md`](pipeline/publish/README.md) |

Lint LinkML blueprints from repo root:

```bash
cd sources/commons_members && gen-yaml commons_members.schema.yaml
cd schemas && gen-yaml schema.yaml
```

**Local data dependency:** `commons_members_expenditures` reads a pickle corpus at `data/expense_claims.pkl` (not checked into git).

## Pipeline overview

Five-stage medallion pipeline. Runtime output under **`universe/`** (gitignored). Path geometry: [`pipeline/paths.py`](pipeline/paths.py).

| Stage | Purpose | Tier |
|-------|---------|------|
| **1 — Ingest** | Parse raw publisher data; `SchemaNormalizer` | `universe/{run_id}/1-staging/` |
| **2 — Validate** | LinkML source-schema gate | Bronze · `universe/{run_id}/2-bronze/` |
| **3 — Transform** | `YamlMapEngine` → graph fragments | Silver · `universe/{run_id}/3-silver/` |
| **4 — Integrate** | Merge, dedupe, entity resolution | Merged · `universe/{run_id}/4-merged/` |
| **5 — Publish** | LinkML domain-schema gate | Gold · `universe/{run_id}/5-gold/` |

Diagrams: [`pipeline/diagrams/pipeline.mmd`](pipeline/diagrams/pipeline.mmd) · [`pipeline/diagrams/sources.mmd`](pipeline/diagrams/sources.mmd)

## File layout

```text
gckg/
├── pipeline/           Stage 1–5 runners + paths.py + per-stage READMEs
├── sources/            Per-source adapter, source schema, transform map
├── schemas/            Domain LinkML (Gold gate) + discovery schemas
├── universe/           Runtime pipeline output (gitignored)
├── tools/              Neo4j import, source investigator, …
└── docs/               Guides and source investigation assessments
```

## Investigation-only sources

LinkML schemas and impact assessments exist; no runtime adapter yet:

| Source | Schema | Assessment |
|--------|--------|------------|
| Justice legislation catalog | `schemas/discovery/justice_legis_catalog.schema.yaml` | [`docs/source_investigator/assessments/justice_legis_catalog.md`](docs/source_investigator/assessments/justice_legis_catalog.md) |
| Justice statute (Part I) | `schemas/discovery/justice_statute_p1.schema.yaml` | [`docs/source_investigator/assessments/justice_statute_p1.md`](docs/source_investigator/assessments/justice_statute_p1.md) |

## Related docs

- [`docs/ingest-adapter-refactor-guide.md`](docs/ingest-adapter-refactor-guide.md) — onboarding a new source (some paths legacy)
- [`docs/knowledge-graph-template-guide.md`](docs/knowledge-graph-template-guide.md) — template backbone guide (some paths legacy)
- [`docs/source_investigator/`](docs/source_investigator/) — profiling and impact assessments
