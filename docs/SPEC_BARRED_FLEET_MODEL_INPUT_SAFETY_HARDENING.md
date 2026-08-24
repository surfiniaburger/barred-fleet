# Spec: BARRED-Fleet Model/Input Safety Hardening

## Objective
Map BARRED-Fleet's current local safety policy to a production safety architecture without claiming unimplemented Google Cloud controls.

This slice is a design and verification spec. It does not add Model Armor, Agent Gateway, IAM changes, or new network controls yet. The goal is to define exactly where those controls should attach after the local contract is stable.

## Current Baseline
BARRED-Fleet already enforces a local deterministic safety posture:

- Seed IDs are allowlisted: `fixture:first` and `cve500:N`.
- Arbitrary seed paths are rejected.
- Raw seed text is not exposed by `/seeds/manifest`.
- Run IDs are regex-limited.
- Model route roles are limited to `generator`, `judge`, and `verifier`.
- Live execution requires explicit server-side flags.
- Live execution is bounded by `BARRED_MAX_LIVE_FRESH_ATTEMPTS`, defaulting to `1`.
- Deterministic B-gate decides acceptance; model narration does not.

The implemented local contract is documented in `docs/SPEC_BARRED_FLEET_LOCAL_SAFETY_POLICY.md`.

The concrete first Model Armor integration plan is documented in `docs/SPEC_BARRED_FLEET_MODEL_ARMOR_INTEGRATION_V1.md`.

## Threat Model

### Trust Boundaries
- Browser UI and CLI requests crossing into Cloud Run.
- Seed selectors crossing into packaged seed loading.
- Model route overrides crossing into debate orchestration.
- LLM-generated debate attempts crossing into artifact storage.
- Artifact paths crossing into report generation.
- Firestore and GCS reads crossing into demo/report responses.

### Assets
- Cloud Run runtime service account.
- Private GCS artifacts.
- Firestore `barred_runs` metadata.
- Packaged seed corpus.
- Deterministic B-gate integrity.
- Demo/report credibility.

### Abuse Cases
- User supplies an arbitrary local path as a seed selector.
- User supplies a URL-like seed selector to trigger SSRF-style fetching.
- User requests unbounded debate attempts to create cost exposure.
- User injects unsupported model route roles.
- Generated text tries to spoof B-gate results.
- Report endpoint leaks raw seed/code bodies instead of metadata and hashes.
- Firestore/GCS metadata is missing or stale and the UI presents it as accepted.

## Control Map

| Boundary | Current Local Control | Future Cloud Control | Verification Evidence |
|---|---|---|---|
| `/runs` request | Pydantic shape, seed allowlist, run ID regex, bounded attempts | Agent Gateway or API gateway policy | Unit tests plus authenticated route smoke |
| Seed selection | `fixture:first` / `cve500:N` only | GCS-backed signed seed manifest | `/seeds/manifest` policy and hash output |
| Raw seed/code exposure | metadata and SHA-256 only | Model Armor pre-ingest screening and redaction logging | No raw topic/predicate in manifest/report receipts |
| Live execution | disabled by default, explicit env gates | Gateway policy plus operator approval workflow | blocked diagnostic receipts and status transitions |
| Model routing | role allowlist, non-empty model values | managed route registry and egress policy | lifecycle/report `model_routes` field |
| LLM outputs | deterministic B-gate after generation | Model Armor output screening before artifact promotion | B-gate receipt plus screening receipt |
| Artifact reads | registry resolver with GCS/local fallback | least-privilege runtime read identity | `artifact_registry` storage labels |
| Artifact writes | promotion flag, GCS upload lifecycle | writer identity separated from read runtime | Firestore/GCS promotion status |

## Proposed Production Sequence

### Step 1 — Local Policy Enforcement Receipt
Add a compact `safety_receipt` to future fresh run reports.

Required fields:

```json
{
  "status": "enforced",
  "seed_id": "cve500:1",
  "seed_selector_allowed": true,
  "arbitrary_paths_allowed": false,
  "raw_seed_text_exposed": false,
  "max_attempts": 1,
  "live_execution_flags_checked": true
}
```

This is still local deterministic evidence, not Model Armor evidence.

### Step 2 — Model Armor Screening Boundary
Add screening at two points only:

1. Before live debate starts: screen selected seed topic/predicate.
2. Before artifact promotion: screen generated attempts and verifier outputs.

