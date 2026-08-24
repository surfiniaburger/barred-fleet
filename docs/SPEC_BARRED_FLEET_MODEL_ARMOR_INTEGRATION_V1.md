# Spec: BARRED-Fleet Model Armor Integration V1

## Objective
Add a real Model Armor integration after the local safety receipt is stable, without weakening deterministic BARRED acceptance.

Model Armor should screen unsafe text processing boundaries. It must not decide whether vulnerability evidence is accepted. BARRED B-gate remains the acceptance authority.

## Current Baseline
- `/runs` and `/runs/{run_id}/report` expose `safety_policy`.
- `/runs` and `/runs/{run_id}/report` expose `safety_receipt`.
- `/runs/{run_id}/report` exposes cloud safety placeholders:
  - `model_armor.status = "not_configured"`
  - `agent_gateway.status = "not_configured"`
- Planned/dry-run reports do not try to read missing final artifacts.
- Local adapter baseline:
  - `BARRED_MODEL_ARMOR_MODE` defaults to `not_configured`.
  - `BARRED_MODEL_ARMOR_MODE=local_blocklist` is test/demo-only and is not Cloud Model Armor.
  - Unsupported modes fail closed before live model calls.

## Cloud Model Armor Mode

### Environment Contract
Cloud Model Armor must be explicitly enabled:

```text
BARRED_MODEL_ARMOR_MODE=cloud_model_armor
BARRED_MODEL_ARMOR_PROJECT=<project-id>
BARRED_MODEL_ARMOR_LOCATION=<region>
BARRED_MODEL_ARMOR_TEMPLATE_ID=<template-id>
```

Fallbacks:

- `BARRED_MODEL_ARMOR_PROJECT` may fall back to `GOOGLE_CLOUD_PROJECT`.
- `BARRED_MODEL_ARMOR_LOCATION` may fall back to `GOOGLE_CLOUD_LOCATION`.
- `BARRED_MODEL_ARMOR_TEMPLATE_ID` has no fallback; missing template ID blocks live execution fail-closed.

### Google API Contract
Based on Google Cloud Model Armor documentation:

- Use regional endpoint: `modelarmor.<LOCATION>.rep.googleapis.com`.
- Use template resource: `projects/<PROJECT>/locations/<LOCATION>/templates/<TEMPLATE_ID>`.
- Use `sanitizeUserPrompt` / Python `sanitize_user_prompt`.
- Required runtime permission includes `modelarmor.templates.useToSanitizeUserPrompt`.
- Recommended predefined roles include `roles/modelarmor.user` and `roles/modelarmor.viewer`.

### Cloud Client Boundary
The application code must depend on a small internal client boundary, not leak Google SDK objects through the run lifecycle:

```python
class ModelArmorClient(Protocol):
    def sanitize_user_prompt_text(self, *, template_name: str, text: str) -> Any: ...
```

The cloud screen converts the provider response into BARRED's stable receipt:

```json
{
  "status": "configured",
  "mode": "cloud_model_armor",
  "decision_authority": "content_safety_only",
  "seed_screening": {
    "status": "passed|blocked|error",
    "checked": true,
    "blocked": false,
    "kind": "seed",
    "template_name": "projects/.../templates/...",
    "input_text_stored": false
  }
}
```

### Fail-Closed Rules
- Missing project/location/template blocks live execution before model calls.
- Missing Python SDK blocks live execution before model calls.
- Provider invocation failure blocks live execution before model calls.
- Provider `MATCH_FOUND` blocks live execution.
- Provider non-success invocation result blocks live execution.
- Receipts must not contain raw seed topic or predicate text.

## Integration Scope

### V1 Screening Points
Screen only two boundaries:

1. **Pre-run seed screening**
   - Input: selected seed `topic` and `predicate`.
   - Timing: after allowlisted seed selection, before live debate execution.
   - Output: `model_armor.seed_screening`.

2. **Pre-promotion artifact screening**
   - Input: generated attempts and verifier outputs.
   - Timing: after fresh debate execution, before GCS/Firestore promotion.
   - Output: `model_armor.artifact_screening`.

### Explicit Non-Goals
- Do not screen arbitrary user-supplied paths or URLs.
- Do not send raw seed text to Firestore.
- Do not replace B-gate.
- Do not add Model Armor to curated read-only reporting first.
- Do not block dry-runs; dry-runs should report `not_configured` or `not_applicable`.

## Proposed Report Shape

```json
{
  "model_armor": {
    "status": "configured",
    "decision_authority": "content_safety_only",
    "seed_screening": {
      "status": "passed",
      "checked": true,
      "blocked": false,
      "policy_name": "barred-fleet-seed-screening",
      "checked_at": "2026-08-20T00:00:00Z"
    },
    "artifact_screening": {
      "status": "passed",
      "checked": true,
      "blocked": false,
      "policy_name": "barred-fleet-artifact-screening",
      "checked_at": "2026-08-20T00:00:00Z"
    }
  },
  "b_gate": {
    "passed": true
  }
}
```

When not enabled:

```json
{
  "model_armor": {
    "status": "not_configured",
    "decision_authority": "none"
  }
}
```

