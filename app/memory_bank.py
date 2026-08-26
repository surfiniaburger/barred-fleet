from __future__ import annotations

import logging
import os
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.gepa_memory import (
    DEFAULT_PARETO_FRONTIER_PATH,
    ParetoSpecialist,
    get_pareto_directive_for_taxonomy,
    load_pareto_specialists,
)

logger = logging.getLogger(__name__)

MEMORY_BANK_FIRESTORE_PROJECT_ENV = "BARRED_MEMORY_BANK_FIRESTORE_PROJECT"
MEMORY_BANK_FIRESTORE_DATABASE_ENV = "BARRED_MEMORY_BANK_FIRESTORE_DATABASE"
MEMORY_BANK_FIRESTORE_COLLECTION_ENV = "BARRED_MEMORY_BANK_FIRESTORE_COLLECTION"
DEFAULT_FIRESTORE_PROJECT = "gem-creation"
DEFAULT_FIRESTORE_DATABASE = "barred-fleet"
DEFAULT_FIRESTORE_COLLECTION = "memory_bank_pareto"


class EnterpriseMemoryBank:
    """Enterprise Memory Bank client for querying and caching evolved Pareto invariants."""

    def __init__(
        self,
        project_id: str | None = None,
        database: str | None = None,
        collection: str | None = None,
        cache_ttl_seconds: int = 300,
        firestore_client: Any | None = None,
    ) -> None:
        """Initialize the Enterprise Memory Bank with optional cloud credentials and in-memory cache."""
        self.project_id = project_id or os.getenv(
            MEMORY_BANK_FIRESTORE_PROJECT_ENV, DEFAULT_FIRESTORE_PROJECT
        )
        self.database = database or os.getenv(
            MEMORY_BANK_FIRESTORE_DATABASE_ENV, DEFAULT_FIRESTORE_DATABASE
        )
        self.collection = collection or os.getenv(
            MEMORY_BANK_FIRESTORE_COLLECTION_ENV, DEFAULT_FIRESTORE_COLLECTION
        )
        self.cache_ttl_seconds = cache_ttl_seconds
        self._firestore_client = firestore_client
        self._cache: dict[str, dict[str, Any]] = {}

    def get_specialist(self, taxonomy: str) -> dict[str, Any]:
        """Retrieve a specialist Pareto invariant directive and metadata for a given taxonomy."""
        normalized_taxonomy = taxonomy.strip().lower()
        now = time.time()

        # Check per-taxonomy in-memory cache
        cached_entry = self._cache.get(normalized_taxonomy)
        if cached_entry and now < cached_entry.get("expires_at", 0.0):
            cached_result = dict(cached_entry["data"])
            cached_result["cached"] = True
            return cached_result

        # Try Firestore fetch if available
        firestore_result = self._fetch_from_firestore(normalized_taxonomy)
        if firestore_result:
            self._cache[normalized_taxonomy] = {
                "data": firestore_result,
                "expires_at": now + self.cache_ttl_seconds,
            }
            return firestore_result

        # Fallback to local Pareto artifact
        local_result = self._fetch_from_local_artifact(normalized_taxonomy)
        self._cache[normalized_taxonomy] = {
            "data": local_result,
            "expires_at": now + self.cache_ttl_seconds,
        }
        return local_result

    def _fetch_from_firestore(self, taxonomy: str) -> dict[str, Any] | None:
        """Attempt to fetch a Pareto invariant document from Firestore."""
        try:
            client = self._get_firestore_client()
            if client is None:
                return None
            doc_ref = client.collection(self.collection).document(taxonomy)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict() or {}
                prompt = str(data.get("prompt", "")).strip()
                if not prompt:
                    return None
                specialist = ParetoSpecialist(
                    taxonomy_bucket=taxonomy,
                    prompt=prompt,
                    score=float(data.get("score", 0.0)),
                    updated_at=str(data.get("updated_at", "")),
                    variant_id=str(data.get("variant_id", "")),
                )
                return {
                    "taxonomy_bucket": taxonomy,
                    "active_directive": specialist.format_micro_directive(),
                    "score": specialist.score,
                    "variant_id": specialist.variant_id,
                    "prompt_sha256": specialist.prompt_sha256,
                    "source": "firestore",
                    "cached": False,
                }
        except Exception as exc:
            logger.warning("Failed to fetch taxonomy document from Firestore: %s", type(exc).__name__)
            return None
        return None

    def _fetch_from_local_artifact(self, taxonomy: str) -> dict[str, Any]:
        """Fetch Pareto specialist from local artifact with deterministic fallback."""
        specialists = load_pareto_specialists(DEFAULT_PARETO_FRONTIER_PATH)
        if taxonomy in specialists:
            spec = specialists[taxonomy]
            return {
                "taxonomy_bucket": taxonomy,
                "active_directive": spec.format_micro_directive(),
                "score": spec.score,
                "variant_id": spec.variant_id,
                "prompt_sha256": spec.prompt_sha256,
                "source": "local_artifact",
                "cached": False,
            }

        return {
            "taxonomy_bucket": taxonomy,
            "active_directive": get_pareto_directive_for_taxonomy(taxonomy),
            "score": 0.0,
            "variant_id": "fallback_ast_rule",
            "prompt_sha256": "",
            "source": "deterministic_fallback",
            "cached": False,
        }

    def _get_firestore_client(self) -> Any | None:
        """Lazily initialize or return the injected Firestore client."""
        if self._firestore_client is False:
            return None
        if self._firestore_client is not None:
            return self._firestore_client
        try:
            from google.cloud import firestore

            self._firestore_client = firestore.Client(
                project=self.project_id,
                database=self.database,
            )
            return self._firestore_client
        except Exception as exc:
            logger.debug("Firestore client unavailable: %s", type(exc).__name__)
            return None
