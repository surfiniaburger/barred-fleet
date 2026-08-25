import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.run_lifecycle as run_lifecycle
from app.fast_api_app import app
from app.fresh_debate import FreshDebateRequest
from app.run_lifecycle import (
    build_product_run_report,
    create_product_run,
    get_product_run,
    queue_product_run,
    run_queued_product_run,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_product_run_dry_run_writes_planned_status() -> None:
    writes: list[tuple[str, dict]] = []

    async def unused_runner(_request: FreshDebateRequest) -> dict:
        raise AssertionError("dry run must not call live runner")

    response = await create_product_run(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="product-dry-run",
            dry_run=True,
        ),
        runner=unused_runner,
        env={},
        status_writer=lambda run_id, payload: writes.append((run_id, payload)),
    )

    assert response["status"] == "planned"
    assert response["run_id"] == "product-dry-run"
    assert response["run_status_uri"] == "/runs/product-dry-run"
    assert response["seed_id"] == "fixture:first"
    assert response["safety_policy"]["status"] == "enforced"
    assert response["safety_policy"]["seed_allowlist"] == [
        "fixture:first",
        "cve500:N",
        "smoke:model-armor-block",
    ]
    assert response["safety_receipt"]["status"] == "enforced"
    assert response["safety_receipt"]["seed_selector_allowed"] is True
    assert response["safety_receipt"]["raw_seed_text_exposed"] is False
    assert response["safety_receipt"]["live_execution_flags_checked"] is False
    assert response["b_gate_passed"] is None
    assert response["promotion"]["status"] == "not_started"
    assert writes[0][0] == "product-dry-run"
    assert writes[0][1]["status"] == "planned"
    assert writes[0][1]["seed_metadata"]["seed_id"] == "fixture:first"
    assert writes[0][1]["safety_policy"]["raw_seed_text_exposed"] is False
    assert writes[0][1]["safety_receipt"]["arbitrary_paths_allowed"] is False
    assert writes[0][1]["max_attempts"] == 1
    assert "created_at" in writes[0][1]


@pytest.mark.asyncio
async def test_product_run_live_disabled_records_blocked_status(
    tmp_path: Path,
) -> None:
    writes: list[tuple[str, dict]] = []
    env = {"BARRED_FRESH_DEBATE_TMP_DIR": str(tmp_path)}

    async def disabled_runner(_request: FreshDebateRequest) -> dict:
        return {
            "status": "attention_required",
            "run_id": None,
            "error": "live fresh debate execution is disabled",
            "required_env": "BARRED_ENABLE_LIVE_FRESH_DEBATE=true",
        }

    response = await create_product_run(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="product-blocked-run",
            dry_run=False,
        ),
        runner=disabled_runner,
        env=env,
        status_writer=lambda run_id, payload: writes.append((run_id, payload)),
    )

    assert response["status"] == "blocked"
    assert response["run_id"] == "product-blocked-run"
    assert response["error"] == "live fresh debate execution is disabled"
    assert [payload["status"] for _run_id, payload in writes] == [
        "running",
        "blocked",
    ]
    assert writes[-1][1]["error"] == "live fresh debate execution is disabled"
    assert writes[-1][1]["diagnostic_receipt_path"].endswith(
        "diagnostic_receipt.json"
    )


@pytest.mark.asyncio
async def test_product_run_preserves_model_armor_blocked_seed_receipt(
    tmp_path: Path,
) -> None:
    writes: list[tuple[str, dict]] = []
    env = {"BARRED_FRESH_DEBATE_TMP_DIR": str(tmp_path)}
    model_armor = {
        "status": "configured",
        "control": "model_armor",
        "decision_authority": "content_safety_only",
        "seed_screening": {
            "status": "blocked",
            "checked": True,
            "blocked": True,
            "kind": "seed",
        },
        "artifact_screening": {
            "status": "not_started",
            "checked": False,
            "blocked": False,
            "kind": "artifact",
        },
        "input_text_stored": False,
    }

    async def blocked_runner(_request: FreshDebateRequest) -> dict:
        return {
            "status": "attention_required",
            "run_id": "product-model-armor-blocked",
            "error": "model armor seed screening blocked live execution",
            "error_category": "content_safety",
            "model_armor": model_armor,
        }

    response = await create_product_run(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="product-model-armor-blocked",
            dry_run=False,
        ),
        runner=blocked_runner,
        env=env,
        status_writer=lambda run_id, payload: writes.append((run_id, payload)),
    )

    assert response["status"] == "blocked"
    assert response["error_category"] == "content_safety"
    assert response["model_armor"]["status"] == "configured"
    assert response["model_armor"]["seed_screening"]["blocked"] is True
    assert response["model_armor"]["input_text_stored"] is False
    assert writes[-1][1]["model_armor"]["seed_screening"]["blocked"] is True

    report = build_product_run_report(
        "product-model-armor-blocked",
        status_reader=lambda _run_id: writes[-1][1],
    )

    assert report["model_armor"]["status"] == "configured"
    assert report["model_armor"]["seed_screening"]["blocked"] is True
    assert report["lifecycle"]["error_category"] == "content_safety"


