# Stage 4 — Integrate

Merge per-source **Silver fragments** into one reconciled graph: dedupe by GCKG URI, union provenance, optional entity resolution across sources.

| | |
|--|--|
| **CLI** | `python3 -m pipeline.integrate` |
| **Tier** | Merged Silver |
| **Input** | One or more `universe/{run_id}/3-silver/{source}/fragments.jsonl` |
| **Output** | `universe/{run_id}/4-merged/` |

Introduces **no new GCKG IDs** — only reconciles IDs Stage 3 already minted.

## Commands

```bash
python3 -m pipeline.integrate run \
  --input commons_members \
  --input commons_members_bylaw \
  --input commons_members_expenditures \
  --run-id demo

# Members + expenditures: resolve Person stubs via Bronze crosswalk
python3 -m pipeline.integrate run \
  --run-id demo \
  --resolver pipeline.integrate.resolvers.commons_person.get_resolver \
  --input commons_members \
  --input commons_members_expenditures
```

### CLI flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--input` | required (repeatable) | Source name, or `source:silver_run_id` for cross-run silver |
| `--run-id` | UTC timestamp | Run directory under `universe/` |
| `--universe-root` | `universe` | Runtime output root |
| `--resolver` | `pipeline.integrate.resolvers.identity.get_resolver` | EntityResolver factory |
| `--members-bronze` | auto-discover | Explicit members Bronze path |
| `--expenditures-bronze` | auto-discover | Explicit expenditures Bronze path |
| `--person-crosswalk-tsv` | — | Pre-built uuid→person_id TSV |

## Resolvers

| Resolver | Factory | Purpose |
|----------|---------|---------|
| Identity (default) | `pipeline.integrate.resolvers.identity.get_resolver` | Exact-URI merge |
| Commons Person | `pipeline.integrate.resolvers.commons_person.get_resolver` | Map expenditure Person stubs → members Person URIs |

`commons_person` discovers Bronze paths from Silver manifests when `--members-bronze` / `--expenditures-bronze` are omitted.

## Output layout

```text
universe/{run_id}/4-merged/
  nodes.jsonl
  edges.jsonl
  manifest.json
  resolution_report.json
  quarantine.jsonl          shape errors, null ids, type conflicts
  conflicts.jsonl           subset of quarantine (when conflicts occur)
```

Output is **deterministic**: sorted keys, stable merge order.

## How it works

1. Read and classify each Silver fragment (node vs edge).
2. Apply `EntityResolver.canonical_id()` before grouping.
3. Merge nodes/edges by canonical URI; union attributes and `bronze_references`.
4. Normalize legacy `rel_type` → `predicate` on edges.
5. Write sorted `nodes.jsonl` / `edges.jsonl` + reports.

## Package layout

```text
integrate/
  cli.py
  runner.py
  engine.py           GraphAccumulator, fragment iteration
  context.py          IntegrateContext, SilverInput
  resolvers/
    identity.py
    commons_person.py
    commons_person_crosswalk.py
  tests/
```

## Handoff to Stage 5

```bash
python3 -m pipeline.publish run --run-id {run_id}
```