When configured but blocking:

```json
{
  "status": "blocked",
  "error_category": "content_safety",
  "model_armor": {
    "status": "configured",
    "decision_authority": "content_safety_only",
    "seed_screening": {
      "status": "blocked",
      "checked": true,
      "blocked": true
    }
  },
  "b_gate": {
    "available": false,
    "passed": null
  }
}
```

## Tech Stack
- Fresh run planning/execution: `barred-fleet/app/fresh_debate.py`.
- Lifecycle/report evidence: `barred-fleet/app/run_lifecycle.py`.
- Artifact promotion boundary: `barred-fleet/app/fresh_artifacts.py`.
- Demo visibility: `barred-fleet/app/demo.py`.
- Tests: `barred-fleet/tests/unit/`.
- Google Cloud: Model Armor, Cloud Run, Firestore, GCS.

## Commands
- Local unit gate: `cd barred-fleet && uv run pytest tests/unit -q`
- Demo gate: `cd barred-fleet && make verify-demo`
- Dry-run product report smoke:

```bash
cd barred-fleet
SERVICE_URL="https://barred-fleet-837262597425.us-east1.run.app"
TOKEN="$(gcloud auth print-identity-token)"
RUN_ID="model-armor-dry-smoke-$(date +%Y%m%d%H%M%S)"
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  "$SERVICE_URL/runs" \
  -d "{\"seed_id\":\"fixture:first\",\"run_id\":\"$RUN_ID\",\"dry_run\":true,\"max_attempts\":1}" \
  | python3 -m json.tool
curl -sS \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json" \
  "$SERVICE_URL/runs/$RUN_ID/report" \
  | python3 -m json.tool
```

## Implementation Plan

### Task 1 — Local Client Interface
Add a small adapter interface:

```python
class TextSafetyScreen(Protocol):
    def screen_text(self, *, text: str, context: str) -> dict[str, Any]: ...
```

Default implementation returns `not_configured`.

Status: complete.

### Task 2 — Seed Screening Hook
Call the adapter before live debate execution.

Acceptance:
- dry-run remains unaffected;
- live run blocks before model calls if seed screening blocks;
- blocked status writes a diagnostic receipt;
- raw seed text is not stored in Firestore.

Status: complete for local adapter; cloud-mode client boundary is the next slice.

### Task 2B — Cloud Model Armor Screen Boundary
Add:

- `CloudModelArmorTextSafetyScreen`;
- `GoogleModelArmorClient`;
- env-selected factory mode `cloud_model_armor`;
- fake-client tests for pass/block/error/misconfiguration.

Acceptance:

- default remains `not_configured`;
- `cloud_model_armor` with missing template fails closed;
- fake provider `MATCH_FOUND` blocks;
- fake provider `NO_MATCH_FOUND` passes;
- fake provider exception blocks;
- raw seed text is absent from receipts.

### Task 3 — Artifact Screening Hook
Call the adapter before promotion.

Acceptance:
- generated artifact path metadata can be promoted only if screening passes;
- blocking creates a diagnostic receipt;
- deterministic B-gate receipt remains separate.

### Task 4 — Report/UI Evidence
Expose `model_armor` in:

- `/runs`;
- `/runs/{run_id}`;
- `/runs/{run_id}/report`;
- `/demo` live-result panel.

### Task 5 — Cloud Configuration
Only after local adapter tests pass:

- create/select Model Armor policy;
- grant minimal runtime permissions;
- deploy with opt-in env flag;
- run one bounded live case;
- verify report shows configured screening evidence.

## Testing Strategy
- Unit-test default `not_configured` behavior.
- Unit-test seed-blocked live run creates `status=blocked` and `error_category=content_safety`.
- Unit-test artifact-blocked promotion does not write promoted GCS/Firestore success.
- Unit-test raw topic/predicate text is absent from Firestore status and diagnostic receipts.
- Unit-test B-gate is unavailable when Model Armor blocks before debate.
- Unit-test B-gate remains authoritative when Model Armor passes.

## Boundaries
- Always: keep Model Armor as content safety, not vulnerability acceptance.
- Always: keep B-gate and deterministic eval receipts separate.
- Always: store hashes and metadata in Firestore, not raw seed/code bodies.
- Always: fail closed if configured Model Armor is unreachable during live execution.
- Ask first: add Google Cloud IAM roles, create policies, or enable Model Armor env flags.
- Ask first: send full generated artifacts to external screening.
- Never: claim `configured` unless a cloud policy is actually deployed and verified.
- Never: bypass local allowlist because Model Armor exists.

## Success Criteria
- Placeholder `not_configured` remains visible until real integration is enabled.
- Configured integration can block a live run before model calls.
- Configured integration can block artifact promotion after generation.
- B-gate remains the only acceptance decision.
- `make verify-demo` still passes after integration.

## Open Questions
- Which Model Armor policy name and location should be used for `gem-creation`?
- Should seed screening send full `topic`, only normalized snippets, or hash plus small excerpt?
- Should artifact screening sample large attempts or require full artifact screening before promotion?
- Should Model Armor failures be retryable or hard-blocking for demo runs?
