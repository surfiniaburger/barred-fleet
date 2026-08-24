from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.fast_api_app import app
from app.gepa_memory import (
    MEMORY_KIND_GEPA_EMPIRICAL_SUMMARY,
    GepaMemoryError,
    build_gepa_memory_preview,
    compile_gepa_memory_from_artifacts,
)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_fixture_artifacts(tmp_path: Path) -> dict[str, Path]:
    pareto_path = tmp_path / "pareto_frontier.json"
    mutations_path = tmp_path / "mutations.jsonl"
    traces_path = tmp_path / "traces.jsonl"
    acceptance_path = tmp_path / "step4_acceptance_report.json"

    _write_json(
        pareto_path,
        {
            "input_validation": {
                "prompt": "RAW PROMPT MUST NOT LEAK",
                "score": 9.7,
                "updated_at": "2026-08-23T23:21:56Z",
                "variant_id": "var_input",
            },
            "memory_safety": {
                "prompt": "ANOTHER RAW PROMPT MUST NOT LEAK",
                "score": 8.1,
                "updated_at": "2026-08-23T23:21:56Z",
                "variant_id": "var_memory",
            },
        },
    )
    _write_jsonl(
        mutations_path,
        [
            {
                "event": "prompt_mutation",
                "taxonomy_bucket": "input_validation",
                "variant_id": "var_input",
                "score": 1.0,
                "topological_rule": "[B_SANITIZER_MISMATCH] Apply NULL_CHECK.",
                "rationale": "fine to summarize counts, but not required",
            },
            {
                "event": "prompt_mutation",
                "taxonomy_bucket": "memory_safety",
                "variant_id": "var_memory",
                "score": -1.5,
                "topological_rule": "[B_SOURCE_MISSING] Find source.",
            },
        ],
    )
    _write_jsonl(
        traces_path,
        [
            {
                "outcome": "VALID_ACCEPT",
                "canonical_mutation_id": "var_input",
                "predicate_family": "RAW CODE BODY MUST NOT LEAK",
                "details": {
                    "run_id": "pilot-v7-poe",
                    "prompt": "TRACE PROMPT MUST NOT LEAK",
                    "status": "completed",
                },
            },
            {
                "outcome": "REJECTED",
                "canonical_mutation_id": "var_memory",
                "predicate_family": "SECOND RAW CODE BODY MUST NOT LEAK",
                "details": {
                    "run_id": "pilot-v7-poe",
                    "status": "completed",
                },
            },
        ],
    )
    _write_json(
        acceptance_path,
        {
            "status": "APPROVED_FOR_MERGE",
            "all_invariants_passed": True,
            "dataset_summary": {
                "total_attempts_scanned": 100,
                "accepted_attempts": 40,
            },
            "invariants": [
                {
                    "id": "INV-1",
                    "name": "Zero Logic Errors",
                    "measured": "0.0",
                    "passed": True,
                },
                {
                    "id": "INV-7",
                    "name": "Graph Pre-Filter AST Coverage",
                    "measured": "parse_coverage=0.7100",
                    "passed": True,
                },
            ],
        },
    )
    return {
        "pareto": pareto_path,
        "mutations": mutations_path,
        "traces": traces_path,
        "acceptance": acceptance_path,
    }


def test_compile_gepa_memory_from_artifacts_redacts_raw_text(tmp_path: Path) -> None:
    paths = _write_fixture_artifacts(tmp_path)

    memory = compile_gepa_memory_from_artifacts(
        pareto_frontier_path=paths["pareto"],
        mutations_path=paths["mutations"],
        traces_path=paths["traces"],
        acceptance_report_path=paths["acceptance"],
    )

    assert memory["memory_id"].startswith("sha256:")
    assert memory["memory_kind"] == MEMORY_KIND_GEPA_EMPIRICAL_SUMMARY
    assert memory["schema_version"] == 1
    assert memory["raw_prompt_text_stored"] is False
    assert memory["raw_seed_text_stored"] is False
    assert memory["raw_code_text_stored"] is False
    assert "RAW PROMPT MUST NOT LEAK" not in repr(memory)
    assert "RAW CODE BODY MUST NOT LEAK" not in repr(memory)
    assert "TRACE PROMPT MUST NOT LEAK" not in repr(memory)


def test_compile_gepa_memory_summarizes_pareto_and_audit(tmp_path: Path) -> None:
    paths = _write_fixture_artifacts(tmp_path)

    memory = compile_gepa_memory_from_artifacts(
        pareto_frontier_path=paths["pareto"],
        mutations_path=paths["mutations"],
        traces_path=paths["traces"],
        acceptance_report_path=paths["acceptance"],
    )

    assert memory["pareto_frontier"]["bucket_count"] == 2
    assert memory["pareto_frontier"]["best_bucket"] == "input_validation"
    assert memory["pareto_frontier"]["buckets"]["input_validation"] == {
        "variant_id": "var_input",
        "score": 9.7,
        "updated_at": "2026-08-23T23:21:56Z",
        "prompt_sha256": memory["pareto_frontier"]["buckets"]["input_validation"][
            "prompt_sha256"
        ],
        "raw_prompt_text_stored": False,
    }
    assert memory["acceptance_audit"] == {
        "status": "APPROVED_FOR_MERGE",
        "all_invariants_passed": True,
        "passed_invariants": 2,
        "total_invariants": 2,
        "dataset_summary": {
            "total_attempts_scanned": 100,
            "accepted_attempts": 40,
        },
        "invariants": [
            {
                "id": "INV-1",
                "name": "Zero Logic Errors",
                "measured": "0.0",
                "passed": True,
            },
            {
                "id": "INV-7",
                "name": "Graph Pre-Filter AST Coverage",
                "measured": "parse_coverage=0.7100",
                "passed": True,
            },
        ],
    }


