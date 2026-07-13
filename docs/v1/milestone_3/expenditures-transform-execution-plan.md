# Execution plan — Stage 3 Transform: `commons_members_expenditures`

**Stage 3** maps Bronze `records.jsonl` for House of Commons member expenditure reports to **Silver graph fragments**, using a YAML transform spec executed by **`YamlMapEngine`** (`transforms/map_engine.py`).

**Overview:** see [`README.md`](README.md) for current status across all Stage 3 sources.

**Source:** `commons_members_expenditures` — pickle corpus of contract / hospitality / travel CSVs (see `ingest/adapters/commons/members_expenditures.py`).

**As shipped:** all five Bronze row classes are covered in `transforms/schemas/commons_members_expenditures_to_gckg.transform.yaml` and registered in `transforms/config/maps.yaml` with `map_mode: yaml`. The original plan called for a `LinkMapEngine` wrapper around `linkml-map`; that path was deferred in favour of `YamlMapEngine`.

Implement **top to bottom**. Each section: **what it does** → design guidance, with current state called out.

---

## Implementation status (actual)

| Area | State |
|------|-------|
| Stage 1 ingest adapter | **Done** — five Bronze row classes, `_row_class` tagging |
| Source schema | **Done** — `source/commons_members_expenditures.schema.yaml` |
| Stage 2 validate path | **Done** — registered in `validate/config/schemas.yaml` |
| Domain model (expense classes) | **Done** — claim/report/relationship classes in `house_of_commons.yaml` + `business.yaml` |
| Transform spec | **Done** — `transforms/schemas/commons_members_expenditures_to_gckg.transform.yaml` |
| `maps.yaml` entry | **Done** — `map_mode: yaml` |
| `YamlMapEngine` runtime | **Done** — all row classes materialize Silver fragments |
| `LinkMapEngine` (`map_mode: linkml`) | **Deferred** — not needed; `YamlMapEngine` shipped |
| End-to-end Bronze → Silver run | **Done** |
| Tests | **Partial** — covered by `transforms/tests/test_map_engine.py` (bylaw/members tests; add expenditures-specific cases) |

---

## Prerequisites

| Requirement | Status |
|-------------|--------|
| Bronze layout | Adapter emits rows; full pipeline run depends on ingest + validate being wired |
| Source schema | Done — 5 row classes |
| Domain model | Partial — reconcile spec ↔ domain before `validate-spec` |
| `linkml-map` dependency | Not added — add under `[project.optional-dependencies] transform` |
| `transforms/` runner | Done — extend `_build_engine()` for `map_mode: linkml` |

**Handoff contract:** Transform reads **Bronze only**.

```text
bronze/commons_members_expenditures/{bronze_run_id}/records.jsonl
  →  Transform (LinkMapEngine — row-by-row ObjectTransformer)
  →  silver/commons_members_expenditures/{run_id}/fragments.jsonl
  →  silver/commons_members_expenditures/{run_id}/quarantine.jsonl
  →  silver/commons_members_expenditures/{run_id}/manifest.json
```

---

## Design decisions

1. **Row-by-row LinkML-Map, not batch CLI.** Bronze is heterogeneous JSONL (`_row_class` per line). Use `ObjectTransformer.map_object(row, source_type=..., class_derivation=...)` inside the existing runner loop — same outer contract as `YamlMapEngine` and Stage 2 validate.

2. **One Bronze row → many Silver fragments.** A single `ContractExpenditureRow` must emit **six** fragments today (Person, Supplier/Agent, ContractExpenseClaim, report→claim edge, principal-party edge, supplier edge). The wrapper loops all `class_derivations` whose `populated_from` matches the row class; linkml-map's default lookup returns only one derivation per call.

3. **Silver envelope stays GCKG-specific.** linkml-map produces target-shaped dicts. The wrapper adds `@type` (derivation name), `bronze_reference`, and normalizes relationship slot names to match domain triple classes.

4. **Deterministic IDs in the spec.** All URI templates live in `.transform.yaml` `expr:` fields — not Python materializers.

5. **Entity resolution deferred to Stage 4.** Expenditure Bronze carries `member_disclosure_uuid` and parsed `member_name`, not `PersonId`. Transform emits **source-scoped** Person stubs (`gckg:Commons:ContractExpenseClaim:Person:{member_name}`) and Integrate resolves to canonical `gckg:Person:Commons:{person_id}` later.

6. **Phased row-class rollout.** Contract → hospitality → travel summary → travel segments. Do not block contract on travel domain work.

7. **`when:` guards.** Bylaw maps use GCKG's `when:` extension (implemented in `YamlMapEngine`). linkml-map has no native row guard — implement in `LinkMapEngine` wrapper until upstream adds it, or encode guards inside `expr` / skip derivations with empty required fields.

