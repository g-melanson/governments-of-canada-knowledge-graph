# Milestone 3 — Transform pipeline (Stage 3 / Silver)

**Goal:** Transform Bronze records into **Silver graph fragments** with GCKG domain IDs and typed entities/relationships.

**As implemented:** transformation is performed by **`YamlMapEngine`** (`transforms/map_engine.py`). Transform specs under `transforms/schemas/*.transform.yaml` define `class_derivations` / `slot_derivations` per Bronze `_row_class`. All three Commons sources use `map_mode: yaml` in `transforms/config/maps.yaml`. The legacy Python materializer path remains in the runner but is unused.

| Stage | Tier | Package | CLI |
|-------|------|---------|-----|
| 3 — Transform | Silver (per source) | `transforms/` | `python -m transforms run …` |

**Execution plans:**

- [`transform-execution-plan.md`](transform-execution-plan.md) — platform and members/bylaw transforms
- [`expenditures-transform-execution-plan.md`](expenditures-transform-execution-plan.md) — expenditures transform (originally planned for `LinkMapEngine`; shipped via `YamlMapEngine`)

## Transform specs (today)

| Source | Spec | Coverage |
|--------|------|----------|
| `commons_members` | `transforms/schemas/commons_members_to_gckg.transform.yaml` | Person, MemberOfParliament, tenure triple |
| `commons_members_bylaw` | `transforms/schemas/commons_members_bylaw_to_gckg.transform.yaml` | Bylaw structure, defined terms, cross-references |
| `commons_members_expenditures` | `transforms/schemas/commons_members_expenditures_to_gckg.transform.yaml` | Reports, claims, Person stubs, reified triples |

## Output layout

```text
silver/{source}/{run_id}/
  fragments.jsonl
  quarantine.jsonl          # Bronze rows that failed materialization
  manifest.json
```

Silver is **per-source**. Cross-source merge is Stage 4 (Integrate).

## Done criteria

- [x] `transforms/` package with CLI, runner, `YamlMapEngine`
- [x] Three Commons sources materialize Silver end-to-end
- [x] Deterministic GCKG IDs and `bronze_reference` on every fragment
- [x] `transforms/tests/test_map_engine.py` + `transforms` console script
- [ ] Materialize District + Seat + Party + named tenure triples for members
- [ ] Experimental lane (`--map` / `experimental/` directory)
- [ ] `linkml-map` / `LinkMapEngine` path — deferred; `YamlMapEngine` is sufficient today

## Handoff to Stage 4

```bash
python -m integrate run \
  --input commons_members:{run_id} \
  --input commons_members_bylaw:{run_id} \
  --input commons_members_expenditures:{run_id} \
  --run-id {run_id}-merged
```
