"""Evidence-aware policy/playbook evaluation primitives."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.contract_intelligence.models import PolicyCheck, PolicyDecision


Predicate = Callable[[Any, Any], bool | None]


def evaluate_policy(check: PolicyCheck, actual: Any, predicate: Predicate) -> PolicyDecision:
    verdict = predicate(actual, check.expected)
    if verdict is None:
        outcome = "unknown"
        explanation = "Policy could not be evaluated from available contract facts."
    elif verdict:
        outcome = "pass"
        explanation = "Contract fact satisfies the configured policy."
    else:
        outcome = "fail"
        explanation = "Contract fact conflicts with the configured policy."
    return PolicyDecision(
        policy_key=check.key,
        outcome=outcome,
        explanation=explanation,
        requires_review=outcome in {"fail", "unknown"},
    )