@pytest.mark.asyncio
async def test_product_run_preserves_agent_gateway_blocked_receipt(
    tmp_path: Path,
) -> None:
    writes: list[tuple[str, dict]] = []
    env = {"BARRED_FRESH_DEBATE_TMP_DIR": str(tmp_path)}
    agent_gateway = {
        "status": "blocked",
        "control": "agent_gateway",
        "mode": "local_policy",
        "decision_authority": "routing_and_egress_only",
        "model_route_policy": {
            "checked": True,
            "blocked": True,
            "requested_routes": {"generator": "unapproved/provider"},
            "allowed_routes": ["vertex_ai/gemini-3.5-flash-lite"],
            "blocked_routes": [],
            "rejected_routes": ["unapproved/provider"],
        },
        "tool_egress_policy": {
            "checked": True,
            "blocked": False,
            "requested_tools": ["fresh_debate"],
            "allowed_tools": ["fresh_debate"],
            "blocked_tools": [],
            "rejected_tools": [],
        },
        "egress_decision": {
            "checked": True,
            "blocked": True,
            "context": "fresh_debate.live_execution",
            "reason": "model_route_blocked",
        },
    }

    async def blocked_runner(_request: FreshDebateRequest) -> dict:
        return {
            "status": "attention_required",
            "run_id": "product-agent-gateway-blocked",
            "error": "agent gateway blocked live execution",
            "error_category": "egress_policy",
            "agent_gateway": agent_gateway,
        }

    response = await create_product_run(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="product-agent-gateway-blocked",
            dry_run=False,
        ),
        runner=blocked_runner,
        env=env,
        status_writer=lambda run_id, payload: writes.append((run_id, payload)),
    )

    assert response["status"] == "blocked"
    assert response["error_category"] == "egress_policy"
    assert response["agent_gateway"]["status"] == "blocked"
    assert response["agent_gateway"]["egress_decision"]["blocked"] is True
    assert writes[-1][1]["agent_gateway"]["status"] == "blocked"

    report = build_product_run_report(
        "product-agent-gateway-blocked",
        status_reader=lambda _run_id: writes[-1][1],
    )

    assert report["agent_gateway"]["status"] == "blocked"
    assert report["agent_gateway"]["decision_authority"] == (
        "routing_and_egress_only"
    )
    assert report["agent_gateway"]["egress_decision"]["reason"] == (
        "model_route_blocked"
    )
    assert report["lifecycle"]["error_category"] == "egress_policy"


