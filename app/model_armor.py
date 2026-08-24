from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol

MODEL_ARMOR_MODE_ENV = "BARRED_MODEL_ARMOR_MODE"
MODEL_ARMOR_BLOCKLIST_ENV = "BARRED_MODEL_ARMOR_BLOCKLIST"
MODEL_ARMOR_PROJECT_ENV = "BARRED_MODEL_ARMOR_PROJECT"
MODEL_ARMOR_LOCATION_ENV = "BARRED_MODEL_ARMOR_LOCATION"
MODEL_ARMOR_TEMPLATE_ID_ENV = "BARRED_MODEL_ARMOR_TEMPLATE_ID"
MODEL_ARMOR_MODE_NOT_CONFIGURED = "not_configured"
MODEL_ARMOR_MODE_LOCAL_BLOCKLIST = "local_blocklist"
MODEL_ARMOR_MODE_CLOUD_MODEL_ARMOR = "cloud_model_armor"


class TextSafetyScreen(Protocol):
    def screen_text(self, *, text: str, context: str) -> dict[str, Any]: ...


class ModelArmorClient(Protocol):
    def sanitize_user_prompt_text(
        self,
        *,
        template_name: str,
        text: str,
    ) -> Any: ...


def build_not_configured_model_armor_status() -> dict[str, Any]:
    return {
        "status": "not_configured",
        "control": "model_armor",
        "decision_authority": "none",
        "seed_screening": _not_configured_screening("seed"),
        "artifact_screening": _not_configured_screening("artifact"),
        "notes": [
            "Model Armor is not active until deployed and verified.",
            "Deterministic B-gate remains the acceptance authority.",
        ],
    }


class NotConfiguredTextSafetyScreen:
    def screen_text(self, *, text: str, context: str) -> dict[str, Any]:
        return {
            **build_not_configured_model_armor_status(),
            "screening": {
                "status": "not_configured",
                "checked": False,
                "blocked": False,
                "context": context,
                "input_text_stored": False,
                "input_length": len(text),
            },
        }


class LocalBlocklistTextSafetyScreen:
    def __init__(self, *, blocked_terms: list[str]) -> None:
        self._blocked_terms = [
            blocked_term.casefold()
            for blocked_term in blocked_terms
            if blocked_term.strip()
        ]

    def screen_text(self, *, text: str, context: str) -> dict[str, Any]:
        normalized_text = text.casefold()
        blocked = any(term in normalized_text for term in self._blocked_terms)
        screening_status = "blocked" if blocked else "passed"
        return {
            "status": "configured",
            "control": "model_armor",
            "mode": MODEL_ARMOR_MODE_LOCAL_BLOCKLIST,
            "decision_authority": "content_safety_only",
            "seed_screening": {
                "status": screening_status,
                "checked": True,
                "blocked": blocked,
                "kind": "seed",
                "input_text_stored": False,
                "input_length": len(text),
                "matched_rule_count": int(blocked),
            },
            "artifact_screening": {
                "status": "not_started",
                "checked": False,
                "blocked": False,
                "kind": "artifact",
            },
            "notes": [
                "Local blocklist screening is an adapter test mode, not Cloud Model Armor.",
                "Deterministic B-gate remains the acceptance authority.",
            ],
        }


class CloudModelArmorTextSafetyScreen:
    def __init__(
        self,
        *,
        project_id: str,
        location_id: str,
        template_id: str,
        client: ModelArmorClient | None = None,
    ) -> None:
        self._project_id = project_id.strip()
        self._location_id = location_id.strip()
        self._template_id = template_id.strip()
        self._client = client

    def screen_text(self, *, text: str, context: str) -> dict[str, Any]:
        template_name = self._template_name()
        if not template_name:
            return _cloud_model_armor_error_receipt(
                reason="missing_model_armor_configuration",
                context=context,
                input_length=len(text),
                template_name="",
            )

        try:
            response = self._resolved_client().sanitize_user_prompt_text(
                template_name=template_name,
                text=text,
            )
        except Exception as exc:
            return _cloud_model_armor_error_receipt(
                reason="model_armor_invocation_failed",
                context=context,
                input_length=len(text),
                template_name=template_name,
                error_type=type(exc).__name__,
            )

        filter_match_state = _extract_response_value(
            response,
            "sanitization_result.filter_match_state",
        )
        invocation_result = _extract_response_value(
            response,
            "sanitization_result.invocation_result",
        )
        blocked = (
            filter_match_state != "NO_MATCH_FOUND"
            or invocation_result != "SUCCESS"
        )
        return {
            "status": "configured",
            "control": "model_armor",
            "mode": MODEL_ARMOR_MODE_CLOUD_MODEL_ARMOR,
            "decision_authority": "content_safety_only",
            "seed_screening": {
                "status": "blocked" if blocked else "passed",
                "checked": True,
                "blocked": blocked,
                "kind": "seed",
                "context": context,
                "template_name": template_name,
                "input_text_stored": False,
                "input_length": len(text),
                "checked_at": _utc_now(),
                "filter_match_state": filter_match_state or "UNKNOWN",
                "invocation_result": invocation_result or "UNKNOWN",
            },
            "artifact_screening": {
                "status": "not_started",
                "checked": False,
                "blocked": False,
                "kind": "artifact",
            },
            "notes": [
                "Cloud Model Armor screened seed text before live debate execution.",
                "Deterministic B-gate remains the acceptance authority.",
            ],
        }

    def _template_name(self) -> str:
        if not self._project_id or not self._location_id or not self._template_id:
            return ""
        return (
            f"projects/{self._project_id}/locations/{self._location_id}/"
            f"templates/{self._template_id}"
        )

    def _resolved_client(self) -> ModelArmorClient:
        return self._client or GoogleModelArmorClient(location_id=self._location_id)


