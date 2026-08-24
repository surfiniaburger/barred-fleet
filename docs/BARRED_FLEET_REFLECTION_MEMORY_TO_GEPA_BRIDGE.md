# BARRED-Fleet Reflection Memory to GEPA Bridge

## Purpose

This document explains how the implemented BARRED-Fleet Reflection Memory V1 fits into `docs/SPEC_GRAPH_POWERED_GEPA_REFLECTOR.md`, what is intentionally not implemented yet, and the exact smoke tests another agent should run before extending toward Graph-Powered GEPA/Pareto prompt evolution.

## Current Implemented Layer

Implemented file:

```text
barred-fleet/app/reflection_memory.py
```

Implemented tests:

```text
barred-fleet/tests/unit/test_reflection_memory.py
```

The current layer compiles a deterministic memory document from an artifact-backed `/runs/{run_id}/report` payload.

It provides:

- stable `memory_id`
- source `run_id`
- seed metadata summary
- B-gate result
- promotion status
- verifier parse/pass rates
- model route summary
- Model Armor status
- Agent Gateway status
- deterministic coarse diagnostic bucket
- redaction guarantees

It does **not** write to Firestore yet. It does **not** mutate prompts. It does **not** run an LLM.

## Alignment With `SPEC_GRAPH_POWERED_GEPA_REFLECTOR.md`

The GEPA reflector spec requires a durable work-memory / lesson ledger before prompt mutation can be safe.

Reflection Memory V1 is that prerequisite substrate:

```text
/runs/{run_id}/report
  -> deterministic reflection memory compiler
  -> redacted memory document
  -> future Firestore memory ledger
  -> future GEPA/Pareto reflector
```

This is aligned because the GEPA spec needs historical evidence grouped by outcome and vulnerability family. V1 provides that without trusting raw model traces.

## What Is Still Missing From Full GEPA

Reflection Memory V1 does not yet implement:

- `GraphDiagnosticSignature`
- graph failure buckets such as:
  - `B_UNSUPPORTED_SYNTAX`
  - `B_LOGIC_ERROR`
  - `B_ANCHOR_UNMATCHED`
  - `B_SOURCE_MISSING`
  - `B_SINK_MISSING`
  - `B_SANITIZER_MISMATCH`
  - `B_SANITIZER_TARGET_MISMATCH`
- topology-indexed Pareto prompt variants
- `ReflectorAgent` A2A service
- prompt mutation
- prompt promotion / demotion
- cross-seed dead-end suppression
- time-decayed lesson scoring

Do not claim those are implemented until they are backed by code and tests.

## Current Memory Flow

```text
Cloud Run /runs product lifecycle
  -> GCS artifacts
  -> Firestore run status
  -> /runs/{run_id}/report
  -> compile_reflection_memory(report)
  -> redacted run_outcome_summary memory document
```

The compiler is intentionally deterministic.

B-gate remains the only vulnerability acceptance authority.

Model Armor remains content safety only.

Agent Gateway remains route/tool egress only.

The model may narrate reports, but it does not decide memory outcome or acceptance.

## Current Coarse Diagnostic Buckets

Current function:

```python
classify_reflection_report(report)
```

Priority order:

1. `model_armor.seed_screening.blocked=true` -> `content_safety_blocked`
2. `agent_gateway.egress_decision.blocked=true` -> `egress_policy_blocked`
3. lifecycle `status=blocked` and `error_category=configuration` -> `configuration_blocked`
4. lifecycle `status=failed` -> `runner_failed`
5. `b_gate.passed=true` -> `accepted`
6. `b_gate.passed=false` -> `b_gate_rejected`
7. fallback -> `runner_failed`

These are coarse run-outcome buckets. They are not GEPA graph buckets yet.

## GEPA-Compatible Optional Fields To Add Later

When graph diagnostics exist, extend memory documents with optional fields only. Do not require them for all runs.

Recommended optional fields:

```json
{
  "taxonomy_bucket": "memory_safety",
  "predicate_family": "BUFFER_OVERFLOW",
  "graph_failure_bucket": "B_SOURCE_MISSING",
  "source_id": "param:len",
  "sink_id": "call:memcpy",
  "sink_type": "MEMORY_COPY_CALL",
  "required_sanitizer": "BOUNDS_CHECK",
  "found_sanitizer": "NULL_CHECK",
  "target_var": "len",
  "guarded_target": "ptr",
  "failed_anchor_lines": ["memcpy(dst, src, len);"],
  "verifier_logic_error": false,
  "canonical_mutation_id": "baseline_v0",
  "pareto_variant_id": "baseline_v0",
  "outcome": "VALID_ACCEPT"
}
```

Rules:

- If graph fields are absent, keep coarse V1 memory valid.
- If graph fields are present, they must come from deterministic graph extraction or verifier artifacts, not LLM narration alone.
- Do not store raw code in Firestore; store anchor snippets only if already allowed and short.
- Use GCS for full artifacts.

## Step-By-Step Smoke Tests

### 1. Local Reflection Memory Unit Test

```bash
cd /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one/barred-fleet
uv run pytest tests/unit/test_reflection_memory.py -q
```

Expected:

```text
8 passed
```

### 2. Adjacent Lifecycle/Safety Tests

```bash
uv run pytest tests/unit/test_run_lifecycle.py tests/unit/test_agent_gateway.py tests/unit/test_model_armor.py -q
```

Expected:

```text
43 passed
```

### 3. Full Unit Suite

```bash
uv run pytest tests/unit -q
```

Expected current baseline:

```text
131 passed
```

Warnings from ADK/A2A experimental APIs are expected and not failures.

### 4. Manual Compile Smoke From A Tiny Report

