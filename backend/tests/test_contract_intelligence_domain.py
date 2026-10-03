from datetime import date

from app.contract_intelligence.authority import authority_rank, validate_authority
from app.contract_intelligence.models import (
    ContractRelation,
    Obligation,
    ObligationCondition,
    PolicyCheck,
)
from app.contract_intelligence.obligations import instantiate_obligation, obligation_is_actionable
from app.contract_intelligence.policy import evaluate_policy


def test_authority_rank_keeps_primary_above_secondary_unknown():
    assert authority_rank("primary") < authority_rank("secondary") < authority_rank("unknown")


def test_authority_requires_evidence_for_concrete_rank():
    relation = ContractRelation(relation_type="corroborates", authority="primary")
    assert validate_authority([relation])


def test_obligation_instance_never_invents_due_date():
    obligation = Obligation(key="sla.response", title="Respond", due_date=None)
    instance = instantiate_obligation(obligation, as_of=date(2026, 9, 12))
    assert instance.due_date is None
    assert instance.occurrence_key.endswith("2026-09-12")


def test_conditional_obligation_is_actionable():
    obligation = Obligation(
        key="renewal.notice",
        title="Notice",
        conditions=[ObligationCondition(kind="event", expression="before renewal")],
    )
    assert obligation_is_actionable(obligation) is True


def test_policy_unknown_is_reviewable():
    check = PolicyCheck(key="sla.max", description="SLA threshold", expected=48)
    decision = evaluate_policy(check, actual=None, predicate=lambda actual, expected: None)
    assert decision.outcome == "unknown"
    assert decision.requires_review is True