Do not let Model Armor replace B-gate. Content safety screening answers "is this content safe to process/store"; B-gate answers "is this vulnerability evidence accepted."

### Step 3 — Agent Gateway Boundary
Add gateway/egress controls after the run lifecycle is stable:

- Restrict reachable model/tool destinations.
- Require authenticated callers.
- Preserve Cloud Run private ingress.
- Emit logs linking request identity, run ID, route, and policy decision.

### Step 4 — Operator Evidence
Expose the safety evidence in report/UI:

- local policy status;
- screening status if configured;
- gateway status if configured;
- deterministic B-gate status;
- artifact promotion status.

## Tech Stack
- FastAPI route validation in `barred-fleet/app/fast_api_app.py`.
- Fresh debate request planning in `barred-fleet/app/fresh_debate.py`.
- Run lifecycle and report shaping in `barred-fleet/app/run_lifecycle.py`.
- Demo UI rendering in `barred-fleet/app/demo.py`.
- Google Cloud Run for private service hosting.
- Firestore for run metadata.
- GCS for private artifacts.
- Future: Model Armor and Agent Gateway, only after explicit implementation and cloud verification.

## Commands
- Baseline unit tests: `cd barred-fleet && uv run pytest tests/unit -q`
- Demo verification: `cd barred-fleet && make verify-demo`
- Seed manifest check:

```bash
cd barred-fleet
TOKEN="$(gcloud auth print-identity-token)"
curl -sS \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json" \
  "https://barred-fleet-837262597425.us-east1.run.app/seeds/manifest" \
  | python3 -m json.tool
```

## Project Structure
- `docs/SPEC_BARRED_FLEET_LOCAL_SAFETY_POLICY.md` is the current implemented policy.
- `docs/SPEC_BARRED_FLEET_MODEL_INPUT_SAFETY_HARDENING.md` is the forward map for cloud safety controls.
- `barred-fleet/app/fresh_debate.py` owns deterministic input constraints.
- `barred-fleet/app/run_lifecycle.py` owns durable safety/status evidence.
- `barred-fleet/app/demo.py` exposes policy evidence to operators.

## Code Style
Use additive evidence objects. Do not overload B-gate fields with content-safety or gateway results.

```python
{
    "safety_policy": {"status": "enforced"},
    "safety_receipt": {"status": "enforced", "seed_selector_allowed": True},
    "model_armor": {"status": "not_configured"},
    "agent_gateway": {"status": "not_configured"},
    "b_gate": {"passed": True},
}
```

## Testing Strategy
- Unit-test malformed selectors, unknown route roles, unsafe run IDs, and unbounded attempts.
- Unit-test that raw seed topic/predicate do not appear in manifest/report safety receipts.
- Unit-test that `model_armor.status` and `agent_gateway.status` remain `not_configured` until a real integration is added.
- Integration-test authenticated Cloud Run `/seeds/manifest`, `/runs`, and `/runs/{run_id}/report`.
- Manual cloud proof must include a private service check and an authenticated report check.

## Boundaries
- Always: keep deterministic B-gate separate from LLM and safety-screening decisions.
- Always: expose unimplemented controls as `not_configured`, never as active.
- Always: keep Cloud Run private unless explicitly capturing temporary demo proof.
- Always: keep Firestore metadata-only and GCS artifact-backed.
- Ask first: add Model Armor calls, Agent Gateway, new IAM bindings, new egress controls, or new dependencies.
- Ask first: allow live runs beyond `max_attempts=1`.
- Never: accept arbitrary seed file paths, arbitrary URLs, raw request-influenced artifact paths, or arbitrary model route roles.
- Never: write raw seed/code bodies to Firestore.
- Never: claim Model Armor or Agent Gateway protection before deployed proof exists.

## Success Criteria
- This spec is linked from the roadmap Phase 6 section.
- Future implementation can add `safety_receipt` without changing B-gate semantics.
- Future Model Armor/Gateway work has explicit attach points and non-goals.
- Existing `make verify-demo` remains the minimum regression gate before any cloud safety integration.

## Open Questions
- Which Google safety layer should govern raw seed/code text first: Model Armor at app level, Agent Gateway at ingress, or both?
- Should writer and reader service identities be separated before or during the first Model Armor integration?
- What minimum log fields are required for judging/operator proof without leaking raw seed text?