---

## Bronze row classes → Silver targets

### Row inventory

| `_row_class` | Emitted by | Approx. volume (corpus) |
|--------------|------------|-------------------------|
| `ExpenseReportRow` | Once per CSV file | ~11k |
| `ContractExpenditureRow` | Contract line items | ~296k |
| `HospitalityExpenditureRow` | Hospitality line items | ~20k |
| `TravelExpenditureRow` | Travel claim summary rows | ~46k |
| `TravelClaimSegmentRow` | Travel trip legs | ~155k |

### Target fragments per row (contract — reference implementation)

One `ContractExpenditureRow` → **6 fragments**:

| Domain object | ID pattern (example) | Bronze fields |
|---------------|----------------------|---------------|
| `Person` | `gckg:Commons:ContractExpenseClaim:Person:{member_name}` | `member_name` |
| `Supplier` | `gckg:Commons:Supplier:{supplier}` | `supplier` |
| `ContractExpenseClaim` | `gckg:Commons:ContractExpenseClaim:{uuid}:{year}:{quarter}:{row_index}` | report context + line fields |
| `MembersExpenditureReportHasContractExpenseClaim` | composite edge id | report id → claim id |
| `ContractExpenserClaimHasPrincipalParty` | composite edge id | claim → Person stub |
| `ContractExpenserClaimHasSupplier` | composite edge id | claim → Supplier |

One `ExpenseReportRow` → **1 fragment**:

| Domain object | ID pattern | Bronze fields |
|---------------|------------|---------------|
| `MembersExpenditureReport` | `gckg:Commons:MembersExpenditureReport:{uuid}:{year}:{quarter}` | report context + quarter bounds |

### Hospitality (planned)

One `HospitalityExpenditureRow` → **5–6 fragments** (mirror contract):

- `HospitalityExpenseClaim`, `Supplier`, report→claim edge, supplier edge
- Optional `Person` stub from report title (not on line row — may require denormalizing `member_name` onto line rows in adapter, or emitting Person only from `ExpenseReportRow`)

### Travel (planned — domain prep required)

One `TravelExpenditureRow` → claim node + report→claim edge + funding edge (optional).

One `TravelClaimSegmentRow` → **new domain class** `TravelClaimSegment` (or equivalent) + `TravelExpenseClaimHasPartTravelClaimSegment` edge. Segment rows carry route/traveller detail; summary rows carry monetary totals.

**Claim ID scoping:** always include `(member_disclosure_uuid, report_year, report_quarter, claim_id)` in IDs — 292 claim IDs repeat across reports.

---

## Spec drift to reconcile (existing contract YAML)

File: `transforms/schemas/commons_members_expense_report_to_gckg.transform.yaml`

| Issue | Spec says | Source schema says | Action |
|-------|-----------|-------------------|--------|
| Row sequence key | `row_number` | `row_index` | Fix expr |
| Expense date slot | `date_time` on claim | `expense_date` on `ContractExpenditureRow` | Fix slot_derivations |
| Supplier target | `Agent` + `ContractExpenseClaimHasContractParty` | Domain uses `Supplier` + `ContractExpenserClaimHasSupplier` | Align names to domain |
| Principal-party edge | `ContractExpenseClaimHasPrincipalParty` | Domain: `ContractExpenserClaimHasPrincipalParty` | Fix derivation name |
| Person ID namespace | `gckg:Commons:ContractExpenseClaim:Person:…` | Accept as source-scoped stub until Integrate | Document in spec header |
| Hospitality / travel | Empty `populated_from` blocks | Full row classes exist | Complete derivations |
| File naming | `…expense_report…` | Source name `commons_members_expenditures` | Rename or alias in `maps.yaml` |

Run after fixes:

```bash
linkml-map validate-spec \
  --source-schema source/commons_members_expenditures.schema.yaml \
  --target-schema domain_model/schema.yaml \
  transforms/schemas/commons_members_expense_report_to_gckg.transform.yaml
```

---

## Work breakdown

| Phase | Work | Output |
|-------|------|--------|
| **0 — Domain prep** | Fix relationship typos; add travel segment class + HAS_PART triple if needed; `gen-yaml` passes | Updated `house_of_commons.yaml` |
| **1 — Platform** | `LinkMapEngine` + `map_mode: linkml` in runner; `linkml-map` optional dep | `transforms/link_map_engine.py` |
| **2 — Validate path** | Register source in `validate/config/schemas.yaml`; Bronze gate | `validate run --source commons_members_expenditures` |
| **3 — Spec (contract)** | Fix drift; complete all contract derivations | Validated transform YAML |
| **4 — Spec (hospitality)** | Add claim + edge derivations | Validated transform YAML |
| **5 — Spec (travel)** | Summary + segment derivations; `when:` on row kind if needed | Validated transform YAML |
| **6 — Registry** | `maps.yaml` + path under `transforms/schemas/` | Runnable transform config |
| **7 — Tests** | Dispatch table, per-class smoke, ID determinism, multi-fragment counts | `transforms/tests/test_expenditures_map.py` |
| **8 — Pilot run** | Subsample pickle → ingest → validate → transform | `silver/commons_members_expenditures/{run_id}/` |