@pytest.mark.asyncio
async def test_product_run_success_records_completion_details() -> None:
    writes: list[tuple[str, dict]] = []

    async def successful_runner(_request: FreshDebateRequest) -> dict:
        return {
            "status": "completed",
            "run_id": "product-success-run",
            "artifact_paths": {
                "input_path": "/tmp/product-success-run/training_corpus.jsonl",
                "attempts_path": "/tmp/product-success-run/attempts.jsonl",
            },
            "fresh_report": {
                "b_gate": {"passed": True},
                "promotion": {
                    "status": "promoted",
                    "reason": "gcs_and_firestore_written",
                },
                "artifact_paths": {
                    "input_path": "gs://bucket/runs/product-success-run/training_corpus.jsonl",
                    "attempts_path": "gs://bucket/runs/product-success-run/attempts.jsonl",
                    "deterministic_eval_result_path": "gs://bucket/runs/product-success-run/deterministic_eval_result.json",
                },
            },
        }

    response = await create_product_run(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="product-success-run",
            dry_run=False,
        ),
        runner=successful_runner,
        env={},
        status_writer=lambda run_id, payload: writes.append((run_id, payload)),
    )

    assert response["status"] == "completed"
    assert response["started_at"]
    assert response["completed_at"]
    assert isinstance(response["duration_ms"], int)
    assert response["error_category"] == ""
    assert response["b_gate_passed"] is True
    assert response["promotion"]["status"] == "promoted"
    assert response["artifact_paths"]["input_path"].startswith("gs://bucket/")
    assert [payload["status"] for _run_id, payload in writes] == [
        "running",
        "completed",
    ]
    assert writes[-1][1]["b_gate_passed"] is True
    assert writes[-1][1]["promotion_status"] == "promoted"


@pytest.mark.asyncio
async def test_product_run_runner_exception_records_failed_status(
    tmp_path: Path,
) -> None:
    writes: list[tuple[str, dict]] = []

    async def failing_runner(_request: FreshDebateRequest) -> dict:
        raise RuntimeError("judge unavailable")

    response = await create_product_run(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="product-failed-run",
            dry_run=False,
        ),
        runner=failing_runner,
        env={"BARRED_FRESH_DEBATE_TMP_DIR": str(tmp_path)},
        status_writer=lambda run_id, payload: writes.append((run_id, payload)),
    )

    assert response["status"] == "failed"
    assert response["error"] == "judge unavailable"
    assert writes[-1][1]["status"] == "failed"
    assert writes[-1][1]["error"] == "judge unavailable"
    receipt_path = Path(writes[-1][1]["diagnostic_receipt_path"])
    assert receipt_path == tmp_path / "product-failed-run" / "diagnostic_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["run_id"] == "product-failed-run"
    assert receipt["status"] == "failed"
    assert receipt["seed_metadata"]["seed_id"] == "fixture:first"
    assert receipt["safety_receipt"]["status"] == "enforced"
    assert receipt["safety_receipt"]["raw_seed_text_exposed"] is False
    assert receipt["error"] == "judge unavailable"
    assert "seed_topic" not in receipt
    assert "seed_predicate" not in receipt


@pytest.mark.asyncio
async def test_product_run_promotes_blocked_diagnostic_receipt(tmp_path: Path) -> None:
    writes: list[tuple[str, dict]] = []
    uploads: list[tuple[Path, str]] = []

    async def disabled_runner(_request: FreshDebateRequest) -> dict:
        return {
            "status": "attention_required",
            "run_id": "product-blocked-promoted-run",
            "error": "live fresh debate execution is disabled",
            "required_env": "BARRED_ENABLE_LIVE_FRESH_DEBATE=true",
        }

    response = await create_product_run(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="product-blocked-promoted-run",
            dry_run=False,
        ),
        runner=disabled_runner,
        env={
            "BARRED_FRESH_DEBATE_TMP_DIR": str(tmp_path),
            "BARRED_PROMOTE_FRESH_RUNS": "true",
            "BARRED_FRESH_PROMOTION_BUCKET": "gs://barred-demo-artifacts",
        },
        status_writer=lambda run_id, payload: writes.append((run_id, payload)),
        diagnostic_uploader=lambda source, target: uploads.append((source, target)),
    )

    assert response["status"] == "blocked"
    assert response["diagnostic_receipt_path"] == (
        "gs://barred-demo-artifacts/runs/product-blocked-promoted-run/"
        "diagnostic_receipt.json"
    )
    assert writes[-1][1]["diagnostic_receipt_path"] == response[
        "diagnostic_receipt_path"
    ]
    assert uploads == [
        (
            tmp_path / "product-blocked-promoted-run" / "diagnostic_receipt.json",
            "gs://barred-demo-artifacts/runs/product-blocked-promoted-run/"
            "diagnostic_receipt.json",
        )
    ]


def test_get_product_run_returns_status_payload() -> None:
    response = get_product_run(
        "product-read-run",
        status_reader=lambda _run_id: {
            "run_id": "product-read-run",
            "status": "completed",
        },
    )

    assert response == {"run_id": "product-read-run", "status": "completed"}


