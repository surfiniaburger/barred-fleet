from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

AGENT_GATEWAY_MODE_ENV = "BARRED_AGENT_GATEWAY_MODE"
AGENT_GATEWAY_ALLOWED_MODEL_ROUTES_ENV = "BARRED_AGENT_GATEWAY_ALLOWED_MODEL_ROUTES"
AGENT_GATEWAY_BLOCKED_MODEL_ROUTES_ENV = "BARRED_AGENT_GATEWAY_BLOCKED_MODEL_ROUTES"
AGENT_GATEWAY_ALLOWED_TOOLS_ENV = "BARRED_AGENT_GATEWAY_ALLOWED_TOOLS"
AGENT_GATEWAY_BLOCKED_TOOLS_ENV = "BARRED_AGENT_GATEWAY_BLOCKED_TOOLS"
AGENT_GATEWAY_PROJECT_ENV = "BARRED_AGENT_GATEWAY_PROJECT"
AGENT_GATEWAY_LOCATION_ENV = "BARRED_AGENT_GATEWAY_LOCATION"
AGENT_GATEWAY_ID_ENV = "BARRED_AGENT_GATEWAY_ID"
AGENT_GATEWAY_POLICY_ID_ENV = "BARRED_AGENT_GATEWAY_POLICY_ID"
AGENT_GATEWAY_AUDIT_ONLY_ENV = "BARRED_AGENT_GATEWAY_AUDIT_ONLY"

AGENT_GATEWAY_MODE_NOT_CONFIGURED = "not_configured"
AGENT_GATEWAY_MODE_LOCAL_POLICY = "local_policy"
AGENT_GATEWAY_MODE_CLOUD_AGENT_GATEWAY = "cloud_agent_gateway"
NETWORK_SERVICES_ENDPOINT = "https://networkservices.googleapis.com/v1alpha1"

DEFAULT_ALLOWED_MODEL_ROUTES = (
    "vertex_ai/gemini-3.5-flash-lite",
    "vertex_ai/gemini-3.6-flash",
)
DEFAULT_ALLOWED_TOOLS = (
    "fresh_debate",
    "report_barred_run",
    "run_debate_case",
)


class AgentGateway(Protocol):
    def evaluate_egress(
        self,
        *,
        model_routes: Mapping[str, str],
        tool_names: Sequence[str],
        context: str,
    ) -> dict[str, Any]:
        """Evaluate model/tool egress before live execution."""


class CloudAgentGatewayClient(Protocol):
    def get_agent_gateway(self, *, gateway_resource: str) -> Mapping[str, Any]:
        """Return a Google Agent Gateway control-plane resource."""


class NotConfiguredAgentGateway:
    def evaluate_egress(
        self,
        *,
        model_routes: Mapping[str, str],
        tool_names: Sequence[str],
        context: str,
    ) -> dict[str, Any]:
        return build_not_configured_agent_gateway_status(context=context)


class LocalPolicyAgentGateway:
    def __init__(
        self,
        *,
        allowed_model_routes: Sequence[str] = DEFAULT_ALLOWED_MODEL_ROUTES,
        blocked_model_routes: Sequence[str] = (),
        allowed_tools: Sequence[str] = DEFAULT_ALLOWED_TOOLS,
        blocked_tools: Sequence[str] = (),
    ) -> None:
        self.allowed_model_routes = tuple(_non_empty_values(allowed_model_routes))
        self.blocked_model_routes = tuple(_non_empty_values(blocked_model_routes))
        self.allowed_tools = tuple(_non_empty_values(allowed_tools))
        self.blocked_tools = tuple(_non_empty_values(blocked_tools))

    def evaluate_egress(
        self,
        *,
        model_routes: Mapping[str, str],
        tool_names: Sequence[str],
        context: str,
    ) -> dict[str, Any]:
        rejected_routes = _rejected_values(
            model_routes.values(),
            allowed_values=self.allowed_model_routes,
            blocked_values=self.blocked_model_routes,
        )
        rejected_tools = _rejected_values(
            tool_names,
            allowed_values=self.allowed_tools,
            blocked_values=self.blocked_tools,
        )
        blocked = bool(rejected_routes or rejected_tools)
        reason = _decision_reason(
            rejected_routes=rejected_routes,
            rejected_tools=rejected_tools,
        )
        return {
            "status": "blocked" if blocked else "configured",
            "control": "agent_gateway",
            "mode": AGENT_GATEWAY_MODE_LOCAL_POLICY,
            "decision_authority": "routing_and_egress_only",
            "model_route_policy": {
                "checked": True,
                "blocked": bool(rejected_routes),
                "requested_routes": dict(model_routes),
                "allowed_routes": list(self.allowed_model_routes),
                "blocked_routes": list(self.blocked_model_routes),
                "rejected_routes": rejected_routes,
            },
            "tool_egress_policy": {
                "checked": True,
                "blocked": bool(rejected_tools),
                "requested_tools": list(tool_names),
                "allowed_tools": list(self.allowed_tools),
                "blocked_tools": list(self.blocked_tools),
                "rejected_tools": rejected_tools,
            },
            "egress_decision": {
                "checked": True,
                "blocked": blocked,
                "context": context,
                "reason": reason,
            },
            "notes": [
                "Agent Gateway policy controls model/tool egress only.",
                "Deterministic B-gate remains the acceptance authority.",
            ],
        }


