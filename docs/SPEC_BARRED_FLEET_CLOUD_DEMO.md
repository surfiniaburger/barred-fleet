# Spec: BARRED-Fleet Cloud Demo

## Objective

Deploy BARRED-Fleet as a cloud-hosted, auditable multi-agent security decision system for the Fortified Enterprise Fleet / startup-style demo path.

The demo must show asymmetric debate over a security predicate, deterministic verifier/B-gate governance, and artifact-backed reporting without breaking the existing local BARRED flow.

Primary user: a security/platform team evaluating whether an AI-generated or AI-reviewed security decision is trustworthy enough to accept.

Success means a judge can see one live or recorded cloud run go from seed input to debate, verifier audit, B-gate badges, artifact links, and Cloud Logging/Trace evidence.

## Tech Stack

- Python `>=3.11,<3.14`
- ADK via `google-adk[gcp,otel-gcp]>=2.5.0,<3.0.0`
- `agents-cli` version `1.3.1`
- Cloud target: Cloud Run first
- Default model route: Gemini Flash for ADK orchestration and model-mediated debate roles
- Deterministic governance: existing BARRED verifier/B-gate modules
- Artifact storage target: local artifacts first, GCS after Cloud Run adapter is stable
- Metadata target: Firestore optional, only for run index/status after artifact flow works

## Commands

Inspect ADK project:

```bash
cd barred-fleet && agents-cli info
```

Run unit adapter tests:

```bash
cd barred-fleet && make test-unit
```

Generate deterministic ADK report trace:

```bash
cd barred-fleet && make eval-report-generate
```

Grade deterministic ADK report trace:

```bash
cd barred-fleet && make eval-report-grade-deterministic
```

Run local ADK smoke prompt:

```bash
cd barred-fleet && uv run agents-cli run "Summarize the latest BARRED run report from the available artifacts."
```

Start local ADK UI/playground:

```bash
cd barred-fleet && agents-cli playground
```

Add Cloud Run deployment support, only after spec/task approval:

```bash
cd barred-fleet && agents-cli scaffold enhance . --deployment-target cloud_run
```

Deploy, only after explicit approval and passing local eval:

```bash
cd barred-fleet && agents-cli deploy
```

## Project Structure

```text
barred-fleet/                         ADK scaffolded project
barred-fleet/app/agent.py             ADK root agent and model/tool wiring
barred-fleet/app/tools.py             Thin deterministic BARRED tool adapters
barred-fleet/app/fast_api_app.py      Cloud/HTTP app wrapper and telemetry config
barred-fleet/tests/unit/              Deterministic adapter tests
barred-fleet/tests/eval/              ADK eval datasets and custom metrics
barred-fleet/artifacts/               Local ADK traces and grade results
scenarios/debate/                     Existing BARRED debate/verifier/gate runtime
artifacts/                            Existing BARRED run outputs, attempts, metrics
docs/                                 Specs, RFCs, evaluation discipline, demo docs
tasks/                                Implementation plan and task checklist
```

Cloud Run demo runtime bundle:

```text
barred-fleet/barred_runtime/        Minimal packaged BARRED demo runtime
```

The demo bundle supports deterministic `report_barred_run` / B-gate reporting for `pilot-v1-calibrated-pecan`. It is not the full BARRED debate runtime and should not be described as enabling fresh cloud debate generation by itself.

Read-only demo surface:

```text
barred-fleet/app/demo.py             Curated demo report and HTML renderer
GET /demo                            Browser-readable product demo surface
GET /demo/report                     Deterministic JSON report for the demo fixture
```

## Code Style

Keep cloud code as an adapter over the existing harness:

```python
def build_cloud_run_report(run_id: str, attempts_path: str) -> dict[str, object]:
    b_gate = run_b_gate(attempts_path=attempts_path)
    report = report_barred_run(run_id=run_id, attempts_path=attempts_path)
    return {
        "run_id": run_id,
        "b_gate": b_gate,
        "report": report,
    }
```

Conventions:

- Deterministic tools compute facts; the LLM explains them.
- Preserve `run_id`, artifact paths, model routes, B-gate status, and trace/log identifiers.
- Avoid changing local BARRED scripts unless the cloud adapter requires a stable public boundary.
- Keep prefilter/graph optional and off by default for the deployment demo.
- Do not claim Model Garden/Gemma routing unless a concrete run artifact proves it.

