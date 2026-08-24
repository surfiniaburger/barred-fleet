# BARRED-Fleet ADK Migration Checklist

**Status:** Draft plan / no implementation started  
**Purpose:** Move cleanly from the current offline BARRED research harness toward an ADK-compatible, cloud-deployable security audit agent while quarantining the non-lifting allocation graph tranche.  
**Primary Track:** Fortified Enterprise Fleet  

## Working Decision

Keep the graph extractor as diagnostic evidence, but quarantine the non-lifting allocation tranche.

- Keep: graph core that currently demonstrates `TP=4`, `FP=0`, and semantic reachability evidence.
- Quarantine: exact-standard allocation-size tranche that preserved safety but did not lift 5-fold metrics.
- Pivot: package BARRED as an operational multi-agent security audit engine, not as an offline dataset script.

## Evidence Behind The Decision

Current graph state:

```text
ROC-AUC = 0.5571
PR-AUC = 0.3357
TP = 4
FP = 0
parser_coverage = 15.71%
```

Allocation tranche gate result:

```text
Tests passed.
FP stayed 0.
TP stayed 4.
No metric lift.
```

Interpretation:

- This is a useful negative result.
- It should not be promoted as product progress.
- It should not distract from the ADK/cloud/governance move.

## Phase 0: Quarantine Non-Lifting Allocation Tranche

Goal: leave the repository in a clean, reviewable state before starting ADK migration.

Checklist:

- [ ] Review current uncommitted graph changes.
- [ ] Separate metric-lifting graph changes from non-lifting allocation-tranche changes.
- [ ] Preserve the allocation-tranche spec as a negative-result artifact.
- [ ] Remove or revert allocation-tranche production code if it increases review burden.
- [ ] Remove or quarantine allocation-tranche tests if production code is reverted.
- [ ] Keep the 5-fold graph report showing `TP=4`, `FP=0`.
- [ ] Rerun focused graph tests after quarantine.
- [ ] Rerun 5-fold graph evaluation after quarantine.

Acceptance gate:

```text
Graph core remains green.
5-fold metrics remain at least ROC-AUC=0.5571, PR-AUC=0.3357, TP=4, FP=0.
No non-lifting production code remains in the main graph extractor unless explicitly retained as groundwork.
```

## Phase 1: Define ADK Agent Boundary

Goal: decide what BARRED-Fleet does as an agent.

Recommended agent contract:

```text
Input:
  - vulnerability predicate
  - candidate code snippet or patch
  - optional scenario metadata

Action:
  - run Pro/Con debate
  - run verifier audit
  - run B-gate invariants
  - summarize decision and evidence

Output:
  - accept/reject/security-risk decision
  - Pro/Con argument summary
  - verifier anchor status
  - B-gate invariant badges
  - trace/artifact links
```

Checklist:

- [x] Write `.agents-cli-spec.md`.
- [x] Define the agent name, likely `barred-fleet`.
- [x] Define deterministic tools with no model inside:
  - [x] `run_debate_case`
  - [x] `run_verifier_audit`
  - [x] `run_b_gate`
  - [x] `summarize_artifacts`
- [x] Decide prototype-first vs deployment-first.
- [x] Decide whether the first UI is ADK playground only or a lightweight dashboard.

Recommended decision:

```text
Prototype first.
ADK playground first.
Dashboard after the local agent can complete one end-to-end audit.
```

## Phase 2: Scaffold Prototype ADK Project

Goal: create a clean ADK shell without disturbing the existing BARRED harness.

Agents-CLI guidance:

```bash
agents-cli scaffold create barred-fleet \
  --agent adk \
  --prototype \
  --agent-guidance-filename AGENTS.md
```

Checklist:

- [x] Confirm `agents-cli` is installed.
- [x] Scaffold a new prototype project, not inside a pre-created directory.
- [x] Keep the existing BARRED repo as the source harness.
- [x] Add only thin adapter tools that call existing scripts/functions.
- [x] Do not hand-write A2A infrastructure; use scaffolded ADK/A2A surface.
- [x] Do not change existing model choices unless explicitly approved.

Acceptance gate:

```text
ADK prototype starts locally.
It can call one deterministic BARRED tool.
No production deployment work has started yet.
```

## Phase 3: Build Deterministic Tool Layer

Goal: wrap existing BARRED functionality behind stable agent tools.

Tool design:

```text
run_debate_case(input) -> debate_artifact
run_verifier_audit(debate_artifact) -> verifier_report
run_b_gate(verifier_report, anchors) -> invariant_result
summarize_artifacts(results) -> user-facing audit summary
```

