import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

RunArtifacts = dict[str, str | float]
TextReader = Callable[[str], str]
FirestoreReader = Callable[[str], dict[str, Any] | None]


def load_run_registry(registry_path: Path) -> dict[str, RunArtifacts]:
    if not registry_path.exists():
        return {}

    with registry_path.open("r", encoding="utf-8") as registry_file:
        payload = json.load(registry_file)

    return _coerce_registry_payload(str(registry_path), payload)


def load_run_registry_uri(
    registry_uri: str,
    *,
    reader: TextReader | None = None,
) -> dict[str, RunArtifacts]:
    if not registry_uri:
        return {}
    if not registry_uri.startswith("gs://"):
        raise ValueError("registry_uri must use gs://")

    text = reader(registry_uri) if reader is not None else _read_gcs_text(registry_uri)
    return _coerce_registry_payload(registry_uri, json.loads(text))


def load_firestore_run_artifacts(
    run_id: str,
    *,
    collection: str,
    project: str = "",
    database: str = "",
    reader: FirestoreReader | None = None,
) -> RunArtifacts:
    if not collection:
        return {}

    payload = (
        reader(run_id)
        if reader is not None
        else _read_firestore_document(
            run_id,
            collection=collection,
            project=project,
            database=database,
        )
    )
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"Firestore run {run_id} must contain an object")

    return _coerce_artifact_mapping(f"firestore:{collection}", run_id, payload)


def _coerce_registry_payload(source_name: str, payload: Any) -> dict[str, RunArtifacts]:
    if not isinstance(payload, dict):
        raise ValueError(f"{source_name} must contain a JSON object")

    runs = payload.get("runs", payload)
    if not isinstance(runs, dict):
        raise ValueError(f"{source_name} runs must contain a JSON object")

    registry: dict[str, RunArtifacts] = {}
    for run_id, artifacts in runs.items():
        if not isinstance(run_id, str):
            raise ValueError(f"{source_name} run IDs must be strings")
        if not isinstance(artifacts, dict):
            raise ValueError(f"{source_name} run {run_id} must contain an object")
        registry[run_id] = _coerce_artifact_mapping(source_name, run_id, artifacts)
    return registry


def resolve_run_artifacts(
    run_id: str,
    *,
    registry_path: Path,
    registry_uri: str = "",
    firestore_collection: str = "",
    firestore_project: str = "",
    firestore_database: str = "",
    gcs_reader: TextReader | None = None,
    firestore_reader: FirestoreReader | None = None,
) -> RunArtifacts:
    firestore_artifacts = load_firestore_run_artifacts(
        run_id,
        collection=firestore_collection,
        project=firestore_project,
        database=firestore_database,
        reader=firestore_reader,
    )
    if firestore_artifacts:
        return dict(firestore_artifacts)

    if registry_uri:
        gcs_artifacts = load_run_registry_uri(registry_uri, reader=gcs_reader).get(run_id, {})
        if gcs_artifacts:
            return dict(gcs_artifacts)

    return dict(load_run_registry(registry_path).get(run_id, {}))


def _coerce_artifact_mapping(
    source_name: str,
    run_id: str,
    artifacts: dict[str, Any],
) -> RunArtifacts:
    allowed_keys = {
        "input_path",
        "attempts_path",
        "checkpoint_path",
        "record_path",
        "cassette_path",
        "llm_eval_result_path",
        "deterministic_eval_result_path",
        "min_verifier_parse_ok_rate",
    }
    coerced: RunArtifacts = {}
    for key, value in artifacts.items():
        if key not in allowed_keys:
            continue
        if key == "min_verifier_parse_ok_rate":
            try:
                coerced[key] = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{source_name} run {run_id} field {key} must be numeric"
                ) from exc
            continue
        if not isinstance(value, str):
            raise ValueError(f"{source_name} run {run_id} field {key} must be a string")
        coerced[key] = value
    return coerced


def _read_gcs_text(registry_uri: str) -> str:
    import gcsfs

    filesystem = gcsfs.GCSFileSystem()
    with filesystem.open(registry_uri, "r") as registry_file:
        return registry_file.read()


def _read_firestore_document(
    run_id: str,
    *,
    collection: str,
    project: str = "",
    database: str = "",
) -> dict[str, Any] | None:
    try:
        from google.cloud import firestore
    except ImportError as exc:
        raise RuntimeError(
            "Firestore registry requires google-cloud-firestore to be installed"
        ) from exc

    client = firestore.Client(project=project or None, database=database or None)
    snapshot = client.collection(collection).document(run_id).get()
    if not snapshot.exists:
        return None
    return snapshot.to_dict()