---

## Phase 1 — `LinkMapEngine`

**What:** Thin wrapper around linkml-map's `ObjectTransformer` with the same interface as `YamlMapEngine`.

**File:** `transforms/link_map_engine.py`

```python
class LinkMapEngine:
    def __init__(
        self,
        map_path: Path,
        source_schema_path: Path,
        target_schema_path: Path,
        bronze_reference_factory: Callable[[int], dict] | None = None,
        default_row_class: str | None = None,
        unrestricted_eval: bool = True,  # GCKG specs use Python-style expr today
    ): ...

    def materialize(self, row: dict, line_number: int) -> Iterator[dict]:
        row_class = row.get("_row_class") or self.default_row_class
        payload = {k: v for k, v in row.items() if k != "_row_class"}
        for class_deriv in self._dispatch.get(row_class, []):
            if self._when_guard(class_deriv, payload) is False:
                continue
            result = self._transformer.map_object(
                payload,
                source_type=row_class,
                class_derivation=class_deriv,
            )
            yield self._to_silver_fragment(class_deriv, result, line_number)
```

**Dispatch table construction:** group `specification.class_derivations` by `populated_from` (same algorithm as `YamlMapEngine._build_dispatch`). Reuse or extract shared `build_dispatch(spec) -> dict[str, list[ClassDerivation]]`.

**Runner wiring** (`transforms/runner.py`):

```yaml
# transforms/config/maps.yaml
commons_members_expenditures:
  map_mode: linkml
  map_path: transforms/schemas/commons_members_expense_report_to_gckg.transform.yaml
  source_schema: source/commons_members_expenditures.schema.yaml
  target_schema: domain_model/schema.yaml
```

**Dependency** (`pyproject.toml`):

```toml
[project.optional-dependencies]
transform = ["linkml-map>=0.6", "linkml>=1.9.0"]
```

**Fallback:** If linkml-map is not installed, document `map_mode: yaml` with the same spec file for local dev (expr syntax is already Python-locals compatible with `YamlMapEngine`).

---

## Phase 3 — Contract transform spec (complete)

**What:** Finish and validate the contract portion of the transform YAML.

**Derivations for `ContractExpenditureRow` (6):**

```yaml
class_derivations:
  Person:
    populated_from: ContractExpenditureRow
    slot_derivations:
      id:
        expr: "'gckg:Commons:ContractExpenseClaim:Person:' + str(member_name)"
      name:
        expr: "member_name"

  Supplier:
    populated_from: ContractExpenditureRow
    slot_derivations:
      id:
        expr: "'gckg:Commons:Supplier:' + str(supplier)"
      name:
        expr: "supplier"

  ContractExpenseClaim:
    populated_from: ContractExpenditureRow
    slot_derivations:
      id:
        expr: >-
          'gckg:Commons:ContractExpenseClaim:' + str(member_disclosure_uuid)
          + ':' + str(report_year) + ':' + str(report_quarter)
          + ':' + str(row_index)
      description:
        expr: "description"
      expense_date:
        expr: "expense_date"
      total:
        expr: "total"

  MembersExpenditureReportHasContractExpenseClaim:
    populated_from: ContractExpenditureRow
    slot_derivations:
      id: { expr: "…" }
      subject: { expr: "'gckg:Commons:MembersExpenditureReport:' + …" }
      predicate: { expr: "'CLAIM'" }
      object: { expr: "'gckg:Commons:ContractExpenseClaim:' + …" }

  ContractExpenserClaimHasPrincipalParty:
    populated_from: ContractExpenditureRow
    # subject → claim, object → Person stub

  ContractExpenserClaimHasSupplier:
    populated_from: ContractExpenditureRow
    # subject → claim, object → Supplier
```

**Derivations for `ExpenseReportRow` (1):** `MembersExpenditureReport` with `start_date` / `end_date` from quarter bounds.

**ID helper convention:** define once in spec comments; all edges reference the same claim/report URI templates (no duplicated typo risk across derivations).

---

## Phase 4 — Hospitality transform spec

**What:** Flat 8-column rows — structurally similar to contract.

