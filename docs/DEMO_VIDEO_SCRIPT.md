# BARRED-Fleet 4-Minute Demo Video Script

Target length: `3:35–3:55`. Devpost evaluates only the first four minutes.

## Verification Boundary

`make verify-demo` should stay deterministic. It should prove the deployed agent can resolve cloud artifacts, enforce private access, call the ADK tool path, and return the curated B-gate PASS report.

Do not make `make verify-demo` toggle Cloud Run live-debate flags, run paid model calls, then toggle them back. That creates cost risk, leaves infrastructure state brittle if the command is interrupted, and makes the core proof path non-repeatable.

Use a separate opt-in command or manual clip for live fresh debate:

1. Enable `BARRED_ENABLE_LIVE_FRESH_DEBATE=true`.
2. Enable `BARRED_START_INTERNAL_DEBATE_STACK=true`.
3. Keep `BARRED_MAX_LIVE_FRESH_ATTEMPTS=1`.
4. Run one selected `fixture:first` or `cve500:N` seed.
5. Return the service to the closed/default posture.

The main judged proof should be deterministic; the live run is bonus evidence if time and budget allow.

## Recording Checklist

- Browser tab with `/demo` screenshot or temporarily authenticated `/demo`.
- Google Cloud Console tab showing Cloud Run service `barred-fleet`.
- Cloud Run revision/service-account/security screenshot ready.
- Terminal in `barred-fleet/`.
- HTML evaluation report: `artifacts/grade_results/graph_gepa_graded/results_20260826_011010.html`.
- Optional: `docs/ADK_OPTIMIZE_VS_GRAPH_GEPA_COMPARISON_REPORT.md` open for reference.

## Script

### 0:00–0:20 — Hook

**Screen:** BARRED-Fleet `/demo` UI.

**Narration:**

> This is BARRED-Fleet. Enterprise AI is running into a security trilemma: capable agents are useful, fast agents are valuable, but both increase the need for inspection and control. In vulnerability workflows, the hard problem is not generating labels with AI. The hard problem is knowing which generated decisions are trustworthy enough to accept without burning hundreds of thousands of tokens.

### 0:20–0:50 — Problem And Product

**Screen:** `/demo` top cards: B-gate, accepted rows, verifier parse/pass.

**Narration:**

> A model can sound confident and still be unsupported. Recent multiagent research shows that agent coordination and epistemic failures do not disappear just because models get stronger. IBM's breach research also points to the same enterprise pressure: AI changes attacker speed and scale, so defenders need governed automation. BARRED-Fleet separates narration from governance: the model explains the report, but deterministic tools compute the B-gate, verifier rates, artifact provenance, and model routing.

### 0:50–1:20 — Cloud Proof

**Screen:** Google Cloud Console, Cloud Run service `barred-fleet`.

**Narration:**

> This is deployed on Google Cloud Run as `barred-fleet` in `us-east1`. The validated revision is `barred-fleet-00038-skl`. It runs with a dedicated runtime identity, `barred-fleet-runtime@gem-creation.iam.gserviceaccount.com`, rather than relying on a broad default identity. The service was temporarily public for browser proof capture and then returned to IAM-required private access.

### 1:20–1:55 — Agent Flow & Deterministic Report

**Screen:** Terminal running:

```bash
cd barred-fleet
make demo-smoke
```

**Narration:**

> The user does not need to know internal artifact paths. The prompt is just: “Report the BARRED run pilot-v1-calibrated-pecan in concise JSON.” The ADK agent calls `report_barred_run`, resolves the known run ID to curated artifacts, and returns the deterministic report. For this run, B-gate passes with five accepted rows from seventeen attempts, 100% verifier parse rate, and 0.0 logic error contamination.

### 1:55–2:40 — Empirical ADK Evaluation & 66.3% Token Reduction

**Screen:** HTML scorecard `artifacts/grade_results/graph_gepa_graded/results_20260826_011010.html` and terminal running:

```bash
agents-cli eval grade --traces artifacts/traces/graph_gepa_multi_round_traces.json --config tests/eval/eval_config_cve_ab.yaml
```

**Narration:**

> Beyond narration, we benchmarked prompt optimization within the Google Agents CLI sandbox. Generic LLM optimizers pass entire debate transcripts to reflection models, burning tens of thousands of tokens. Instead, our Graph-Powered GEPA extracts Tree-sitter AST data-flow paths locally with zero LLM tokens. On our 83-case evaluation suite graded directly through `agents-cli eval grade`, this dropped token consumption from 99,104 tokens down to 33,401 tokens per valid accept—a 66.3% token reduction with zero logic error contamination.

### 2:40–3:15 — Fresh Bounded Path & Safety Receipts

**Screen:** Fresh Debate Seed Preview panel with Model Armor and Agent Gateway badges.

**Narration:**

> The demo also includes a bounded fresh-debate path. I can choose `fixture:first` or an indexed `cve500` seed, preview the source file, index, language, safety label, and predicate hash, and screen inputs with Model Armor and Agent Gateway receipts before requesting a one-attempt live run. Server-side flags gate live execution, ensuring zero unbudgeted drift.

### 3:15–3:35 — Architecture

**Screen:** README architecture Mermaid or simple diagram.

**Narration:**

> Architecturally, this is a Google ADK and Cloud Run adapter over a disclosed existing BARRED research harness. The new hackathon work is the BARRED-Fleet cloud layer: ADK tool wiring, Cloud Run deployment, scoped identity, run-id artifact registry, bounded seed selector, deterministic report contract, and AST-guided GEPA optimization.

### 3:35–3:55 — Boundaries And Close

**Screen:** Devpost submission draft / GitHub repository summary.

**Narration:**

> The validated report is curated and stable, while fresh runs are bounded and subject to deterministic B-gate acceptance. By combining Google ADK, Cloud Run, and neurosymbolic AST-GEPA optimization, BARRED-Fleet proves that multiagent security audits can be fast, auditable, and 66.3% more token-efficient. Thank you!
