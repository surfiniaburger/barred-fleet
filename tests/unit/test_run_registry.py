import json
from pathlib import Path

import pytest

from app.run_registry import (
    load_firestore_run_artifacts,
    load_run_registry,
    load_run_registry_uri,
    resolve_run_artifacts,
)


def test_load_run_registry_returns_empty_for_missing_file(tmp_path: Path) -> None:
    registry = load_run_registry(tmp_path / "missing.json")

    assert registry == {}


def test_resolve_run_artifacts_loads_registered_run(tmp_path: Path) -> None:
    registry_path = tmp_path / "run_registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "runs": {
                    "run-a": {
                        "input_path": "corpus.jsonl",
                        "attempts_path": "attempts.jsonl",
                        "min_verifier_parse_ok_rate": 1,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    artifacts = resolve_run_artifacts("run-a", registry_path=registry_path)

    assert artifacts == {
        "input_path": "corpus.jsonl",
        "attempts_path": "attempts.jsonl",
        "min_verifier_parse_ok_rate": 1.0,
    }


def test_load_run_registry_uri_reads_gcs_registry_text() -> None:
    registry = load_run_registry_uri(
        "gs://barred-demo/run_registry.json",
        reader=lambda uri: json.dumps(
            {
                "runs": {
                    "run-a": {
                        "input_path": "gs://barred-demo/corpus.jsonl",
                        "attempts_path": "gs://barred-demo/attempts.jsonl",
                    }
                }
            }
        ),
    )

    assert registry["run-a"] == {
        "input_path": "gs://barred-demo/corpus.jsonl",
        "attempts_path": "gs://barred-demo/attempts.jsonl",
    }


def test_load_firestore_run_artifacts_reads_document() -> None:
    artifacts = load_firestore_run_artifacts(
        "run-a",
        collection="barred_runs",
        reader=lambda run_id: {
            "input_path": f"gs://barred-demo/{run_id}/corpus.jsonl",
            "attempts_path": f"gs://barred-demo/{run_id}/attempts.jsonl",
            "min_verifier_parse_ok_rate": 1,
        },
    )

    assert artifacts == {
        "input_path": "gs://barred-demo/run-a/corpus.jsonl",
        "attempts_path": "gs://barred-demo/run-a/attempts.jsonl",
        "min_verifier_parse_ok_rate": 1.0,
    }


def test_resolve_run_artifacts_prefers_firestore_over_gcs_and_local(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "run_registry.json"
    registry_path.write_text(
        json.dumps({"runs": {"run-a": {"input_path": "local.jsonl"}}}),
        encoding="utf-8",
    )

    artifacts = resolve_run_artifacts(
        "run-a",
        registry_path=registry_path,
        registry_uri="gs://barred-demo/run_registry.json",
        gcs_reader=lambda uri: json.dumps(
            {"runs": {"run-a": {"input_path": "gs://barred-demo/corpus.jsonl"}}}
        ),
        firestore_collection="barred_runs",
        firestore_reader=lambda run_id: {
            "input_path": "gs://firestore-artifacts/corpus.jsonl"
        },
    )

    assert artifacts == {"input_path": "gs://firestore-artifacts/corpus.jsonl"}


def test_load_run_registry_rejects_malformed_payload(tmp_path: Path) -> None:
    registry_path = tmp_path / "run_registry.json"
    registry_path.write_text(json.dumps(["not", "a", "mapping"]), encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON object"):
        load_run_registry(registry_path)


def test_load_run_registry_rejects_non_string_artifact_paths(tmp_path: Path) -> None:
    registry_path = tmp_path / "run_registry.json"
    registry_path.write_text(
        json.dumps({"runs": {"run-a": {"input_path": 42}}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="input_path must be a string"):
        load_run_registry(registry_path)


def test_load_run_registry_rejects_non_numeric_threshold(tmp_path: Path) -> None:
    registry_path = tmp_path / "run_registry.json"
    registry_path.write_text(
        json.dumps({"runs": {"run-a": {"min_verifier_parse_ok_rate": "high"}}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="min_verifier_parse_ok_rate must be numeric"):
        load_run_registry(registry_path)
