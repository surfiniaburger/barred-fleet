import json
from pathlib import Path

from app.fresh_artifacts import build_fresh_run_report


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_fresh_report_summarizes_tmp_attempts_without_promoting_missing_corpus(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "fresh-run"
    attempts_path = run_dir / "attempts.jsonl"
    _write_jsonl(
        attempts_path,
        [{"decision": "rejected", "verifier": {"called": True}}],
    )

    report = build_fresh_run_report(
        run_id="fresh-run",
        artifact_paths={
            "run_dir": str(run_dir),
            "input_path": str(run_dir / "training_corpus.jsonl"),
            "attempts_path": str(attempts_path),
        },
    )

    assert report["status"] == "attention_required"
    assert report["promotion"] == {
        "enabled": False,
        "status": "not_promoted",
        "reason": "missing_input_artifact",
        "target_uri": "",
    }
    assert report["artifact_summary"]["artifacts"]["attempts"]["exists"] is True
    assert report["artifact_summary"]["artifacts"]["attempts"]["row_count"] == 1
    assert report["b_gate"]["status"] == "error"


def test_fresh_report_marks_passing_tmp_run_ready_when_promotion_disabled(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "fresh-run"
    corpus_path = run_dir / "training_corpus.jsonl"
    attempts_path = run_dir / "attempts.jsonl"
    record_path = run_dir / "record.json"
    _write_jsonl(
        corpus_path,
        [
            {
                "input": "char buf[8]; memcpy(buf, src, len);",
                "output": {
                    "predicate": "The code may overflow buf through memcpy length.",
                    "anchors": ["memcpy(buf, src, len)", "char buf[8]"],
                    "counterfactual": "Validate len against sizeof(buf) before memcpy.",
                    "verifier_report": {"passes_audit": True, "parse_ok": True},
                    "support_level": "supported",
                },
            }
        ],
    )
    _write_jsonl(
        attempts_path,
        [
            {
                "decision": "accepted",
                "verifier": {
                    "called": True,
                    "parse_ok": True,
                    "passes_audit": True,
                    "model": "vertex_ai/gemini-3.6-flash",
                },
            }
        ],
    )
    _write_json(
        record_path,
        {
            "run_id": "fresh-run",
            "models": {"judge": "vertex_ai/gemini-3.6-flash"},
            "usage_events": [],
        },
    )

    report = build_fresh_run_report(
        run_id="fresh-run",
        artifact_paths={
            "run_dir": str(run_dir),
            "input_path": str(corpus_path),
            "attempts_path": str(attempts_path),
            "record_path": str(record_path),
        },
    )

    assert report["status"] == "ok"
    assert report["b_gate"]["passed"] is True
    assert report["report_checks"]["deterministic_eval_present"] is True
    assert report["promotion"] == {
        "enabled": False,
        "status": "ready",
        "reason": "promotion_disabled",
        "target_uri": "",
    }
    eval_result = json.loads(
        (run_dir / "deterministic_eval_result.json").read_text(encoding="utf-8")
    )
    assert eval_result["summary_metrics"] == [
        {
            "metric_name": "fresh_b_gate_contract",
            "num_cases_total": 1,
            "num_cases_valid": 1,
            "num_cases_error": 0,
            "mean_score": 1.0,
            "fixture_run_id": "fresh-run",
            "accepted_rows": 1,
            "total_rows": 1,
            "verifier_parse_ok_rate": 1.0,
            "verifier_pass_rate": 1.0,
            "anchor_match_rate": 1.0,
        }
    ]
    assert report["model_routing"]["record_models"]["judge"] == (
        "vertex_ai/gemini-3.6-flash"
    )


def test_fresh_report_rejects_artifact_paths_outside_run_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "fresh-run"
    outside_path = tmp_path / "outside.jsonl"
    _write_jsonl(outside_path, [])

    report = build_fresh_run_report(
        run_id="fresh-run",
        artifact_paths={
            "run_dir": str(run_dir),
            "attempts_path": str(outside_path),
        },
    )

    assert report["status"] == "attention_required"
    assert report["promotion"]["reason"] == "invalid_artifact_path"
    assert "is not in the subpath" in report["error"]


def test_fresh_report_promotes_passing_run_with_injected_writers(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "fresh-run"
    corpus_path = run_dir / "training_corpus.jsonl"
    attempts_path = run_dir / "attempts.jsonl"
    checkpoint_path = run_dir / "checkpoint.json"
    _write_jsonl(
        corpus_path,
        [
            {
                "input": "char buf[8]; memcpy(buf, src, len);",
                "output": {
                    "predicate": "The code may overflow buf through memcpy length.",
                    "anchors": ["memcpy(buf, src, len)", "char buf[8]"],
                    "counterfactual": "Validate len against sizeof(buf) before memcpy.",
                    "verifier_report": {"passes_audit": True, "parse_ok": True},
                    "support_level": "supported",
                },
            }
        ],
    )
    _write_jsonl(
        attempts_path,
        [
            {
                "decision": "accepted",
                "verifier": {
                    "called": True,
                    "parse_ok": True,
                    "passes_audit": True,
                },
            }
        ],
    )
    _write_json(checkpoint_path, {"run_id": "fresh-run", "phase": "accepted"})
    uploads: list[tuple[Path, str]] = []
    firestore_writes: list[tuple[str, dict]] = []

    report = build_fresh_run_report(
        run_id="fresh-run",
        artifact_paths={
            "run_dir": str(run_dir),
            "input_path": str(corpus_path),
            "attempts_path": str(attempts_path),
            "checkpoint_path": str(checkpoint_path),
            "record_path": str(run_dir / "missing-record.json"),
        },
        seed_id="fixture:first",
        seed_metadata={"seed_id": "fixture:first", "language": "c"},
        model_routes={"judge": "vertex_ai/gemini-3.6-flash"},
        safety_policy={"status": "enforced"},
        safety_receipt={"status": "enforced"},
        model_armor={
            "status": "configured",
            "seed_screening": {"blocked": False},
        },
        agent_gateway={
            "status": "configured",
            "egress_decision": {"blocked": False},
        },
        max_attempts=1,
        env={
            "BARRED_PROMOTE_FRESH_RUNS": "true",
            "BARRED_FRESH_PROMOTION_BUCKET": "gs://barred-demo-artifacts",
            "BARRED_RUN_REGISTRY_FIRESTORE_COLLECTION": "barred_runs",
        },
        uploader=lambda source, target: uploads.append((source, target)),
        firestore_writer=lambda run_id, payload: firestore_writes.append(
            (run_id, payload)
        ),
    )

    assert report["promotion"]["status"] == "promoted"
    assert report["promotion"]["reason"] == "gcs_and_firestore_written"
    assert uploads == [
        (
            corpus_path,
            "gs://barred-demo-artifacts/runs/fresh-run/training_corpus.jsonl",
        ),
        (
            attempts_path,
            "gs://barred-demo-artifacts/runs/fresh-run/attempts.jsonl",
        ),
        (
            checkpoint_path,
            "gs://barred-demo-artifacts/runs/fresh-run/checkpoint.json",
        ),
        (
            run_dir / "deterministic_eval_result.json",
            "gs://barred-demo-artifacts/runs/fresh-run/"
            "deterministic_eval_result.json",
        ),
    ]
    assert firestore_writes == [
        (
            "fresh-run",
            {
                "input_path": (
                    "gs://barred-demo-artifacts/runs/fresh-run/training_corpus.jsonl"
                ),
                "attempts_path": (
                    "gs://barred-demo-artifacts/runs/fresh-run/attempts.jsonl"
                ),
                "checkpoint_path": (
                    "gs://barred-demo-artifacts/runs/fresh-run/checkpoint.json"
                ),
                "deterministic_eval_result_path": (
                    "gs://barred-demo-artifacts/runs/fresh-run/"
                    "deterministic_eval_result.json"
                ),
                "run_id": "fresh-run",
                "status": "completed",
                "seed_id": "fixture:first",
                "seed_metadata": {"seed_id": "fixture:first", "language": "c"},
                "model_routes": {"judge": "vertex_ai/gemini-3.6-flash"},
                "safety_policy": {"status": "enforced"},
                "safety_receipt": {"status": "enforced"},
                "model_armor": {
                    "status": "configured",
                    "seed_screening": {"blocked": False},
                },
                "agent_gateway": {
                    "status": "configured",
                    "egress_decision": {"blocked": False},
                },
                "max_attempts": 1,
                "b_gate_passed": True,
                "promotion_status": "promoted",
                "promotion_reason": "gcs_and_firestore_written",
                "artifact_paths": {
                    "input_path": (
                        "gs://barred-demo-artifacts/runs/fresh-run/"
                        "training_corpus.jsonl"
                    ),
                    "attempts_path": (
                        "gs://barred-demo-artifacts/runs/fresh-run/attempts.jsonl"
                    ),
                    "checkpoint_path": (
                        "gs://barred-demo-artifacts/runs/fresh-run/checkpoint.json"
                    ),
                    "deterministic_eval_result_path": (
                        "gs://barred-demo-artifacts/runs/fresh-run/"
                        "deterministic_eval_result.json"
                    ),
                },
                "min_verifier_parse_ok_rate": 1.0,
            },
        )
    ]


def test_fresh_report_does_not_promote_without_firestore_collection(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "fresh-run"
    corpus_path = run_dir / "training_corpus.jsonl"
    _write_jsonl(
        corpus_path,
        [
            {
                "input": "char buf[8]; memcpy(buf, src, len);",
                "output": {
                    "predicate": "The code may overflow buf through memcpy length.",
                    "anchors": ["memcpy(buf, src, len)", "char buf[8]"],
                    "counterfactual": "Validate len against sizeof(buf) before memcpy.",
                    "verifier_report": {"passes_audit": True, "parse_ok": True},
                    "support_level": "supported",
                },
            }
        ],
    )

    report = build_fresh_run_report(
        run_id="fresh-run",
        artifact_paths={
            "run_dir": str(run_dir),
            "input_path": str(corpus_path),
        },
        env={
            "BARRED_PROMOTE_FRESH_RUNS": "true",
            "BARRED_FRESH_PROMOTION_BUCKET": "gs://barred-demo-artifacts",
        },
        uploader=lambda _source, _target: None,
        firestore_writer=lambda _run_id, _payload: None,
    )

    assert report["promotion"]["status"] == "ready"
    assert report["promotion"]["reason"] == "firestore_collection_missing"


def test_fresh_report_returns_promotion_failure_without_raising(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "fresh-run"
    corpus_path = run_dir / "training_corpus.jsonl"
    _write_jsonl(
        corpus_path,
        [
            {
                "input": "char buf[8]; memcpy(buf, src, len);",
                "output": {
                    "predicate": "The code may overflow buf through memcpy length.",
                    "anchors": ["memcpy(buf, src, len)", "char buf[8]"],
                    "counterfactual": "Validate len against sizeof(buf) before memcpy.",
                    "verifier_report": {"passes_audit": True, "parse_ok": True},
                    "support_level": "supported",
                },
            }
        ],
    )

    def failing_uploader(_source: Path, _target: str) -> None:
        raise RuntimeError("bucket denied")

    report = build_fresh_run_report(
        run_id="fresh-run",
        artifact_paths={
            "run_dir": str(run_dir),
            "input_path": str(corpus_path),
        },
        env={
            "BARRED_PROMOTE_FRESH_RUNS": "true",
            "BARRED_FRESH_PROMOTION_BUCKET": "gs://barred-demo-artifacts",
            "BARRED_RUN_REGISTRY_FIRESTORE_COLLECTION": "barred_runs",
        },
        uploader=failing_uploader,
        firestore_writer=lambda _run_id, _payload: None,
    )

    assert report["b_gate"]["passed"] is True
    assert report["promotion"]["status"] == "not_promoted"
    assert report["promotion"]["reason"] == "promotion_failed"
    assert report["promotion"]["error"] == "bucket denied"