class CloudAgentGateway:
    def __init__(
        self,
        *,
        project_id: str,
        location_id: str,
        gateway_id: str,
        policy_id: str = "",
        audit_only: bool = False,
        client: CloudAgentGatewayClient | None = None,
        allowed_model_routes: Sequence[str] = DEFAULT_ALLOWED_MODEL_ROUTES,
        blocked_model_routes: Sequence[str] = (),
        allowed_tools: Sequence[str] = DEFAULT_ALLOWED_TOOLS,
        blocked_tools: Sequence[str] = (),
    ) -> None:
        self.project_id = project_id.strip()
        self.location_id = location_id.strip()
        self.gateway_id = gateway_id.strip()
        self.policy_id = policy_id.strip()
        self.audit_only = audit_only
        self.client = client
        self.allowed_model_routes = tuple(_non_empty_values(allowed_model_routes))
        self.blocked_model_routes = tuple(_non_empty_values(blocked_model_routes))
        self.allowed_tools = tuple(_non_empty_values(allowed_tools))
        self.blocked_tools = tuple(_non_empty_values(blocked_tools))

    def evaluate_egress(
        self,
        *,
        model_routes: Mapping[str, str],
        tool_names: Sequence[str],
        context: str,
    ) -> dict[str, Any]:
        gateway_resource = self._gateway_resource()
        if not gateway_resource:
            return _cloud_agent_gateway_error_receipt(
                reason="missing_agent_gateway_configuration",
                context=context,
                model_routes=model_routes,
                tool_names=tool_names,
                gateway_resource="",
                policy_name=self.policy_id,
            )

        try:
            gateway_config = self._resolved_client().get_agent_gateway(
                gateway_resource=gateway_resource
            )
        except Exception as exc:
            return _cloud_agent_gateway_error_receipt(
                reason="cloud_agent_gateway_unavailable",
                context=context,
                model_routes=model_routes,
                tool_names=tool_names,
                gateway_resource=gateway_resource,
                policy_name=self.policy_id,
                error_type=type(exc).__name__,
            )

        validation_error = _validate_cloud_gateway_config(
            gateway_config,
            gateway_resource=gateway_resource,
        )
        if validation_error:
            return _cloud_agent_gateway_error_receipt(
                reason=validation_error,
                context=context,
                model_routes=model_routes,
                tool_names=tool_names,
                gateway_resource=gateway_resource,
                policy_name=self.policy_id,
            )

        rejected_routes = _rejected_values(
            model_routes.values(),
            allowed_values=self.allowed_model_routes,
            blocked_values=self.blocked_model_routes,
        )
        rejected_tools = _rejected_values(
            tool_names,
            allowed_values=self.allowed_tools,
            blocked_values=self.blocked_tools,
        )
        blocked = bool(rejected_routes or rejected_tools)
        reason = _decision_reason(
            rejected_routes=rejected_routes,
            rejected_tools=rejected_tools,
        )
        return {
            "status": "blocked" if blocked else "configured",
            "control": "agent_gateway",
            "mode": AGENT_GATEWAY_MODE_CLOUD_AGENT_GATEWAY,
            "decision_authority": "routing_and_egress_only",
            "cloud_control_plane": {
                "checked": True,
                "blocked": False,
                "gateway_resource": gateway_resource,
                "policy_name": self.policy_id,
                "audit_only": self.audit_only,
                "provider": "google_network_services_agent_gateway",
                "governed_access_path": _extract_response_value(
                    gateway_config,
                    "googleManaged.governedAccessPath",
                )
                or "UNKNOWN",
            },
            "model_route_policy": {
                "checked": True,
                "blocked": bool(rejected_routes),
                "requested_routes": dict(model_routes),
                "allowed_routes": list(self.allowed_model_routes),
                "blocked_routes": list(self.blocked_model_routes),
                "rejected_routes": rejected_routes,
                "policy_name": self.policy_id,
                "gateway_resource": gateway_resource,
            },
            "tool_egress_policy": {
                "checked": True,
                "blocked": bool(rejected_tools),
                "requested_tools": list(tool_names),
                "allowed_tools": list(self.allowed_tools),
                "blocked_tools": list(self.blocked_tools),
                "rejected_tools": rejected_tools,
                "policy_name": self.policy_id,
                "gateway_resource": gateway_resource,
            },
            "egress_decision": {
                "checked": True,
                "blocked": blocked,
                "context": context,
                "reason": reason,
            },
            "notes": [
                "Google Agent Gateway control-plane configuration was verified before live execution.",
                "BARRED-Fleet still applies an application egress policy because this Cloud Run path is not Agent Runtime traffic.",
                "Deterministic B-gate remains the acceptance authority.",
            ],
        }

    def _gateway_resource(self) -> str:
        if not self.project_id or not self.location_id or not self.gateway_id:
            return ""
        if self.gateway_id.startswith("projects/"):
            return self.gateway_id
        return (
            f"projects/{self.project_id}/locations/{self.location_id}/"
            f"agentGateways/{self.gateway_id}"
        )

    def _resolved_client(self) -> CloudAgentGatewayClient:
        return self.client or GoogleCloudAgentGatewayClient()


