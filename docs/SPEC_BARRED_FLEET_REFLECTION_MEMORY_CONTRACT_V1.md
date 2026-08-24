# Spec: BARRED-Fleet Reflection Memory Contract V1

## Objective

Define the first production-shaped reflection/memory contract for BARRED-Fleet after the cloud run lifecycle, GCS/Firestore artifact promotion, Model Armor screening, and Agent Gateway egress receipts are stable.

The goal is not to add autonomous prompt evolution immediately. The goal is to create a safe, auditable memory layer that can summarize completed runs and later support Graph-Powered GEPA/Pareto prompt evolution without corrupting deterministic acceptance.

## Assumptions

1. BARRED-Fleet remains a Cloud Run ADK service.
2. Firestore remains metadata-only; large artifacts stay in GCS.
3. Reflection memory reads from completed run reports and deterministic receipts, not raw uncontrolled prompt history.
4. B-gate remains the only vulnerability acceptance authority.
5. The first implementation should be read/write memory receipts and queries, not live prompt mutation.
6. Reflection/Pareto evolution is opt-in and disabled by default.

## Tech Stack

- Python 3.11
- FastAPI routes inside `barred-fleet/app/fast_api_app.py`
- BARRED-Fleet run lifecycle in `barred-fleet/app/run_lifecycle.py`
- Firestore collection for run metadata: `barred_runs`
- Proposed Firestore collection for reflection memory: `barred_reflection_memory`
- GCS artifact bucket: `gs://gem-creation-barred-fleet-artifacts`
- Google ADK root agent for narration/tool orchestration
- Model Armor and Agent Gateway remain safety controls before live execution

## Commands

Local tests:

```bash
cd /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one/barred-fleet
uv run pytest tests/unit/test_run_lifecycle.py tests/unit/test_agent_gateway.py tests/unit/test_model_armor.py -q
uv run pytest tests/unit -q
```

Cloud baseline checks:

```bash
cd /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one/barred-fleet
make verify-demo
make verify-fresh-demo
```

Deferred bounded live check:

```bash
cat /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one/docs/BARRED_FLEET_CLOUD_GATEWAY_LIVE_CHECKS.md
```

## Project Structure

```text
barred-fleet/app/reflection_memory.py
  Data contracts and deterministic memory compiler.

barred-fleet/app/fast_api_app.py
  Future read-only or admin-gated memory endpoints.

barred-fleet/app/run_lifecycle.py
  Source of artifact-backed run reports used by memory compilation.

barred-fleet/tests/unit/test_reflection_memory.py
  Contract tests for memory compilation, redaction, and Firestore payload shape.

docs/SPEC_GRAPH_POWERED_GEPA_REFLECTOR.md
  Long-range GEPA/Pareto reflector vision.

docs/SPEC_BARRED_FLEET_REFLECTION_MEMORY_CONTRACT_V1.md
  This constrained V1 contract.
```

## Memory Model

### Collection

```text
barred_reflection_memory/{memory_id}
```

### Document Shape

```json
{
  "memory_id": "sha256:<hash>",
  "source_run_id": "product-cloud-gateway-live-...",
  "source_report_uri": "gs://.../deterministic_eval_result.json",
  "created_at": "2026-08-22T00:00:00Z",
  "memory_kind": "run_outcome_summary",
  "predicate_family": "BUFFER_OVERFLOW",
  "seed_id": "fixture:first",
  "seed_source": "scenarios/debate/cve_seeds_test.jsonl",
  "seed_index": 0,
  "b_gate_passed": true,
  "promotion_status": "promoted",
  "verifier_parse_ok_rate": 1.0,
  "verifier_pass_rate": 1.0,
  "model_routes": {
    "generator": "vertex_ai/gemini-3.5-flash-lite",
    "judge": "vertex_ai/gemini-3.6-flash",
    "verifier": "vertex_ai/gemini-3.6-flash"
  },
  "safety_controls": {
    "model_armor_status": "configured",
    "agent_gateway_status": "configured",
    "agent_gateway_mode": "cloud_agent_gateway"
  },
  "diagnostic_bucket": "accepted",
  "lesson": "This seed produced an accepted, B-gate-passing artifact with verifier parse/pass receipts.",
  "negative_constraints": [],
  "positive_constraints": [
    "Preserve exact code anchors.",
    "Keep source/sink claims tied to deterministic artifacts."
  ],
  "raw_prompt_text_stored": false,
  "raw_seed_text_stored": false,
  "raw_code_text_stored": false,
  "schema_version": 1
}
```

