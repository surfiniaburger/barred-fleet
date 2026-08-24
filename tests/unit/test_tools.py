import json
import sys
from pathlib import Path

import pytest

import app.tools as tools_module
from app.tools import (
    build_artifact_summary,
    build_b_gate_result,
    build_debate_case_payload,
    build_observability_report,
    execute_debate_case,
    report_barred_run,
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


def test_ensure_barred_import_path_includes_packaged_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    legacy_root = tmp_path / "legacy"
    original_sys_path = list(sys.path)
    monkeypatch.setattr(tools_module, "BARRED_DEBATE_RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(tools_module, "BARRED_ROOT", legacy_root)

    try:
        tools_module._ensure_barred_import_path()

        assert str(runtime_root / "src") in sys.path
        assert str(runtime_root) in sys.path
        assert str(legacy_root / "src") in sys.path
        assert str(legacy_root) in sys.path
        assert sys.path.index(str(runtime_root / "src")) < sys.path.index(
            str(legacy_root / "src")
        )
    finally:
        sys.path[:] = original_sys_path


def test_build_artifact_summary_counts_attempts_and_verifier(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "artifacts" / "attempts" / "run.jsonl",
        [
            {"decision": "accepted", "verifier": {"called": True, "passes_audit": True}},
            {"decision": "rejected", "pre_filter_stage": "graph"},
            {"decision": "rejected", "pre_filter_stage": "graph"},
        ],
    )
    _write_json(
        tmp_path / "artifacts" / "checkpoints" / "run" / "42.json",
        {
            "schema_version": 1,
            "run_id": "run",
            "seed": 42,
            "phase": "accepted",
            "refinement_round": 0,
            "updated_at": "2026-08-16T00:00:00Z",
        },
    )

    summary = build_artifact_summary(
        attempts_path="artifacts/attempts/run.jsonl",
        checkpoint_path="artifacts/checkpoints/run/42.json",
        base_dir=tmp_path,
    )

    assert summary["status"] == "ok"
    assert summary["artifact_count"] == 2
    assert summary["artifacts"]["attempts"]["row_count"] == 3
    assert summary["artifacts"]["attempts"]["decisions"] == {
        "accepted": 1,
        "rejected": 2,
    }
    assert summary["artifacts"]["attempts"]["pre_filter_stages"] == {"graph": 2}
    assert summary["artifacts"]["attempts"]["verifier"]["called"] == 1
    assert summary["artifacts"]["attempts"]["verifier"]["passes_audit"] == 1
    assert summary["artifacts"]["checkpoint"]["phase"] == "accepted"


def test_build_artifact_summary_reports_missing_files(tmp_path: Path) -> None:
    summary = build_artifact_summary(
        attempts_path="artifacts/attempts/missing.jsonl",
        base_dir=tmp_path,
    )

    assert summary["artifact_count"] == 1
    assert summary["artifacts"]["attempts"]["exists"] is False


def test_build_artifact_summary_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        build_artifact_summary(
            attempts_path="../outside.jsonl",
            base_dir=tmp_path,
        )


def test_build_b_gate_result_passes_grounded_supported_row(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "corpus.jsonl",
        [
            {
                "input": "char buf[8]; memcpy(buf, src, len);",
                "output": {
                    "predicate": "The code may overflow buf through memcpy length.",
                    "anchors": ["memcpy(buf, src, len)", "char buf[8]"],
                    "counterfactual": "Validate len against sizeof(buf) before memcpy.",
                    "verifier_report": {"passes_audit": True},
                    "support_level": "supported",
                },
            }
        ],
    )

    result = build_b_gate_result(input_path="corpus.jsonl", base_dir=tmp_path)

    assert result["status"] == "ok"
    assert result["passed"] is True
    assert result["failed_checks"] == []
    assert result["selected_metrics"]["accepted_rows"] == 1
    assert result["selected_metrics"]["b2_anchor_match_rate"] == 1.0


def test_build_b_gate_result_materializes_gcs_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus_path = tmp_path / "corpus.jsonl"
    _write_jsonl(
        corpus_path,
        [
            {
                "input": "char buf[8]; memcpy(buf, src, len);",
                "output": {
                    "predicate": "The code may overflow buf through memcpy length.",
                    "anchors": ["memcpy(buf, src, len)", "char buf[8]"],
                    "counterfactual": "Validate len against sizeof(buf) before memcpy.",
                    "verifier_report": {"passes_audit": True},
                    "support_level": "supported",
                },
            }
        ],
    )
    monkeypatch.setattr(
        tools_module,
        "_materialize_gcs_artifact",
        lambda uri: corpus_path,
    )

    result = build_b_gate_result(input_path="gs://barred-demo/corpus.jsonl")

    assert result["status"] == "ok"
    assert result["passed"] is True
    assert result["selected_metrics"]["accepted_rows"] == 1


def test_build_b_gate_result_fails_ungrounded_anchor(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "corpus.jsonl",
        [
            {
                "input": "return safe_value;",
                "output": {
                    "predicate": "The code may overflow buf through memcpy length.",
                    "anchors": ["memcpy(buf, src, len)", "char buf[8]"],
                    "counterfactual": "Validate len against sizeof(buf) before memcpy.",
                    "verifier_report": {"passes_audit": True},
                    "support_level": "supported",
                },
            }
        ],
    )

    result = build_b_gate_result(input_path="corpus.jsonl", base_dir=tmp_path)

    assert result["status"] == "ok"
    assert result["passed"] is False
    assert "row_failures" in result["failed_checks"]
    assert result["selected_metrics"]["b2_anchor_match_rate"] == 0.0


def test_build_b_gate_result_reports_missing_input(tmp_path: Path) -> None:
    result = build_b_gate_result(input_path="missing.jsonl", base_dir=tmp_path)

    assert result["status"] == "error"
    assert result["passed"] is False
    assert "input_path does not exist" in result["error"]


def test_checked_in_adk_smoke_fixture_summarizes_and_passes_b_gate() -> None:
    fixture_root = Path(__file__).resolve().parents[1] / "fixtures" / "adk_smoke_cloud"

    summary = build_artifact_summary(
        attempts_path="adk_smoke_attempts.jsonl",
        base_dir=fixture_root,
    )
    gate_result = build_b_gate_result(
        input_path="adk_smoke_corpus.jsonl",
        attempts_path="adk_smoke_attempts.jsonl",
        min_verifier_parse_ok_rate=1.0,
        base_dir=fixture_root,
    )

    assert summary["status"] == "ok"
    assert summary["artifacts"]["attempts"]["row_count"] == 1
    assert summary["artifacts"]["attempts"]["decisions"] == {"accepted": 1}
    assert summary["artifacts"]["attempts"]["verifier"] == {
        "rows": 1,
        "called": 1,
        "passes_audit": 1,
    }
    assert gate_result["status"] == "ok"
    assert gate_result["passed"] is True
    assert gate_result["failed_checks"] == []
    assert gate_result["selected_metrics"]["accepted_rows"] == 1
    assert gate_result["selected_metrics"]["verifier_parse_ok_rate"] == 1.0
    assert gate_result["selected_metrics"]["verifier_pass_rate"] == 1.0


def test_build_observability_report_links_artifacts_gate_models_and_eval(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "corpus.jsonl",
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
        tmp_path / "attempts.jsonl",
        [
            {
                "decision": "accepted",
                "verifier": {
                    "called": True,
                    "parse_ok": True,
                    "passes_audit": True,
                    "model": "ollama/gpt-oss:120b-cloud",
                },
                "llm_usage": {
                    "by_model": {
                        "ollama/gemma4:31b-cloud": {"calls": 2},
                        "ollama/gpt-oss:120b-cloud": {"calls": 1},
                    }
                },
            }
        ],
    )
    _write_json(
        tmp_path / "record.json",
        {
            "run_id": "run-a",
            "models": {
                "judge": "ollama/gpt-oss:120b-cloud",
                "debater": "ollama/gemma4:31b-cloud",
            },
            "usage_events": [],
        },
    )
    _write_json(
        tmp_path / "eval.json",
        {
            "summary_metrics": [
                {
                    "metric_name": "barred_artifact_gate_contract",
                    "num_cases_valid": 1,
                    "mean_score": 1.0,
                }
            ]
        },
    )

    report = build_observability_report(
        run_id="run-a",
        input_path="corpus.jsonl",
        attempts_path="attempts.jsonl",
        record_path="record.json",
        deterministic_eval_result_path="eval.json",
        min_verifier_parse_ok_rate=1.0,
        base_dir=tmp_path,
    )

    assert report["status"] == "ok"
    assert report["report_checks"] == {
        "artifacts_read": True,
        "b_gate_passed": True,
        "verifier_parse_ok_rate_met": True,
        "deterministic_eval_present": True,
    }
    assert report["b_gate"]["selected_metrics"]["accepted_rows"] == 1
    assert report["b_gate"]["selected_metrics"]["verifier_parse_ok_rate"] == 1.0
    assert report["model_routing"]["record_models"]["judge"] == "ollama/gpt-oss:120b-cloud"
    assert report["model_routing"]["attempt_models"]["by_model_calls"] == {
        "ollama/gemma4:31b-cloud": 2,
        "ollama/gpt-oss:120b-cloud": 1,
    }
    assert report["eval_results"]["deterministic"]["summary_metrics"][0]["mean_score"] == 1.0


def test_pecan_demo_fixture_builds_ok_observability_report() -> None:
    report = build_observability_report(
        run_id="pilot-v1-calibrated-pecan",
        input_path="training_corpus_calibrated_pecan.jsonl",
        attempts_path="artifacts/attempts/pilot-v1-calibrated-pecan.jsonl",
        deterministic_eval_result_path=(
            "barred-fleet/tests/fixtures/pecan_demo/deterministic_eval_result.json"
        ),
        min_verifier_parse_ok_rate=1.0,
    )

    assert report["status"] == "ok"
    assert report["report_checks"] == {
        "artifacts_read": True,
        "b_gate_passed": True,
        "verifier_parse_ok_rate_met": True,
        "deterministic_eval_present": True,
    }
    assert report["b_gate"]["passed"] is True
    assert report["b_gate"]["selected_metrics"]["accepted_rows"] == 5
    assert report["b_gate"]["selected_metrics"]["verifier_parse_ok_rate"] == 1.0
    assert report["b_gate"]["selected_metrics"]["verifier_pass_rate"] == 0.75
    assert report["eval_results"]["deterministic"]["summary_metrics"][0]["mean_score"] == 1.0
    assert report["model_routing"]["attempt_models"]["by_model_calls"] == {
        "ollama/gemma4:31b-cloud": 24,
        "ollama/gpt-oss:120b-cloud": 50,
    }
    assert report["artifact_registry"]["corpus"] == {
        "path": "training_corpus_calibrated_pecan.jsonl",
        "available": True,
        "storage": "local",
    }
    assert report["artifact_registry"]["attempts"]["path"] == (
        "artifacts/attempts/pilot-v1-calibrated-pecan.jsonl"
    )
    assert report["artifact_registry"]["deterministic_eval_result"]["available"] is True
    assert report["artifact_registry"]["diagnostic_receipt"] == {
        "path": "",
        "available": False,
        "storage": "missing",
    }


def test_report_barred_run_resolves_known_demo_fixture_by_run_id() -> None:
    report = report_barred_run(run_id="pilot-v1-calibrated-pecan")

    assert report["status"] == "ok"
    assert report["artifact_paths"]["input_path"] == "training_corpus_calibrated_pecan.jsonl"
    assert report["artifact_registry"]["corpus"]["path"] == (
        "training_corpus_calibrated_pecan.jsonl"
    )
    assert (
        report["artifact_paths"]["attempts_path"]
        == "artifacts/attempts/pilot-v1-calibrated-pecan.jsonl"
    )
    assert report["report_checks"] == {
        "artifacts_read": True,
        "b_gate_passed": True,
        "verifier_parse_ok_rate_met": True,
        "deterministic_eval_present": True,
    }
    assert report["b_gate"]["selected_metrics"]["accepted_rows"] == 5


def test_report_barred_run_resolves_registered_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = tmp_path / "run_registry.json"
    _write_json(
        registry_path,
        {
            "runs": {
                "alias-run": {
                    "input_path": "training_corpus_calibrated_pecan.jsonl",
                    "attempts_path": "artifacts/attempts/pilot-v1-calibrated-pecan.jsonl",
                    "deterministic_eval_result_path": (
                        "barred-fleet/tests/fixtures/pecan_demo/deterministic_eval_result.json"
                    ),
                    "min_verifier_parse_ok_rate": 1.0,
                }
            }
        },
    )
    monkeypatch.setattr(tools_module, "RUN_REGISTRY_PATH", registry_path)

    report = report_barred_run(run_id="alias-run")

    assert report["status"] == "ok"
    assert report["run_id"] == "alias-run"
    assert report["b_gate"]["selected_metrics"]["accepted_rows"] == 5


def test_report_barred_run_preserves_explicit_paths_for_known_runs() -> None:
    report = report_barred_run(
        run_id="pilot-v1-calibrated-pecan",
        input_path="missing-explicit-corpus.jsonl",
    )

    assert report["status"] == "attention_required"
    assert report["artifact_paths"]["input_path"] == "missing-explicit-corpus.jsonl"
    assert report["b_gate"]["status"] == "error"
    assert "missing-explicit-corpus.jsonl" in report["b_gate"]["error"]


def test_report_barred_run_returns_attention_required_for_unknown_run_without_input() -> None:
    report = report_barred_run(run_id="unknown-run")

    assert report["status"] == "attention_required"
    assert report["artifact_paths"]["input_path"] == ""
    assert report["artifact_registry"]["corpus"]["available"] is False
    assert report["b_gate"]["error"] == (
        "input_path is required unless run_id has a registered run or known demo fixture."
    )


def test_build_debate_case_payload_preserves_legacy_eval_request_shape() -> None:
    payload = build_debate_case_payload(
        code="int main(void) { return 0; }",
        predicate="The code is safe.",
        run_id="run-a",
        seed=7,
        mode="replay",
        clock_now="2026-08-16T00:00:00Z",
    )

    assert payload["participants"] == {
        "pro_debater": "http://127.0.0.1:9019/",
        "con_debater": "http://127.0.0.1:9018/",
    }
    assert payload["config"]["topic"] == "int main(void) { return 0; }"
    assert payload["config"]["predicate"] == "The code is safe."
    assert payload["config"]["run_id"] == "run-a"
    assert payload["config"]["seed"] == 7
    assert payload["config"]["mode"] == "replay"
    assert payload["config"]["checkpoint_path"] == "artifacts/checkpoints/run-a/7.json"
    assert payload["config"]["record_path"] == "artifacts/runs/run-a/7.json"
    assert payload["config"]["attempts_path"] == "artifacts/attempts/run-a.jsonl"
    assert payload["config"]["cassette_path"] == "artifacts/cassettes/run-a.json"
    assert payload["config"]["clock_now"] == "2026-08-16T00:00:00Z"


def test_build_debate_case_payload_rejects_invalid_mode() -> None:
    with pytest.raises(ValueError):
        build_debate_case_payload(
            code="int main(void) { return 0; }",
            predicate="The code is safe.",
            mode="offline",
        )


@pytest.mark.asyncio
async def test_execute_debate_case_uses_injected_sender() -> None:
    calls = []
    payload = build_debate_case_payload(
        code="int main(void) { return 0; }",
        predicate="The code is safe.",
        run_id="run-a",
        seed=7,
    )

    async def fake_sender(message: str, base_url: str) -> dict:
        calls.append((json.loads(message), base_url))
        return {
            "status": "completed",
            "context_id": "ctx-1",
            "response": "accepted with grounded anchors",
        }

    result = await execute_debate_case(
        payload=payload,
        judge_url="http://judge.local",
        sender=fake_sender,
    )

    assert calls == [(payload, "http://judge.local")]
    assert result["status"] == "completed"
    assert result["context_id"] == "ctx-1"
    assert result["response_excerpt"] == "accepted with grounded anchors"
    assert result["artifact_paths"] == {
        "attempts_path": "artifacts/attempts/run-a.jsonl",
        "checkpoint_path": "artifacts/checkpoints/run-a/7.json",
        "record_path": "artifacts/runs/run-a/7.json",
        "cassette_path": "artifacts/cassettes/run-a.json",
        "output_file": "training_corpus.jsonl",
    }
    assert result["payload_controls"]["mode"] == "record"
