from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.fast_api_app import app, get_memory_bank
from app.memory_bank import EnterpriseMemoryBank


def test_memory_bank_local_artifact_resolution() -> None:
    """Verify that EnterpriseMemoryBank resolves local Pareto specialist directives."""
    bank = EnterpriseMemoryBank(firestore_client=False)
    result = bank.get_specialist("memory_safety")

    assert result["taxonomy_bucket"] == "memory_safety"
    assert "Verify" in result["active_directive"] or "Focus on" in result["active_directive"] or "1." in result["active_directive"]
    assert result["score"] > 0.0
    assert result["source"] == "local_artifact"
    assert not result["cached"]

    # Test cache hit on second invocation
    cached_result = bank.get_specialist("memory_safety")
    assert cached_result["cached"] is True


def test_memory_bank_unknown_taxonomy_fallback() -> None:
    """Verify that EnterpriseMemoryBank defaults to AST reachability rule on unknown category."""
    bank = EnterpriseMemoryBank(firestore_client=False)
    result = bank.get_specialist("unknown_zero_day_taxonomy")

    assert result["taxonomy_bucket"] == "unknown_zero_day_taxonomy"
    assert "Enforce strict AST reachability invariants" in result["active_directive"]
    assert result["source"] == "deterministic_fallback"


def test_memory_bank_firestore_mock_resolution() -> None:
    """Verify that EnterpriseMemoryBank resolves from Firestore when document is present."""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "prompt": "You are a specialized cloud auditor.\n1. Inspect metadata API headers.",
        "score": 9.95,
        "variant_id": "var_firestore_cloud_995",
        "updated_at": "2026-08-27T00:00:00Z",
    }

    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc

    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc_ref

    mock_client = MagicMock()
    mock_client.collection.return_value = mock_collection

    bank = EnterpriseMemoryBank(firestore_client=mock_client)
    result = bank.get_specialist("cloud_metadata")

    assert result["taxonomy_bucket"] == "cloud_metadata"
    assert "1. Inspect metadata API headers." in result["active_directive"]
    assert result["score"] == 9.95
    assert result["variant_id"] == "var_firestore_cloud_995"
    assert result["source"] == "firestore"


def test_gepa_memory_query_endpoint() -> None:
    """Verify that GET /memory/gepa/query returns valid specialist payload with dependency injection."""
    mock_bank = EnterpriseMemoryBank(firestore_client=False)
    app.dependency_overrides[get_memory_bank] = lambda: mock_bank

    try:
        with TestClient(app) as client:
            response = client.get("/memory/gepa/query?taxonomy=input_validation")

        assert response.status_code == 200
        payload = response.json()
        assert payload["taxonomy_bucket"] == "input_validation"
        assert "active_directive" in payload
        assert payload["score"] > 0.0
    finally:
        app.dependency_overrides.pop(get_memory_bank, None)