def test_compile_gepa_memory_summarizes_mutations_and_traces(tmp_path: Path) -> None:
    paths = _write_fixture_artifacts(tmp_path)

    memory = compile_gepa_memory_from_artifacts(
        pareto_frontier_path=paths["pareto"],
        mutations_path=paths["mutations"],
        traces_path=paths["traces"],
        acceptance_report_path=paths["acceptance"],
    )

    assert memory["mutation_summary"] == {
        "total_mutations": 2,
        "by_taxonomy_bucket": {
            "input_validation": 1,
            "memory_safety": 1,
        },
        "by_topological_rule": {
            "[B_SANITIZER_MISMATCH] Apply NULL_CHECK.": 1,
            "[B_SOURCE_MISSING] Find source.": 1,
        },
        "positive_score_count": 1,
        "negative_score_count": 1,
    }
    assert memory["trace_summary"] == {
        "total_traces": 2,
        "by_outcome": {
            "VALID_ACCEPT": 1,
            "REJECTED": 1,
        },
        "by_variant": {
            "var_input": 1,
            "var_memory": 1,
        },
        "run_ids": ["pilot-v7-poe"],
    }


def test_gepa_memory_id_is_stable(tmp_path: Path) -> None:
    paths = _write_fixture_artifacts(tmp_path)

    first = compile_gepa_memory_from_artifacts(
        pareto_frontier_path=paths["pareto"],
        mutations_path=paths["mutations"],
        traces_path=paths["traces"],
        acceptance_report_path=paths["acceptance"],
    )
    second = compile_gepa_memory_from_artifacts(
        pareto_frontier_path=paths["pareto"],
        mutations_path=paths["mutations"],
        traces_path=paths["traces"],
        acceptance_report_path=paths["acceptance"],
    )

    assert first["memory_id"] == second["memory_id"]


def test_compile_gepa_memory_requires_pareto_frontier(tmp_path: Path) -> None:
    with pytest.raises(GepaMemoryError, match="pareto frontier"):
        compile_gepa_memory_from_artifacts(
            pareto_frontier_path=tmp_path / "missing.json",
        )


def test_gepa_memory_preview_endpoint_returns_redacted_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _write_fixture_artifacts(tmp_path)
    monkeypatch.setenv("BARRED_GEPA_PARETO_FRONTIER_PATH", str(paths["pareto"]))
    monkeypatch.setenv("BARRED_GEPA_MUTATIONS_PATH", str(paths["mutations"]))
    monkeypatch.setenv("BARRED_GEPA_TRACES_PATH", str(paths["traces"]))
    monkeypatch.setenv("BARRED_GEPA_ACCEPTANCE_REPORT_PATH", str(paths["acceptance"]))

    with TestClient(app) as client:
        response = client.get("/memory/gepa/preview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["source"] == "local"
    assert payload["write_enabled"] is False
    assert payload["memory"]["memory_kind"] == MEMORY_KIND_GEPA_EMPIRICAL_SUMMARY
    assert payload["memory"]["decision_authority"] == "deterministic_b_gate_only"
    assert payload["memory"]["pareto_frontier"]["best_bucket"] == "input_validation"
    assert payload["memory"]["acceptance_audit"]["all_invariants_passed"] is True
    assert "RAW PROMPT MUST NOT LEAK" not in response.text
    assert "RAW CODE BODY MUST NOT LEAK" not in response.text


def test_gepa_memory_preview_reads_redacted_gcs_summary() -> None:
    memory = {
        "memory_id": "sha256:abc123",
        "memory_kind": MEMORY_KIND_GEPA_EMPIRICAL_SUMMARY,
        "decision_authority": "deterministic_b_gate_only",
        "raw_prompt_text_stored": False,
        "raw_seed_text_stored": False,
        "raw_code_text_stored": False,
        "schema_version": 1,
    }

    preview = build_gepa_memory_preview(
        env={
            "BARRED_GEPA_MEMORY_SOURCE": "gcs",
            "BARRED_GEPA_MEMORY_GCS_URI": "gs://bucket/memory/gepa/latest.json",
        },
        gcs_reader=lambda uri: json.dumps({"memory": memory, "status": "ok"}),
    )

    assert preview == {
        "status": "ok",
        "source": "gcs",
        "memory": memory,
        "artifact_paths": {
            "gcs_uri": "gs://bucket/memory/gepa/latest.json",
        },
        "write_enabled": False,
    }


def test_gepa_memory_preview_gcs_source_requires_uri() -> None:
    preview = build_gepa_memory_preview(
        env={"BARRED_GEPA_MEMORY_SOURCE": "gcs"},
        gcs_reader=lambda _uri: "{}",
    )

    assert preview["status"] == "attention_required"
    assert preview["source"] == "gcs"
    assert preview["memory"] is None
    assert "BARRED_GEPA_MEMORY_GCS_URI is required" in preview["error"]


def test_gepa_memory_preview_endpoint_reports_missing_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        "BARRED_GEPA_PARETO_FRONTIER_PATH",
        str(tmp_path / "missing-pareto-frontier.json"),
    )
    monkeypatch.delenv("BARRED_GEPA_MUTATIONS_PATH", raising=False)
    monkeypatch.delenv("BARRED_GEPA_TRACES_PATH", raising=False)
    monkeypatch.delenv("BARRED_GEPA_ACCEPTANCE_REPORT_PATH", raising=False)

    with TestClient(app) as client:
        response = client.get("/memory/gepa/preview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "attention_required"
    assert "pareto frontier artifact does not exist" in payload["error"]
    assert payload["memory"] is None
