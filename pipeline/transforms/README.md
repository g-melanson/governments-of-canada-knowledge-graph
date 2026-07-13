# Stage 3 — Transform

Map Bronze records to **Silver graph fragments**: typed nodes and reified edges with GCKG URIs and `bronze_reference` provenance.

| | |
|--|--|
| **CLI** | `python3 -m pipeline.transforms` |
| **Tier** | Silver (per source) |
| **Input** | `universe/{run_id}/2-bronze/{source}/` |
| **Output** | `universe/{run_id}/3-silver/{source}/` |

Cross-source merge is **Stage 4** (Integrate).

## Commands

```bash
python3 -m pipeline.transforms run \
  --source commons_members \
  --run-id demo
```

### CLI flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--source` | required | Source name |
| `--run-id` | UTC timestamp | Run directory under `universe/` |
| `--bronze-run-id` | same as `--run-id` | Override Bronze input when it differs |
| `--universe-root` | `universe` | Runtime output root |

## Transform specs

All Commons sources use **`YamlMapEngine`** (`map_engine.py`) with `map_mode: yaml` in [`config/maps.yaml`](config/maps.yaml):

| Source | Transform map |
|--------|---------------|
| `commons_members` | `sources/commons_members/commons_members_to_gckg.transform.yaml` |
| `commons_members_bylaw` | `sources/commons_members_bylaw/commons_members_bylaw_to_gckg.transform.yaml` |
| `commons_members_expenditures` | `sources/commons_members_expenditures/commons_members_expenditures_to_gckg.transform.yaml` |

Specs define `class_derivations` / `slot_derivations` per Bronze `_row_class`. A legacy Python materializer path exists in the runner but is unused by current sources.

## Output layout

```text
universe/{run_id}/3-silver/{source}/
  fragments.jsonl       one graph node or edge per line
  quarantine.jsonl      Bronze rows that failed materialization
  manifest.json
```

Each fragment is either:

- a **node**: `@type`, `id`, attributes
- an **edge**: `@type`, `subject`, `predicate`, `object` (reified relationship)

## Package layout

```text
transforms/
  cli.py
  runner.py
  map_engine.py       YamlMapEngine (active)
  engine.py           Bronze record iteration
  context.py
  config/maps.yaml
  tests/test_map_engine.py
```

Lint transform maps from repo root:

```bash
cd sources/commons_members && gen-yaml commons_members_to_gckg.transform.yaml
```

## Handoff to Stage 4

```bash
python3 -m pipeline.integrate run \
  --input commons_members \
  --input commons_members_bylaw \
  --input commons_members_expenditures \
  --run-id {run_id}
```