class GoogleModelArmorClient:
    def __init__(self, *, location_id: str) -> None:
        self._location_id = location_id
        self._client: Any | None = None
        self._modelarmor_v1: Any | None = None

    def sanitize_user_prompt_text(
        self,
        *,
        template_name: str,
        text: str,
    ) -> Any:
        modelarmor_v1, client = self._load_client()
        request = modelarmor_v1.SanitizeUserPromptRequest(
            name=template_name,
            user_prompt_data=modelarmor_v1.DataItem(text=text),
        )
        return client.sanitize_user_prompt(request=request)

    def _load_client(self) -> tuple[Any, Any]:
        if self._client is not None and self._modelarmor_v1 is not None:
            return self._modelarmor_v1, self._client
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import modelarmor_v1
        except ImportError as exc:
            raise RuntimeError("google-cloud-modelarmor is not installed") from exc

        self._modelarmor_v1 = modelarmor_v1
        self._client = modelarmor_v1.ModelArmorClient(
            transport="rest",
            client_options=ClientOptions(
                api_endpoint=f"modelarmor.{self._location_id}.rep.googleapis.com"
            ),
        )
        return self._modelarmor_v1, self._client


class MisconfiguredTextSafetyScreen:
    def __init__(self, *, mode: str) -> None:
        self._mode = mode

    def screen_text(self, *, text: str, context: str) -> dict[str, Any]:
        return {
            "status": "misconfigured",
            "control": "model_armor",
            "mode": self._mode,
            "decision_authority": "content_safety_only",
            "seed_screening": {
                "status": "blocked",
                "checked": True,
                "blocked": True,
                "kind": "seed",
                "input_text_stored": False,
                "input_length": len(text),
                "reason": "unsupported_model_armor_mode",
            },
            "artifact_screening": {
                "status": "not_started",
                "checked": False,
                "blocked": False,
                "kind": "artifact",
            },
            "notes": [
                "Unsupported Model Armor mode blocks live execution fail-closed.",
                "Deterministic B-gate remains the acceptance authority.",
            ],
        }


def build_text_safety_screen(
    *,
    env: Mapping[str, str],
) -> TextSafetyScreen:
    mode = env.get(MODEL_ARMOR_MODE_ENV, MODEL_ARMOR_MODE_NOT_CONFIGURED).strip()
    if mode in {"", MODEL_ARMOR_MODE_NOT_CONFIGURED}:
        return NotConfiguredTextSafetyScreen()
    if mode == MODEL_ARMOR_MODE_LOCAL_BLOCKLIST:
        return LocalBlocklistTextSafetyScreen(
            blocked_terms=_parse_blocklist(env.get(MODEL_ARMOR_BLOCKLIST_ENV, "")),
        )
    if mode == MODEL_ARMOR_MODE_CLOUD_MODEL_ARMOR:
        return CloudModelArmorTextSafetyScreen(
            project_id=_env_first(env, MODEL_ARMOR_PROJECT_ENV, "GOOGLE_CLOUD_PROJECT"),
            location_id=_env_first(
                env,
                MODEL_ARMOR_LOCATION_ENV,
                "GOOGLE_CLOUD_LOCATION",
            ),
            template_id=env.get(MODEL_ARMOR_TEMPLATE_ID_ENV, ""),
        )
    return MisconfiguredTextSafetyScreen(mode=mode)


def _not_configured_screening(screening_kind: str) -> dict[str, Any]:
    return {
        "status": "not_configured",
        "checked": False,
        "blocked": False,
        "kind": screening_kind,
    }


def _cloud_model_armor_error_receipt(
    *,
    reason: str,
    context: str,
    input_length: int,
    template_name: str,
    error_type: str = "",
) -> dict[str, Any]:
    seed_screening = {
        "status": "error",
        "checked": True,
        "blocked": True,
        "kind": "seed",
        "context": context,
        "template_name": template_name,
        "input_text_stored": False,
        "input_length": input_length,
        "checked_at": _utc_now(),
        "reason": reason,
    }
    if error_type:
        seed_screening["error_type"] = error_type
    return {
        "status": "misconfigured" if reason.endswith("configuration") else "error",
        "control": "model_armor",
        "mode": MODEL_ARMOR_MODE_CLOUD_MODEL_ARMOR,
        "decision_authority": "content_safety_only",
        "seed_screening": seed_screening,
        "artifact_screening": {
            "status": "not_started",
            "checked": False,
            "blocked": False,
            "kind": "artifact",
        },
        "notes": [
            "Cloud Model Armor could not complete screening; live execution blocks fail-closed.",
            "Deterministic B-gate remains the acceptance authority.",
        ],
    }


def _extract_response_value(response: Any, dotted_path: str) -> str:
    current = response
    for part in dotted_path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
            continue
        current = getattr(current, part, None)
    if current is None:
        return ""
    value = getattr(current, "name", current)
    return str(value).split(".")[-1]


def _env_first(env: Mapping[str, str], *keys: str) -> str:
    for key in keys:
        value = env.get(key, "").strip()
        if value:
            return value
    return ""


def _parse_blocklist(blocklist_text: str) -> list[str]:
    return [
        blocked_term.strip()
        for blocked_term in blocklist_text.split(",")
        if blocked_term.strip()
    ]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