def test_get_product_run_returns_not_found() -> None:
    response = get_product_run("missing-run", status_reader=lambda _run_id: None)

    assert response == {"status": "not_found", "run_id": "missing-run"}


def test_product_run_report_returns_not_found() -> None:
    response = build_product_run_report(
        "missing-report-run",
        status_reader=lambda _run_id: None,
    )

    assert response == {"status": "not_found", "run_id": "missing-report-run"}


def test_product_run_report_describes_blocked_diagnostic_receipt() -> None:
    response = build_product_run_report(
        "product-blocked-report",
        status_reader=lambda _run_id: {
            "run_id": "product-blocked-report",
            "status": "blocked",
            "seed_id": "fixture:first",
            "seed_metadata": {"seed_id": "fixture:first", "language": "c"},
            "model_routes": {"generator": "gemini-3.5-flash-lite"},
            "safety_policy": {"status": "enforced"},
            "safety_receipt": {"status": "enforced"},
            "max_attempts": 1,
            "b_gate_passed": None,
            "promotion_status": "not_promoted",
            "promotion_reason": "b_gate_not_passed",
            "artifact_paths": {
                "run_dir": "/tmp/product-blocked-report",
            },
            "diagnostic_receipt_path": (
                "gs://barred-demo-artifacts/runs/product-blocked-report/"
                "diagnostic_receipt.json"
            ),
            "diagnostic_receipt_error": "",
            "error": "live fresh debate execution is disabled",
        },
    )

    assert response["status"] == "ok"
    assert response["run_id"] == "product-blocked-report"
    assert response["seed_metadata"]["language"] == "c"
    assert response["model_routes"]["generator"] == "gemini-3.5-flash-lite"
    assert response["safety_policy"]["status"] == "enforced"
    assert response["safety_receipt"]["status"] == "enforced"
    assert response["b_gate"]["available"] is False
    assert response["b_gate"]["passed"] is None
    assert response["b_gate"]["selected_metrics"] == {}
    assert response["b_gate"]["invariant_scorecard"]["available"] is False
    assert response["diagnostic"]["available"] is True
    assert response["diagnostic"]["path"].startswith("gs://barred-demo-artifacts/")
    assert response["promotion"]["status"] == "not_promoted"
    assert response["error"] == "live fresh debate execution is disabled"
    assert response["provenance"]["chain"][-1] == {
        "step": "4. Deterministic gate",
        "system": "BARRED offline B-gate",
        "evidence": "not evaluated for this lifecycle state",
    }


def test_product_run_report_describes_completed_promoted_artifacts() -> None:
    response = build_product_run_report(
        "product-completed-report",
        status_reader=lambda _run_id: {
            "run_id": "product-completed-report",
            "status": "completed",
            "seed_id": "cve500:1",
            "seed_metadata": {"seed_id": "cve500:1", "index": 1},
            "model_routes": {
                "generator": "gemini-3.5-flash-lite",
                "judge": "gemini-3.6-flash",
            },
            "safety_policy": {"status": "enforced"},
            "safety_receipt": {"status": "enforced"},
            "max_attempts": 1,
            "b_gate_passed": True,
            "promotion_status": "promoted",
            "promotion_reason": "gcs_and_firestore_written",
            "artifact_paths": {
                "input_path": (
                    "gs://barred-demo-artifacts/runs/product-completed-report/"
                    "training_corpus.jsonl"
                ),
                "deterministic_eval_result_path": (
                    "gs://barred-demo-artifacts/runs/product-completed-report/"
                    "deterministic_eval_result.json"
                ),
            },
            "error": None,
        },
    )

    assert response["status"] == "ok"
    assert response["safety_policy"]["status"] == "enforced"
    assert response["safety_receipt"]["status"] == "enforced"
    assert response["model_armor"]["status"] == "not_configured"
    assert response["agent_gateway"]["status"] == "not_configured"
    assert response["b_gate"]["available"] is True
    assert response["b_gate"]["passed"] is True
    assert response["b_gate"]["selected_metrics"] == {}
    assert response["b_gate"]["invariant_scorecard"]["available"] is False
    assert response["deterministic_eval"]["available"] is True
    assert response["promotion"]["reason"] == "gcs_and_firestore_written"
    assert response["provenance"]["chain"][-1]["step"] == (
        "5. Deterministic eval receipt"
    )