Checklist:

- [ ] Tools return structured dictionaries.
- [ ] Tools write or reference deterministic artifacts.
- [ ] Tools do not embed additional LLM calls unless already part of existing BARRED flow.
- [ ] Tool outputs include provenance paths.
- [ ] The model only orchestrates and explains; deterministic tools compute gate decisions.

Acceptance gate:

```text
One local prompt can run an end-to-end audit and return a grounded decision.
The decision is traceable to deterministic tool outputs.
```

## Phase 4: Local Evaluation

Goal: prove the ADK wrapper does not hallucinate or skip the gate.

Checklist:

- [ ] Create 3-5 ADK eval cases:
  - [ ] valid accepted vulnerability candidate
  - [ ] rejected keyword-only false positive
  - [ ] prompt-injection attempt inside untrusted code/comment text
  - [ ] malformed snippet that must fail closed
  - [ ] missing-anchor case
- [ ] Run `agents-cli eval generate`.
- [ ] Run `agents-cli eval grade`.
- [ ] Compare results across iterations.
- [ ] Do not lower eval thresholds to pass.

Acceptance gate:

```text
Agent correctly calls tools.
Agent reports B-gate failures honestly.
Agent does not obey injected instructions inside code/news/untrusted text.
```

## Phase 5: Deploy As Running Service

Goal: satisfy cloud-hosted operational-agent expectations.

Recommended deployment target:

```text
Cloud Run first for hackathon demo control.
Agent Runtime later if managed sessions/OAuth/Gemini Enterprise publishing become central.
```

Checklist:

- [ ] Use `google-agents-cli-deploy` guidance before deploying.
- [ ] Add deployment scaffolding only after local eval passes.
- [ ] Decide CI/CD runner: GitHub Actions or Cloud Build.
- [ ] Deploy to Cloud Run.
- [ ] Verify deployed endpoint can run one audit.
- [ ] Capture demo-safe trace/artifact links.

Acceptance gate:

```text
Cloud URL works.
One audit flow succeeds from deployed service.
Logs/traces are visible.
```

## Phase 6: Govern The Agent

Goal: implement the governance checklist from the post in BARRED terms.

Post-derived governance checklist:

- [ ] **Starting reachability probe:** document what outbound hosts the deployed service can reach before restrictions.
- [ ] **Scoped identity:** deploy with a dedicated service account.
- [ ] **Least privilege:** grant only model invocation, logging, tracing, and required artifact access.
- [ ] **Prompt-injection screen:** add a raw-input screen before untrusted code/comment text reaches the model.
- [ ] **Deterministic gate before model summary:** B-gate decisions are computed before the model writes the final explanation.
- [ ] **Egress allow-list:** restrict outbound traffic to required model/API/artifact endpoints.
- [ ] **Observability:** enable Cloud Trace and decide whether prompt-response logging is acceptable for demo data.
- [ ] **Audit proof:** show identity, permissions, injection test, and egress behavior in the demo.

Acceptance gate:

```text
The deployed agent has bounded identity, bounded inputs, bounded network access, and observable traces.
```

## Phase 7: Optional GEPA Layer

Goal: add self-improvement only after the operational agent works.

Checklist:

- [ ] Capture failed audit traces as GEPA feedback tuples.
- [ ] Store mutation history under `artifacts/gepa/`.
- [ ] Keep prompt mutation separate from deterministic B-gate decisions.
- [ ] Compare token efficiency and accepted-row quality before/after GEPA.
- [ ] Do not claim GEPA lift without paired-seed evaluation.

Acceptance gate:

```text
GEPA improves prompt efficiency or quality without weakening B-gate invariants.
```

## Recommended Order Of Work

1. Quarantine allocation tranche.
2. Freeze graph core as diagnostic evidence.
3. Write `.agents-cli-spec.md`.
4. Scaffold `barred-fleet` prototype.
5. Wrap existing BARRED flow as deterministic tools.
6. Run local ADK playground.
7. Add ADK eval cases.
8. Deploy to Cloud Run.
9. Add governance controls.
10. Add GEPA only after the deployed demo loop is stable.

## Do Not Do Yet

- Do not chase another graph metric tranche.
- Do not deploy before a local ADK prototype works.
- Do not add GEPA before the basic operational audit flow exists.
- Do not claim cloud governance until identity, prompt-injection screening, and egress have been demonstrated.
- Do not hand-write A2A infrastructure; scaffold it.