## Testing Strategy

Unit tests verify deterministic adapter contracts:

- Artifact path safety and JSON/JSONL loading
- `run_debate_case` payload construction
- `run_b_gate` report shape
- `report_barred_run` observability summary
- Cloud-report object contains run ID, artifact paths, B-gate status, and model routing

ADK eval verifies agent behavior:

- Agent calls deterministic tools for factual claims
- Agent does not invent missing metrics
- Agent reports B-gate failures honestly
- Agent does not treat cassette replay as provider cache telemetry

Manual/cloud checks verify deployment:

- Cloud Run URL responds
- One curated seed audit can be triggered or summarized
- Logs/traces are visible in Google Cloud
- Endpoint uses bounded identity and does not expose unrestricted credentials

## Boundaries

- Always:
  - Preserve local CLI/BARRED behavior.
  - Run `make test-unit` before deployment changes are considered done.
  - Run deterministic ADK grade for the report case before deployment.
  - Keep B-gate deterministic and authoritative.
  - Use Gemini Flash as the default cost-controlled model route.

- Ask first:
  - Adding Cloud Run deployment files with `agents-cli scaffold enhance`.
  - Running `agents-cli deploy`.
  - Enabling prompt-response logging with full content capture.
  - Deploying Model Garden/Gemma endpoints.
  - Moving seeds or artifacts to Firestore/GCS beyond the first demo slice.

- Never:
  - Break existing `scenarios/debate` local commands.
  - Make graph/prefilter mandatory for the demo path.
  - Leave GPU-backed Model Garden endpoints running without a cleanup plan.
  - Commit secrets or unrestricted API keys.
  - Let the LLM override deterministic B-gate failures.

## Success Criteria

- `cd barred-fleet && agents-cli info` identifies `barred-fleet`, app directory `app`, and A2A enabled.
- `cd barred-fleet && make test-unit` passes.
- `cd barred-fleet && make eval-report-grade-deterministic` scores `1.0000` for the report contract.
- ADK default UI/playground can show a BARRED-Fleet response grounded in deterministic artifacts.
- Cloud Run deployment target is added without changing local BARRED commands.
- Deployed service returns or summarizes one run with B-gate status, artifact references, model route, and trace/log evidence.
- Dashboard work is read-only first: trigger run or select run, then show status, artifacts, and B-gate result.
- Demo UI proves low-handholding operation: a short run-id prompt maps to curated artifacts and B-gate facts without requiring the user to know internal artifact paths.

## Demo Narrative

Position BARRED-Fleet as an enterprise reliability layer for multi-agent security decisions, not as a generic vulnerability chatbot.

The judge-facing story should emphasize:

- **Autonomous evidence workflow**: one run ID is enough for the deployed agent to retrieve artifacts, compute B-gate status, and summarize model routing.
- **Asymmetric debate**: cheaper/faster debate generation is separated from stronger adjudication and verifier lanes.
- **Deterministic governance**: accepted outputs are gated by code, not by model self-report.
- **Cloud proof**: the service runs on Cloud Run with a dedicated runtime identity and bounded scaling.
- **Handholding reduction**: earlier prompts required explicit artifact paths; the current demo resolves the known run directly, which better matches the hackathon criterion for agents that complete work with little manual steering.

Demo video sequence:

1. Show Cloud Run service `barred-fleet` and deployed revision.
2. Open `/demo` or call `agents-cli run` with `Report the BARRED run pilot-v1-calibrated-pecan in concise JSON.`
3. Show B-gate pass, accepted/rejected rows, verifier parse/pass rates, model routing, deterministic eval score, and provenance note.
4. Explain that the LLM narrates the result but the acceptance gate is deterministic.
5. State the next production step: move artifact storage to GCS and run index metadata to Firestore without changing the local BARRED flow.

## Open Questions

- Should the first Cloud Run endpoint trigger a fresh debate run, summarize an existing run, or support both behind separate actions?
- Should GCS artifact upload be implemented before or after the first Cloud Run smoke deployment?
- Should the demo dashboard be a small custom frontend in `barred-fleet/frontend`, or a separate static app that calls the deployed service?
- What exact curated seed/run should be used for the recorded demo path?