| Derivation | `populated_from` |
|------------|------------------|
| `HospitalityExpenseClaim` | `HospitalityExpenditureRow` |
| `Supplier` | `HospitalityExpenditureRow` |
| `MembersExpenditureReportHasHospitalityExpenseClaim` | `HospitalityExpenditureRow` |
| `HospitalityExpenseClaimFundedByMiscellaneousExpendituresAccount` | optional — defer if MEA node not materialized |

Claim key: `(member_disclosure_uuid, report_year, report_quarter, claim_id)`.

---

## Phase 5 — Travel transform spec

**What:** Two row kinds per claim group; requires domain class for segments.

### Domain additions (Phase 0)

```yaml
TravelClaimSegment:
  is_a: Entity
  slots:
    - id
    - traveller_name
    - traveller_type
    - description
    - departure
    - destination
    - segment_date

TravelExpenseClaimHasPartTravelClaimSegment:
  is_a: Relationship
  attributes:
    subject: { range: TravelExpenseClaim }
    predicate: { ifabsent: "HAS_PART" }
    object: { range: TravelClaimSegment }
```

### Spec sketch

| Derivation | `populated_from` | Notes |
|------------|------------------|-------|
| `TravelExpenseClaim` | `TravelExpenditureRow` | Monetary totals + dates |
| `MembersExpenditureReportHasTravelExpenseClaim` | `TravelExpenditureRow` | |
| `TravelClaimSegment` | `TravelClaimSegmentRow` | Route / traveller |
| `TravelExpenseClaimHasPartTravelClaimSegment` | `TravelClaimSegmentRow` | subject = claim id from shared context |
| `Person` (stub) | `TravelClaimSegmentRow` | `when: "traveller_name is not None"` |

---

## Phase 7 — Tests

**File:** `transforms/tests/test_expenditures_map.py`

| Test | Asserts |
|------|---------|
| `test_dispatch_covers_all_row_classes` | 5 Bronze classes have ≥1 derivation |
| `test_contract_row_emits_six_fragments` | Fragment count + `@type` set |
| `test_expense_report_row_emits_one_fragment` | `MembersExpenditureReport` |
| `test_claim_id_deterministic` | Same Bronze → same claim URI |
| `test_bronze_reference_injected` | `line_number` preserved |
| `test_hospitality_smoke` | 1 row → expected types |
| `test_travel_summary_and_segment` | Summary vs segment derivations fire on correct `_row_class` |

Use inline spec fixtures for `when:` guards; use full YAML file for integration smoke.

---

## Phase 8 — Pilot run

```bash
# Stage 1 — Ingest (subsample or full pickle)
python -m ingest run \
  --source commons_members_expenditures \
  --fetch-policy local-file \
  --input data/expense_claims.pkl \
  --run-id exp-pilot

# Stage 2 — Validate
python -m validate run \
  --source commons_members_expenditures \
  --staging-run-id exp-pilot \
  --run-id exp-pilot

# Stage 3 — Transform
python -m transforms run \
  --source commons_members_expenditures \
  --bronze-run-id exp-pilot \
  --run-id exp-pilot

# Inspect
head -n 20 silver/commons_members_expenditures/exp-pilot/fragments.jsonl
python -c "
import json
from collections import Counter
types = Counter()
with open('silver/commons_members_expenditures/exp-pilot/fragments.jsonl') as f:
    for line in f:
        types[json.loads(line)['@type']] += 1
print(types.most_common())
"
```

**Success criteria (contract-only pilot):**

- [ ] Zero quarantine rows on adapter test fixture
- [ ] ~6 × contract line fragments + 1 × report fragment per contract CSV
- [ ] All fragments carry `bronze_reference`
- [ ] `linkml-map validate-spec` passes on transform YAML
- [ ] Spot-check: claim URI stable across re-run

---

## Out of scope (this plan)

| Item | Stage |
|------|-------|
| UUID / name → `PersonId` resolution | Stage 4 Integrate |
| `MiscellaneousExpendituresAccount` / FUNDS edges | Later — needs MEA entity decision |
| Cross-source join to `commons_members` tenure intervals | Stage 4 |
| Gold / SHACL validation | Stage 5 Publish |
| Full 500k+ row production run | After pilot + perf check |

---

## Checklist (copy for PR tracking)

- [ ] Domain typos fixed; travel segment class added
- [ ] `linkml-map` optional dependency + `LinkMapEngine`
- [ ] `validate/config/schemas.yaml` entry
- [ ] Contract spec drift fixed; `validate-spec` green
- [ ] Hospitality derivations complete
- [ ] Travel + segment derivations complete
- [ ] `maps.yaml` entry for `commons_members_expenditures`
- [ ] Tests pass
- [ ] End-to-end pilot on fixture / subsample
- [ ] README / milestone_3 note updated
