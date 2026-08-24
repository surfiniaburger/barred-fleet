# BARRED Runtime Demo Bundle

This directory contains the minimal deterministic runtime artifacts required for the first Cloud Run demo report path.

It is intentionally not the full BARRED harness. It supports `report_barred_run` / B-gate reporting for the curated `pilot-v1-calibrated-pecan` fixture without requiring fresh debate model calls.

Included:

- `scenarios/debate/offline_b_gate.py`
- `training_corpus_calibrated_pecan.jsonl`
- `artifacts/attempts/pilot-v1-calibrated-pecan.jsonl`
- `barred-fleet/tests/fixtures/pecan_demo/deterministic_eval_result.json`

For local development, `BARRED_ROOT` continues to default to the parent `silver-one` checkout. In Cloud Run, the Dockerfile sets `BARRED_ROOT=/code/barred_runtime`.
