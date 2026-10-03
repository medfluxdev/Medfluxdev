from datetime import date
from decimal import Decimal

from app.contract_intelligence.clauses import fingerprint_clause
from app.contract_intelligence.invoice import ContractCharge, InvoiceLine, reconcile_invoice, value_leakage
from app.contract_intelligence.portfolio import answer_portfolio_question
from app.contract_intelligence.models import PortfolioQuestion
from app.contract_intelligence.risk import RiskFinding, summarize_risk
from app.contract_intelligence.search import evidence_first_answer
from app.contract_intelligence.workflows import commands_for_event


def test_clause_fingerprint_normalizes_numbers():
    a = fingerprint_clause("Response within 48 hours")
    b = fingerprint_clause("Response within 24 hours")
    assert a.fingerprint == b.fingerprint


def test_invoice_reconciliation_detects_overbilling_without_guessing():
    findings = reconcile_invoice(
        [InvoiceLine(label="service", amount=Decimal("1800"), currency="EUR")],
        [ContractCharge(label="service", amount=Decimal("1650"), currency="EUR", charge_type="fixed", applicable=True)],
    )
    assert findings[0].outcome == "overbilled"
    assert value_leakage(findings)["EUR"] == Decimal("150")


def test_ambiguous_invoice_match_requires_review():
    findings = reconcile_invoice(
        [InvoiceLine(label="service", amount=Decimal("100"), currency="EUR")],
        [],
    )
    assert findings[0].outcome == "unknown"
    assert findings[0].requires_review


def test_portfolio_uncovered_filter_uses_persisted_state_only():
    result = answer_portfolio_question(
        PortfolioQuestion(query="show uncovered equipment"),
        [{"contract_id": None, "equipment_coverage": "uncovered"}],
    )
    assert result.answer.startswith("1 matching")


def test_risk_is_explainable():
    result = summarize_risk([RiskFinding(key="sla", severity="high", explanation="SLA below policy")])
    assert result["level"] == "high"
    assert result["reasons"][0]["key"] == "sla"


def test_evidence_first_answer_marks_ungrounded():
    assert evidence_first_answer("x", [])["requires_review"] is True


def test_contract_event_fans_out_to_deterministic_workflows():
    names = [x.event_type for x in commands_for_event("contract.accepted", "c1")]
    assert names == ["policy.evaluate", "obligations.refresh", "work_queue.refresh"]