## Reflection Contract

### Input

Reflection memory is compiled from `/runs/{run_id}/report`, not from arbitrary user text.

Required source fields:

- `run_id`
- `seed_id`
- `seed_metadata`
- `model_routes`
- `model_armor`
- `agent_gateway`
- `b_gate`
- `deterministic_eval`
- `promotion`
- `artifact_registry`
- `artifact_summary`

### Output

The compiler emits one `run_outcome_summary` memory record per completed or blocked run.

Allowed statuses:

```text
accepted
b_gate_rejected
content_safety_blocked
egress_policy_blocked
configuration_blocked
runner_failed
```

### Deterministic Classification Priority

1. If `model_armor.seed_screening.blocked=true`: `content_safety_blocked`
2. Else if `agent_gateway.egress_decision.blocked=true`: `egress_policy_blocked`
3. Else if lifecycle `status=blocked` and `error_category=configuration`: `configuration_blocked`
4. Else if lifecycle `status=failed`: `runner_failed`
5. Else if `b_gate.passed=true`: `accepted`
6. Else if `b_gate.passed=false`: `b_gate_rejected`
7. Else: `runner_failed`

## Code Style

Use explicit typed payload builders rather than passing raw report dictionaries through unbounded mutation.

```python
def compile_reflection_memory(report: Mapping[str, Any]) -> dict[str, Any]:
    """Compile one redacted memory document from an artifact-backed run report."""
    return {
        "memory_id": _memory_id(report),
        "source_run_id": str(report["run_id"]),
        "memory_kind": "run_outcome_summary",
        "diagnostic_bucket": _classify_report(report),
        "raw_prompt_text_stored": False,
        "raw_seed_text_stored": False,
        "raw_code_text_stored": False,
        "schema_version": 1,
    }
```

## Testing Strategy

Unit tests first:

- accepted run compiles to `diagnostic_bucket=accepted`
- B-gate rejected run compiles to `diagnostic_bucket=b_gate_rejected`
- Model Armor blocked run compiles to `content_safety_blocked`
- Agent Gateway blocked run compiles to `egress_policy_blocked`
- raw prompt/seed/code text is never stored
- memory ID is stable across repeated compilation of the same report
- Firestore payload stays metadata-only

No paid model calls are needed for V1 tests.

## Boundaries

### Always

- Compile memory only from artifact-backed product reports.
- Redact raw prompt, raw seed, and raw code text.
- Keep B-gate as acceptance authority.
- Store large evidence in GCS, not Firestore.
- Preserve local BARRED compatibility.

### Ask First

- Adding a new Firestore collection in production.
- Writing reflection memory from live cloud runs.
- Letting reflection memory alter prompts.
- Adding new model calls for reflection.
- Changing model routes.

### Never

- Store raw vulnerability source code in Firestore.
- Store raw prompts containing provider secrets or hidden instructions.
- Let reflection memory override deterministic B-gate.
- Treat an LLM reflection as accepted evidence.
- Auto-promote a prompt mutation from one successful run.

## Success Criteria

V1 is done when:

- `compile_reflection_memory(report)` exists and is fully unit-tested.
- Memory records are deterministic and stable for the same input report.
- Accepted, rejected, content-safety-blocked, and egress-blocked examples are covered.
- Firestore writer is optional and disabled by default.
- `/runs/{run_id}/report` remains unchanged and backward compatible.
- No live model calls are required to verify the memory compiler.

## Open Questions

1. Should reflection memory be stored in the same Firestore database as `barred_runs`, or in a separate collection/database for clearer access control?
2. Should V1 expose a read-only endpoint such as `GET /memory/{run_id}`, or keep memory compiler internal until GEPA evolution begins?
3. Should memory be generated only for promoted runs, or also for blocked/rejected runs to support negative learning?
4. What minimum number of accepted promoted runs should exist before prompt evolution is enabled?

## Recommended Next Slice

Implement only the deterministic compiler and tests:

```text
barred-fleet/app/reflection_memory.py
barred-fleet/tests/unit/test_reflection_memory.py
```

Do not implement prompt mutation yet. The next milestone is a trustworthy memory ledger, not autonomous optimization.
