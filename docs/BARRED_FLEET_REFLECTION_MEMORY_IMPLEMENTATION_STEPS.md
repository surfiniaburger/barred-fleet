# BARRED-Fleet Reflection Memory Implementation Steps

## Objective

Implement the BARRED-Fleet reflection memory layer without changing live debate behavior, deterministic B-gate acceptance, or existing `/runs` and `/demo` contracts.

The first fulfilled version is a deterministic memory compiler that converts an artifact-backed `/runs/{run_id}/report` payload into a small redacted Firestore-ready memory document.

## Non-Negotiable Rules

1. Do not let reflection memory decide vulnerability acceptance.
2. Do not store raw seed text, raw code text, raw prompts, provider traces, or hidden instructions in Firestore.
3. Do not trigger live model calls during unit tests.
4. Do not change model routes.
5. Do not change `/runs/{run_id}/report` response shape unless explicitly requested.
6. Keep memory writer optional and disabled by default.
7. Keep BARRED-Fleet local tests passing.

## Files To Add

```text
barred-fleet/app/reflection_memory.py
barred-fleet/tests/unit/test_reflection_memory.py
```

## Files To Avoid Changing In V1

```text
barred-fleet/app/agent.py
barred-fleet/app/fresh_debate.py
barred-fleet/app/model_armor.py
barred-fleet/app/agent_gateway.py
barred-fleet/scenarios/debate/*
```

Only touch those if a test proves the compiler cannot be implemented otherwise.

## Step 1: Define The Compiler Boundary

Create `barred-fleet/app/reflection_memory.py`.

Expose one public function first:

```python
def compile_reflection_memory(report: Mapping[str, Any]) -> dict[str, Any]:
    """Compile one redacted memory document from an artifact-backed run report."""
```

Acceptance:

- Function accepts a report dictionary.
- Function returns a Firestore-ready dictionary.
- Function does not mutate the input report.

Verification:

```bash
cd barred-fleet
uv run pytest tests/unit/test_reflection_memory.py -q
```

## Step 2: Implement Deterministic Classification

Classification priority must be exactly:

1. `model_armor.seed_screening.blocked=true` -> `content_safety_blocked`
2. `agent_gateway.egress_decision.blocked=true` -> `egress_policy_blocked`
3. lifecycle `status=blocked` and `error_category=configuration` -> `configuration_blocked`
4. lifecycle `status=failed` -> `runner_failed`
5. `b_gate.passed=true` -> `accepted`
6. `b_gate.passed=false` -> `b_gate_rejected`
7. fallback -> `runner_failed`

Recommended private helper:

```python
def classify_reflection_report(report: Mapping[str, Any]) -> str:
    ...
```

Acceptance:

- Each status is covered by a unit test.
- Classification does not call any external service.

## Step 3: Build Stable Memory IDs

Memory IDs should be stable for the same run and classification.

Recommended format:

```text
sha256:<hex>
```

Suggested hash inputs:

- `run_id`
- `diagnostic_bucket`
- `seed_id`
- `schema_version`

Acceptance:

- Same report compiles to the same `memory_id` repeatedly.
- Different run ID produces a different `memory_id`.

## Step 4: Extract Safe Metadata Only

Include:

- `memory_id`
- `source_run_id`
- `source_report_uri` if available
- `created_at`
- `memory_kind=run_outcome_summary`
- `predicate_family` if available; otherwise `unknown`
- `seed_id`
- `seed_source`
- `seed_index`
- `b_gate_passed`
- `promotion_status`
- `verifier_parse_ok_rate`
- `verifier_pass_rate`
- `model_routes`
- `safety_controls`
- `diagnostic_bucket`
- `lesson`
- `negative_constraints`
- `positive_constraints`
- `raw_prompt_text_stored=false`
- `raw_seed_text_stored=false`
- `raw_code_text_stored=false`
- `schema_version=1`

Do not include:

- raw seed topic/predicate/code
- attempt text
- prompt text
- model response text
- full artifact rows

Acceptance:

- Unit test asserts forbidden raw text keys are absent.
- Unit test asserts redaction booleans are false.

## Step 5: Generate Conservative Lessons

Lesson strings should be deterministic, short, and not overclaim.

Suggested mapping:

```text
accepted -> Accepted by deterministic B-gate with artifact-backed verifier receipts.
b_gate_rejected -> Generated artifact was rejected by deterministic B-gate; do not promote this pattern.
content_safety_blocked -> Model Armor blocked seed/content before live execution.
egress_policy_blocked -> Agent Gateway blocked route/tool egress before live execution.
configuration_blocked -> Run blocked by configuration before live execution completed.
runner_failed -> Run failed or lacked enough deterministic evidence for memory promotion.
```

Acceptance:

- Tests assert lesson text is present and bucket-specific.

## Step 6: Optional Firestore Payload Boundary

Do not write to Firestore yet unless explicitly asked.

If needed later, add a separate function:

```python
def build_reflection_memory_firestore_payload(memory: Mapping[str, Any]) -> dict[str, Any]:
    ...
```

Acceptance for future writer:

- Writer is opt-in.
- Writer is tested with a fake client.
- Writer stores metadata only.

## Step 7: Focused Tests To Add

Create `barred-fleet/tests/unit/test_reflection_memory.py` with these tests:

1. `test_compile_accepted_report_memory`
2. `test_compile_b_gate_rejected_report_memory`
3. `test_compile_model_armor_blocked_memory`
4. `test_compile_agent_gateway_blocked_memory`
5. `test_compile_configuration_blocked_memory`
6. `test_compile_runner_failed_memory`
7. `test_memory_id_is_stable`
8. `test_memory_document_is_redacted`

Keep fixtures small dictionaries. Do not load GCS, Firestore, or live artifacts.

## Step 8: Validation Commands

Run targeted tests:

```bash
cd /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one/barred-fleet
uv run pytest tests/unit/test_reflection_memory.py -q
```

Run nearby lifecycle tests:

```bash
uv run pytest tests/unit/test_run_lifecycle.py tests/unit/test_agent_gateway.py tests/unit/test_model_armor.py -q
```

Run full unit suite when time permits:

```bash
uv run pytest tests/unit -q
```

If `uv` cannot read cache because of sandboxing, rerun with normal terminal access or ask for elevated filesystem permission.

## Done Criteria

Reflection memory V1 is fulfilled when:

- `compile_reflection_memory` exists.
- All classification statuses are tested.
- Memory IDs are stable.
- Memory payload is redacted.
- No live calls are required.
- Existing unit tests remain green.
- Docs point future agents to this checklist and `docs/SPEC_BARRED_FLEET_REFLECTION_MEMORY_CONTRACT_V1.md`.

## Next After V1

Only after this deterministic compiler is stable:

1. Add optional Firestore writer behind an env flag.
2. Add read-only memory report endpoint.
3. Compile memory automatically after promoted product runs.
4. Collect several promoted and rejected runs.
5. Then start the Graph-Powered GEPA/Pareto prompt evolution experiment.