class GoogleCloudAgentGatewayClient:
    def get_agent_gateway(self, *, gateway_resource: str) -> Mapping[str, Any]:
        try:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
        except ImportError as exc:
            raise RuntimeError("google-auth is not installed") from exc

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        session = AuthorizedSession(credentials)
        response = session.get(
            f"{NETWORK_SERVICES_ENDPOINT}/{gateway_resource}",
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Agent Gateway response was not a JSON object")
        return payload


class ErrorAgentGateway:
    def __init__(self, *, mode: str) -> None:
        self.mode = mode

    def evaluate_egress(
        self,
        *,
        model_routes: Mapping[str, str],
        tool_names: Sequence[str],
        context: str,
    ) -> dict[str, Any]:
        return {
            "status": "error",
            "control": "agent_gateway",
            "mode": self.mode,
            "decision_authority": "routing_and_egress_only",
            "model_route_policy": {
                "checked": False,
                "blocked": True,
                "requested_routes": dict(model_routes),
                "allowed_routes": [],
                "blocked_routes": [],
                "rejected_routes": [],
            },
            "tool_egress_policy": {
                "checked": False,
                "blocked": True,
                "requested_tools": list(tool_names),
                "allowed_tools": [],
                "blocked_tools": [],
                "rejected_tools": [],
            },
            "egress_decision": {
                "checked": True,
                "blocked": True,
                "context": context,
                "reason": "unsupported_agent_gateway_mode",
            },
            "error": f"unsupported Agent Gateway mode: {self.mode}",
            "notes": [
                "Unsupported Agent Gateway configuration fails closed before live execution.",
                "Deterministic B-gate remains the acceptance authority.",
            ],
        }


def build_agent_gateway(
    *,
    env: Mapping[str, str],
) -> AgentGateway:
    mode = env.get(AGENT_GATEWAY_MODE_ENV, "").strip()
    if not mode or mode == AGENT_GATEWAY_MODE_NOT_CONFIGURED:
        return NotConfiguredAgentGateway()
    if mode == AGENT_GATEWAY_MODE_LOCAL_POLICY:
        return LocalPolicyAgentGateway(
            allowed_model_routes=_env_list(
                env,
                AGENT_GATEWAY_ALLOWED_MODEL_ROUTES_ENV,
                DEFAULT_ALLOWED_MODEL_ROUTES,
            ),
            blocked_model_routes=_env_list(
                env,
                AGENT_GATEWAY_BLOCKED_MODEL_ROUTES_ENV,
                (),
            ),
            allowed_tools=_env_list(
                env,
                AGENT_GATEWAY_ALLOWED_TOOLS_ENV,
                DEFAULT_ALLOWED_TOOLS,
            ),
            blocked_tools=_env_list(env, AGENT_GATEWAY_BLOCKED_TOOLS_ENV, ()),
        )
    if mode == AGENT_GATEWAY_MODE_CLOUD_AGENT_GATEWAY:
        return CloudAgentGateway(
            project_id=_env_first(
                env,
                AGENT_GATEWAY_PROJECT_ENV,
                "GOOGLE_CLOUD_PROJECT",
            ),
            location_id=_env_first(
                env,
                AGENT_GATEWAY_LOCATION_ENV,
                "GOOGLE_CLOUD_LOCATION",
            ),
            gateway_id=env.get(AGENT_GATEWAY_ID_ENV, ""),
            policy_id=env.get(AGENT_GATEWAY_POLICY_ID_ENV, ""),
            audit_only=_env_flag(AGENT_GATEWAY_AUDIT_ONLY_ENV, env),
            allowed_model_routes=_env_list(
                env,
                AGENT_GATEWAY_ALLOWED_MODEL_ROUTES_ENV,
                DEFAULT_ALLOWED_MODEL_ROUTES,
            ),
            blocked_model_routes=_env_list(
                env,
                AGENT_GATEWAY_BLOCKED_MODEL_ROUTES_ENV,
                (),
            ),
            allowed_tools=_env_list(
                env,
                AGENT_GATEWAY_ALLOWED_TOOLS_ENV,
                DEFAULT_ALLOWED_TOOLS,
            ),
            blocked_tools=_env_list(env, AGENT_GATEWAY_BLOCKED_TOOLS_ENV, ()),
        )
    return ErrorAgentGateway(mode=mode)


def build_not_configured_agent_gateway_status(
    *,
    context: str = "",
) -> dict[str, Any]:
    return {
        "status": "not_configured",
        "control": "agent_gateway",
        "decision_authority": "none",
        "model_route_policy": {
            "checked": False,
            "blocked": False,
            "requested_routes": {},
            "allowed_routes": [],
            "blocked_routes": [],
            "rejected_routes": [],
        },
        "tool_egress_policy": {
            "checked": False,
            "blocked": False,
            "requested_tools": [],
            "allowed_tools": [],
            "blocked_tools": [],
            "rejected_tools": [],
        },
        "egress_decision": {
            "checked": False,
            "blocked": False,
            "context": context,
            "reason": "not_configured",
        },
        "notes": [
            "Agent Gateway is not active until deployed and verified.",
            "Deterministic B-gate remains the acceptance authority.",
        ],
    }


def _env_list(
    env: Mapping[str, str],
    name: str,
    default: Sequence[str],
) -> tuple[str, ...]:
    raw_value = env.get(name)
    if raw_value is None or not raw_value.strip():
        return tuple(default)
    return tuple(_non_empty_values(raw_value.replace("|", ",").split(",")))


def _non_empty_values(values: Sequence[str]) -> list[str]:
    return [value.strip() for value in values if value.strip()]


def _rejected_values(
    values: Sequence[str],
    *,
    allowed_values: Sequence[str],
    blocked_values: Sequence[str],
) -> list[str]:
    allowed = set(allowed_values)
    blocked = set(blocked_values)
    return [
        value
        for value in values
        if value in blocked or (allowed and value not in allowed)
    ]


def _decision_reason(
    *,
    rejected_routes: Sequence[str],
    rejected_tools: Sequence[str],
) -> str:
    if rejected_routes:
        return "model_route_blocked"
    if rejected_tools:
        return "tool_egress_blocked"
    return "passed"


def _cloud_agent_gateway_error_receipt(
    *,
    reason: str,
    context: str,
    model_routes: Mapping[str, str],
    tool_names: Sequence[str],
    gateway_resource: str,
    policy_name: str,
    error_type: str = "",
) -> dict[str, Any]:
    egress_decision = {
        "checked": True,
        "blocked": True,
        "context": context,
        "reason": reason,
    }
    if error_type:
        egress_decision["error_type"] = error_type
    return {
        "status": "error",
        "control": "agent_gateway",
        "mode": AGENT_GATEWAY_MODE_CLOUD_AGENT_GATEWAY,
        "decision_authority": "routing_and_egress_only",
        "cloud_control_plane": {
            "checked": True,
            "blocked": True,
            "gateway_resource": gateway_resource,
            "policy_name": policy_name,
            "reason": reason,
        },
        "model_route_policy": {
            "checked": False,
            "blocked": True,
            "requested_routes": dict(model_routes),
            "allowed_routes": [],
            "blocked_routes": [],
            "rejected_routes": [],
            "policy_name": policy_name,
            "gateway_resource": gateway_resource,
        },
        "tool_egress_policy": {
            "checked": False,
            "blocked": True,
            "requested_tools": list(tool_names),
            "allowed_tools": [],
            "blocked_tools": [],
            "rejected_tools": [],
            "policy_name": policy_name,
            "gateway_resource": gateway_resource,
        },
        "egress_decision": egress_decision,
        "notes": [
            "Cloud Agent Gateway could not verify egress governance; live execution blocks fail-closed.",
            "Deterministic B-gate remains the acceptance authority.",
        ],
    }


def _validate_cloud_gateway_config(
    gateway_config: Mapping[str, Any],
    *,
    gateway_resource: str,
) -> str:
    configured_name = str(gateway_config.get("name", "")).strip()
    if configured_name != gateway_resource:
        return "cloud_agent_gateway_name_mismatch"
    governed_access_path = _extract_response_value(
        gateway_config,
        "googleManaged.governedAccessPath",
    )
    if governed_access_path and governed_access_path != "AGENT_TO_ANYWHERE":
        return "cloud_agent_gateway_not_egress"
    return ""


def _extract_response_value(response: Mapping[str, Any], dotted_path: str) -> str:
    current: Any = response
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping):
            return ""
        current = current.get(part)
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


def _env_flag(name: str, env: Mapping[str, str]) -> bool:
    return env.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