def test_product_run_report_preserves_fresh_demo_promotion_metadata() -> None:
    response = build_product_run_report(
        "fresh-demo-promoted-report",
        status_reader=lambda _run_id: {
            "run_id": "fresh-demo-promoted-report",
            "status": "completed",
            "seed_id": "fixture:first",
            "seed_metadata": {"seed_id": "fixture:first", "language": "c"},
            "model_routes": {
                "generator": "vertex_ai/gemini-3.5-flash-lite",
                "judge": "vertex_ai/gemini-3.6-flash",
            },
            "safety_policy": {"status": "enforced"},
            "safety_receipt": {"status": "enforced"},
            "model_armor": {
                "status": "configured",
                "mode": "cloud_model_armor",
                "seed_screening": {"checked": True, "blocked": False},
            },
            "agent_gateway": {
                "status": "configured",
                "mode": "local_policy",
                "egress_decision": {"checked": True, "blocked": False},
            },
            "max_attempts": 1,
            "b_gate_passed": True,
            "promotion_status": "promoted",
            "promotion_reason": "gcs_and_firestore_written",
            "artifact_paths": {
                "input_path": (
                    "gs://barred-demo-artifacts/runs/fresh-demo-promoted-report/"
                    "training_corpus.jsonl"
                ),
                "attempts_path": (
                    "gs://barred-demo-artifacts/runs/fresh-demo-promoted-report/"
                    "attempts.jsonl"
                ),
                "deterministic_eval_result_path": (
                    "gs://barred-demo-artifacts/runs/fresh-demo-promoted-report/"
                    "deterministic_eval_result.json"
                ),
            },
            "error": None,
        },
    )

    assert response["seed_metadata"]["language"] == "c"
    assert response["model_routes"]["judge"] == "vertex_ai/gemini-3.6-flash"
    assert response["model_armor"]["status"] == "configured"
    assert response["model_armor"]["mode"] == "cloud_model_armor"
    assert response["agent_gateway"]["status"] == "configured"
    assert response["agent_gateway"]["mode"] == "local_policy"
    assert response["promotion"] == {
        "status": "promoted",
        "reason": "gcs_and_firestore_written",
    }
    assert response["max_attempts"] == 1


