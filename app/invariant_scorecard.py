from __future__ import annotations

from typing import Any


INVARIANT_SCORECARD_DEFINITIONS: tuple[dict[str, str], ...] = (
    {
        "key": "total_rows",
        "label": "Total accepted corpus rows",
        "format": "integer",
        "direction": "context",
    },
    {
        "key": "accepted_rows",
        "label": "Accepted rows",
        "format": "integer",
        "direction": "context",
    },
    {
        "key": "b0_structural_completeness_pass_rate",
        "label": "Structural completeness",
        "format": "percent",
        "direction": "higher_is_better",
    },
    {
        "key": "b1_unsupported_in_accepted_rate",
        "label": "Unsupported accepted rate",
        "format": "percent",
        "direction": "lower_is_better",
    },
    {
        "key": "b1_inconclusive_in_accepted_rate",
        "label": "Inconclusive accepted rate",
        "format": "percent",
        "direction": "lower_is_better",
    },
    {
        "key": "b2_anchor_match_rate",
        "label": "Anchor match rate",
        "format": "percent",
        "direction": "higher_is_better",
    },
    {
        "key": "verifier_parse_ok_rate",
        "label": "Verifier parse OK",
        "format": "percent",
        "direction": "higher_is_better",
    },
    {
        "key": "verifier_pass_rate",
        "label": "Verifier pass",
        "format": "percent",
        "direction": "higher_is_better",
    },
    {
        "key": "accepted_attempt_logic_error_rate",
        "label": "Attempt logic error rate",
        "format": "percent",
        "direction": "lower_is_better",
    },
    {
        "key": "accepted_corpus_logic_error_rate",
        "label": "Corpus logic error rate",
        "format": "percent",
        "direction": "lower_is_better",
    },
)


def build_invariant_scorecard(
    selected_metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    metrics = selected_metrics or {}
    rows = [
        {
            **definition,
            "value": metrics.get(definition["key"]),
            "available": definition["key"] in metrics,
        }
        for definition in INVARIANT_SCORECARD_DEFINITIONS
    ]
    has_metrics = any(row["available"] for row in rows)
    return {
        "available": has_metrics,
        "reason": "" if has_metrics else "no_b_gate_metrics",
        "rows": rows,
    }
