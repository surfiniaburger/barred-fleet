# BARRED-Fleet Demo Fixture

## Selected Fixture

Use the `pecan` run as the primary product-demo fixture.

```text
run_id: pilot-v1-calibrated-pecan
corpus: training_corpus_calibrated_pecan.jsonl
attempts: artifacts/attempts/pilot-v1-calibrated-pecan.jsonl
b_gate_metrics: artifacts/metrics/b_gate-pilot-v1-calibrated-pecan.json
benchmark_metrics: artifacts/metrics/debate_benchmark-pilot-v1-calibrated-pecan.json
deterministic_eval_result: barred-fleet/tests/fixtures/pecan_demo/deterministic_eval_result.json
seed_source: scenarios/debate/cve_seeds_specific_anchor_10.jsonl
```

## Why This Fixture

- It is a real BARRED debate run, not only a synthetic ADK smoke fixture.
- It is budget-safe for demo because the expensive model calls have already been made.
- It passed B-gate.
- It produced 5 accepted rows from 17 attempts.
- It has stronger quality than the generic-anchor comparison run:
  - verifier pass rate: `0.75`
  - verifier parse-ok rate: `1.0`
  - predicate quality fail rate: `0.0`
  - B2 strict fail rate: `0.0`
  - tokens per accepted row: `57541.8`
- It does not require graph/prefilter to be enabled.
- With the deterministic eval fixture attached, `build_observability_report` returns `status: ok`.

## Cloud Run Bundle

The first Cloud Run smoke path packages this fixture under `barred-fleet/barred_runtime/` and sets `BARRED_ROOT=/code/barred_runtime` in the Dockerfile. This supports deterministic report/B-gate demo behavior without requiring fresh debate model calls in the deployed container.

## Secondary Fixture

Use the ADK smoke fixture for deterministic local/tool regression only.

```text
run_id: adk-smoke-cloud-fixture
corpus: barred-fleet/tests/fixtures/adk_smoke_cloud/adk_smoke_corpus.jsonl
attempts: barred-fleet/tests/fixtures/adk_smoke_cloud/adk_smoke_attempts.jsonl
dataset: barred-fleet/tests/eval/datasets/barred-report-dataset.json
```

This fixture is intentionally tiny and stable, but it is less persuasive as a product demo because it has only one accepted attempt and fixture-sized artifacts.

## Demo Interpretation

The demo should present `pecan` as an auditable asymmetric-debate run:

1. Input seed/predicate enters BARRED.
2. Purple Pro and Purple Con debate the security claim.
3. Green Judge adjudicates support.
4. Verifier audits anchors/mechanism.
5. B-gate enforces deterministic invariants.
6. BARRED-Fleet reports accepted/rejected status with artifact and trace links.

## Non-Goals For This Fixture

- Do not use this fixture to claim statistical significance.
- Do not claim graph/prefilter lift from this run.
- Do not claim Model Garden/Gemma routing unless a run artifact explicitly proves it.
- Do not rerun the full debate unless budget is intentionally allocated.