def test_product_run_report_enriches_local_artifacts(tmp_path: Path) -> None:
    corpus_path = tmp_path / "training_corpus.jsonl"
    attempts_path = tmp_path / "attempts.jsonl"
    eval_path = tmp_path / "deterministic_eval_result.json"
    _write_jsonl(
        corpus_path,
        [
            {
                "input": "char buf[8]; memcpy(buf, src, len);",
                "output": {
                    "predicate": "The code may overflow buf through memcpy length.",
                    "anchors": ["memcpy(buf, src, len)", "char buf[8]"],
                    "counterfactual": "Validate len against sizeof(buf) before memcpy.",
                    "verifier_report": {"parse_ok": True, "passes_audit": True},
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
                "model": "gemini-3.6-flash",
                "verifier": {"called": True, "parse_ok": True, "passes_audit": True},
            },
            {
                "decision": "rejected",
                "model": "gemini-3.5-flash-lite",
                "verifier": {"called": True, "parse_ok": True, "passes_audit": False},
            },
        ],
    )
    _write_json(
        eval_path,
        {
            "summary_metrics": [
                {
                    "metric_name": "fresh_b_gate_contract",
                    "num_cases_total": 1,
                    "num_cases_valid": 1,
                    "num_cases_error": 0,
                    "mean_score": 1.0,
                }
            ]
        },
    )

    response = build_product_run_report(
        "product-local-artifact-report",
        status_reader=lambda _run_id: {
            "run_id": "product-local-artifact-report",
            "status": "completed",
            "seed_id": "fixture:first",
            "seed_metadata": {"seed_id": "fixture:first"},
            "model_routes": {"judge": "gemini-3.6-flash"},
            "safety_policy": {"status": "enforced"},
            "safety_receipt": {"status": "enforced"},
            "max_attempts": 1,
            "b_gate_passed": True,
            "promotion_status": "not_promoted",
            "promotion_reason": "",
            "artifact_paths": {
                "input_path": str(corpus_path),
                "attempts_path": str(attempts_path),
                "deterministic_eval_result_path": str(eval_path),
            },
            "error": None,
        },
    )

    assert response["status"] == "ok"
    assert response["artifact_report"]["available"] is True
    assert response["artifact_summary"]["artifacts"]["attempts"]["row_count"] == 2
    assert response["artifact_summary"]["artifacts"]["attempts"]["decisions"] == {
        "accepted": 1,
        "rejected": 1,
    }
    assert response["b_gate"]["available"] is True
    assert response["b_gate"]["passed"] is True
    assert response["b_gate"]["selected_metrics"]["accepted_rows"] == 1
    assert response["b_gate"]["selected_metrics"]["verifier_parse_ok_rate"] == 1.0
    assert response["b_gate"]["selected_metrics"]["verifier_pass_rate"] == 0.5
    assert response["b_gate"]["invariant_scorecard"]["available"] is True
    assert any(
        row["key"] == "verifier_pass_rate"
        and row["value"] == 0.5
        and row["format"] == "percent"
        for row in response["b_gate"]["invariant_scorecard"]["rows"]
    )
    assert response["deterministic_eval"]["available"] is True
    assert response["deterministic_eval"]["score"] == 1.0
    assert response["safety_policy"]["status"] == "enforced"
    assert response["safety_receipt"]["status"] == "enforced"
    assert response["artifact_registry"]["corpus"]["path"] == str(corpus_path)
    assert response["artifact_registry"]["attempts"]["path"] == str(attempts_path)
    assert response["artifact_registry"]["deterministic_eval_result"]["path"] == str(
        eval_path
    )


def test_product_run_report_prefers_promoted_gcs_paths(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_observability_report(**kwargs) -> dict:
        captured.update(
            {
                "input_path": kwargs["input_path"],
                "attempts_path": kwargs["attempts_path"],
                "deterministic_eval_result_path": kwargs[
                    "deterministic_eval_result_path"
                ],
            }
        )
        return {
            "status": "ok",
            "artifact_summary": {
                "status": "ok",
                "artifact_count": 2,
                "artifacts": {
                    "attempts": {
                        "exists": True,
                        "row_count": 1,
                        "decisions": {"accepted": 1},
                        "verifier": {
                            "rows": 1,
                            "called": 1,
                            "parse_ok_rate": 1.0,
                            "pass_rate": 1.0,
                        },
                    }
                },
            },
            "b_gate": {
                "status": "ok",
                "passed": True,
                "failed_checks": [],
                "selected_metrics": {"accepted_rows": 1},
            },
            "eval_results": {
                "deterministic": {
                    "exists": True,
                    "summary_metrics": [{"mean_score": 1.0}],
                }
            },
            "report_checks": {"deterministic_eval_present": True},
        }

    monkeypatch.setattr(
        run_lifecycle,
        "build_observability_report",
        fake_observability_report,
    )

    response = build_product_run_report(
        "promoted-run",
        status_reader=lambda _run_id: {
            "run_id": "promoted-run",
            "status": "completed",
            "seed_id": "fixture:first",
            "safety_policy": {"status": "enforced"},
            "safety_receipt": {"status": "enforced"},
            "b_gate_passed": True,
            "promotion_status": "promoted",
            "promotion_reason": "gcs_and_firestore_written",
            "artifact_paths": {
                "input_path": "/tmp/promoted-run/training_corpus.jsonl",
                "attempts_path": "/tmp/promoted-run/attempts.jsonl",
                "deterministic_eval_result_path": (
                    "/tmp/promoted-run/deterministic_eval_result.json"
                ),
            },
            "input_path": "gs://bucket/runs/promoted-run/training_corpus.jsonl",
            "attempts_path": "gs://bucket/runs/promoted-run/attempts.jsonl",
            "deterministic_eval_result_path": (
                "gs://bucket/runs/promoted-run/deterministic_eval_result.json"
            ),
        },
    )

    assert captured == {
        "input_path": "gs://bucket/runs/promoted-run/training_corpus.jsonl",
        "attempts_path": "gs://bucket/runs/promoted-run/attempts.jsonl",
        "deterministic_eval_result_path": (
            "gs://bucket/runs/promoted-run/deterministic_eval_result.json"
        ),
    }
    assert response["artifacts"]["paths"] == captured
    assert response["safety_policy"]["status"] == "enforced"
    assert response["safety_receipt"]["status"] == "enforced"
    assert response["artifact_registry"]["corpus"] == {
        "path": "gs://bucket/runs/promoted-run/training_corpus.jsonl",
        "available": True,
        "storage": "gcs",
    }
    assert response["artifact_registry"]["attempts"]["path"] == (
        "gs://bucket/runs/promoted-run/attempts.jsonl"
    )
    assert response["artifact_registry"]["deterministic_eval_result"]["path"] == (
        "gs://bucket/runs/promoted-run/deterministic_eval_result.json"
    )
    assert response["artifact_registry"]["diagnostic_receipt"]["available"] is False
    assert response["artifact_report"]["available"] is True
    assert response["b_gate"]["selected_metrics"]["accepted_rows"] == 1
    assert response["b_gate"]["invariant_scorecard"]["available"] is True
    assert response["deterministic_eval"]["score"] == 1.0


def test_product_run_routes_create_and_read_dry_run(monkeypatch) -> None:
    monkeypatch.delenv("BARRED_RUN_REGISTRY_FIRESTORE_COLLECTION", raising=False)

    with TestClient(app) as client:
        create_response = client.post(
            "/runs",
            json={
                "seed_id": "fixture:first",
                "run_id": "product-route-dry-run",
                "dry_run": True,
            },
        )
        read_response = client.get("/runs/product-route-dry-run")

    assert create_response.status_code == 200
    assert read_response.status_code == 200
    assert create_response.json()["status"] == "planned"
    assert create_response.json()["safety_policy"]["status"] == "enforced"
    assert create_response.json()["safety_receipt"]["status"] == "enforced"
    assert read_response.json()["status"] == "planned"
    assert read_response.json()["safety_policy"]["status"] == "enforced"
    assert read_response.json()["safety_receipt"]["status"] == "enforced"
    assert read_response.json()["seed_metadata"]["seed_id"] == "fixture:first"


def test_product_run_report_route_reads_planned_status(monkeypatch) -> None:
    monkeypatch.delenv("BARRED_RUN_REGISTRY_FIRESTORE_COLLECTION", raising=False)

    with TestClient(app) as client:
        create_response = client.post(
            "/runs",
            json={
                "seed_id": "fixture:first",
                "run_id": "product-route-report-dry-run",
                "dry_run": True,
            },
        )
        report_response = client.get("/runs/product-route-report-dry-run/report")

    assert create_response.status_code == 200
    assert report_response.status_code == 200
    payload = report_response.json()
    assert payload["status"] == "ok"
    assert payload["run_id"] == "product-route-report-dry-run"
    assert payload["lifecycle"]["status"] == "planned"
    assert payload["safety_policy"]["status"] == "enforced"
    assert payload["safety_receipt"]["status"] == "enforced"
    assert payload["b_gate"]["available"] is False
    assert payload["b_gate"]["passed"] is None
    assert payload["b_gate"]["selected_metrics"] == {}
    assert payload["b_gate"]["invariant_scorecard"]["available"] is False
    assert payload["b_gate"]["invariant_scorecard"]["reason"] == "no_b_gate_metrics"
    assert payload["artifact_report"]["available"] is False
    assert payload["artifact_report"]["reason"] == (
        "planned_run_has_no_final_artifacts"
    )
    assert payload["artifact_report"]["b_gate"]["status"] == "not_evaluated"
    assert payload["artifact_report"]["artifact_summary"] == {
        "status": "not_started",
        "artifact_count": 0,
        "artifacts": {},
    }
    assert payload["artifact_registry"]["corpus"]["available"] is False
    assert payload["artifact_registry"]["corpus"]["storage"] == "not_started"
    assert payload["deterministic_eval"] == {
        "available": False,
        "path": payload["artifacts"]["paths"]["deterministic_eval_result_path"],
        "summary_metrics": [],
        "score": None,
    }
    assert payload["model_armor"]["status"] == "not_configured"
    assert payload["model_armor"]["seed_screening"]["checked"] is False
    assert payload["model_armor"]["artifact_screening"]["checked"] is False
    assert payload["agent_gateway"]["status"] == "not_configured"
    assert payload["seed_metadata"]["seed_id"] == "fixture:first"


def test_queue_product_run_writes_queued_without_calling_runner() -> None:
    writes: list[tuple[str, dict]] = []
    background_calls: list[tuple[FreshDebateRequest, dict]] = []

    response = queue_product_run(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="product-queued-run",
            dry_run=False,
            async_mode=True,
        ),
        schedule=lambda request, kwargs: background_calls.append((request, kwargs)),
        env={},
        status_writer=lambda run_id, payload: writes.append((run_id, payload)),
    )

    assert response["status"] == "queued"
    assert response["run_id"] == "product-queued-run"
    assert response["run_status_uri"] == "/runs/product-queued-run"
    assert response["created_at"]
    assert response["safety_policy"]["status"] == "enforced"
    assert response["safety_receipt"]["status"] == "enforced"
    assert response["queued_at"] == response["created_at"]
    assert response["started_at"] is None
    assert response["completed_at"] is None
    assert response["duration_ms"] is None
    assert response["error_category"] == ""
    assert writes[0][0] == "product-queued-run"
    assert writes[0][1]["status"] == "queued"
    assert writes[0][1]["queued_at"] == writes[0][1]["created_at"]
    assert writes[0][1]["seed_metadata"]["seed_id"] == "fixture:first"
    assert background_calls[0][0].run_id == "product-queued-run"


@pytest.mark.asyncio
async def test_run_queued_product_run_records_running_then_completed() -> None:
    writes: list[tuple[str, dict]] = []

    async def successful_runner(_request: FreshDebateRequest) -> dict:
        return {
            "status": "completed",
            "run_id": "product-async-success-run",
            "fresh_report": {
                "b_gate": {"passed": True},
                "promotion": {"status": "ready", "reason": "promotion_disabled"},
                "artifact_paths": {
                    "input_path": "/tmp/product-async-success-run/training_corpus.jsonl"
                },
            },
        }

    await run_queued_product_run(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="product-async-success-run",
            dry_run=False,
            async_mode=True,
        ),
        runner=successful_runner,
        env={},
        status_writer=lambda run_id, payload: writes.append((run_id, payload)),
    )

    assert [payload["status"] for _run_id, payload in writes] == [
        "running",
        "completed",
    ]
    assert "created_at" not in writes[0][1]
    assert writes[0][1]["started_at"]
    assert writes[-1][1]["started_at"] == writes[0][1]["started_at"]
    assert writes[-1][1]["completed_at"]
    assert isinstance(writes[-1][1]["duration_ms"], int)
    assert writes[-1][1]["b_gate_passed"] is True
    assert writes[-1][1]["promotion_status"] == "ready"


def test_product_run_route_async_live_records_final_status(monkeypatch) -> None:
    monkeypatch.delenv("BARRED_RUN_REGISTRY_FIRESTORE_COLLECTION", raising=False)
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")

    with TestClient(app) as client:
        create_response = client.post(
            "/runs",
            json={
                "seed_id": "fixture:first",
                "run_id": "product-route-async-live-disabled",
                "dry_run": False,
                "async_mode": True,
                "max_attempts": 1,
            },
        )
        read_response = client.get("/runs/product-route-async-live-disabled")
        report_response = client.get("/runs/product-route-async-live-disabled/report")

    assert create_response.status_code == 200
    assert read_response.status_code == 200
    assert create_response.json()["status"] == "queued"
    assert read_response.json()["status"] == "blocked"
    assert read_response.json()["completed_at"]
    assert read_response.json()["error_category"] == "configuration"
    assert read_response.json()["required_env"] == "BARRED_ENABLE_LIVE_FRESH_DEBATE=true"

    report_payload = report_response.json()
    assert report_payload["artifact_registry"]["diagnostic_receipt"]["available"] is True
    assert report_payload["artifact_registry"]["diagnostic_receipt"]["path"].endswith(
        "diagnostic_receipt.json"
    )