```bash
cd /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one/barred-fleet
uv run python - <<'PY'
from app.reflection_memory import compile_reflection_memory

report = {
    "run_id": "manual-memory-smoke",
    "lifecycle": {"status": "completed", "error_category": ""},
    "seed_id": "fixture:first",
    "seed_metadata": {
        "source_file": "scenarios/debate/cve_seeds_test.jsonl",
        "index": 0,
        "predicate_family": "BUFFER_OVERFLOW",
    },
    "model_routes": {
        "generator": "vertex_ai/gemini-3.5-flash-lite",
        "judge": "vertex_ai/gemini-3.6-flash",
        "verifier": "vertex_ai/gemini-3.6-flash",
    },
    "model_armor": {
        "status": "configured",
        "mode": "cloud_model_armor",
        "seed_screening": {"blocked": False},
    },
    "agent_gateway": {
        "status": "configured",
        "mode": "cloud_agent_gateway",
        "egress_decision": {"blocked": False},
    },
    "b_gate": {
        "available": True,
        "passed": True,
        "selected_metrics": {
            "verifier_parse_ok_rate": 1.0,
            "verifier_pass_rate": 1.0,
        },
    },
    "deterministic_eval": {
        "available": True,
        "path": "gs://bucket/runs/manual-memory-smoke/deterministic_eval_result.json",
        "score": 1.0,
    },
    "promotion": {"status": "promoted", "reason": "gcs_and_firestore_written"},
}

memory = compile_reflection_memory(report)
print(memory["memory_id"])
print(memory["diagnostic_bucket"])
print(memory["raw_prompt_text_stored"], memory["raw_seed_text_stored"], memory["raw_code_text_stored"])
PY
```

Expected:

```text
sha256:<stable digest>
accepted
False False False
```

### 5. Cloud Run Report To Memory Smoke Later

Only after a product run exists and `/runs/{run_id}/report` is available:

```bash
cd /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one/barred-fleet
SERVICE_URL="https://barred-fleet-837262597425.us-east1.run.app"
RUN_ID="product-live-check-REPLACE_ME"
token="$(gcloud auth print-identity-token)"

curl -sS \
  -H "Authorization: Bearer $token" \
  "$SERVICE_URL/runs/$RUN_ID/report" \
  > /tmp/barred-run-report.json

uv run python - <<'PY'
import json
from app.reflection_memory import compile_reflection_memory

report = json.load(open("/tmp/barred-run-report.json"))
memory = compile_reflection_memory(report)
print(json.dumps({
    "memory_id": memory["memory_id"],
    "source_run_id": memory["source_run_id"],
    "diagnostic_bucket": memory["diagnostic_bucket"],
    "b_gate_passed": memory["b_gate_passed"],
    "promotion_status": memory["promotion_status"],
    "agent_gateway_mode": memory["safety_controls"]["agent_gateway_mode"],
}, indent=2))
PY
```

Expected for a fully green promoted run:

```json
{
  "diagnostic_bucket": "accepted",
  "b_gate_passed": true,
  "promotion_status": "promoted",
  "agent_gateway_mode": "cloud_agent_gateway"
}
```

If B-gate rejected the run, expected bucket is `b_gate_rejected`, not `accepted`.

## Step-By-Step Extension Path Toward GEPA

### Slice A: Optional Firestore Writer

Add:

```text
barred-fleet/app/reflection_memory_store.py
barred-fleet/tests/unit/test_reflection_memory_store.py
```

Requirements:

- env flag controls writes, e.g. `BARRED_REFLECTION_MEMORY_WRITES=true`
- collection env, e.g. `BARRED_REFLECTION_MEMORY_COLLECTION=barred_reflection_memory`
- fake writer tests first
- idempotent write by `memory_id`
- no raw text fields

### Slice B: Read-Only Memory Endpoint

Possible endpoints:

```text
GET /memory/{run_id}
GET /memory/by-run/{run_id}
```

Requirements:

- read-only
- authenticated Cloud Run only
- no write side effects
- return `not_found` cleanly

### Slice C: Compile Memory After Completed Product Runs

Hook after `/runs` lifecycle completion:

```text
run completes -> build report -> compile memory -> optional write
```

Requirements:

- disabled by default
- no effect on B-gate
- failures must not break run completion
- memory write failure logged as diagnostic only

### Slice D: Graph Diagnostic Adapter

Add optional graph fields to memory only when graph diagnostics exist.

Potential source:

```text
artifact_report.graph_diagnostics
fresh_report.graph_diagnostics
verifier_report.graph_diagnostic
```

Do not invent fields from model narration.

### Slice E: Pareto/GEPA Reflector

Only after several memory records exist:

- accepted runs
- B-gate rejected runs
- content safety blocked runs
- egress blocked runs
- graph diagnostic failures if available

Then implement:

```text
barred-fleet/app/reflector.py
barred-fleet/tests/unit/test_reflector.py
```

Prompt mutation must remain opt-in.

## Do Not Do Yet

- Do not add automatic prompt mutation.
- Do not start an A2A Reflector service.
- Do not modify debater/judge/verifier prompts based on one memory record.
- Do not store full code or raw prompts in Firestore.
- Do not claim Pareto evolution exists before mutation history and tests exist.

## Handoff Summary For Another Agent

If picking this up from scratch:

1. Read `docs/SPEC_BARRED_FLEET_REFLECTION_MEMORY_CONTRACT_V1.md`.
2. Read `docs/BARRED_FLEET_REFLECTION_MEMORY_IMPLEMENTATION_STEPS.md`.
3. Read this bridge document.
4. Run `uv run pytest tests/unit/test_reflection_memory.py -q`.
5. Inspect `barred-fleet/app/reflection_memory.py`.
6. If extending, start with optional Firestore writer tests; do not implement prompt mutation yet.
