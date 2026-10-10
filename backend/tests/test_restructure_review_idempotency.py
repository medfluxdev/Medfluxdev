"""Restructure Phase E: doppelt gesendete Prüfungen erzeugen keinen zweiten Eintrag; Konflikte sind 409-fähig (T14)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.contracts.overrides.service import record_override
from app.contracts.review.material import MATERIAL_FACTS
from app.contracts.review.service import ReviewConflict, record_fact_action
from app.database.models import Contract, ContractOverride, FactReview
from app.database.models.organization import Organization
from app.database.session import create_session

FACT = sorted(key for key, _, _ in MATERIAL_FACTS)[0]


def _contract(session):
    org = Organization(id=uuid4(), name="Idempotenz", slug=f"idem-{uuid4().hex[:10]}")
    session.add(org)
    session.flush()
    contract = Contract(organization_id=org.id, short_description="Test", supplier="Partner")
    session.add(contract)
    session.flush()
    return org.id, contract.id


def _count(session, model, contract_id):
    return session.scalar(select(func.count()).select_from(model).where(model.contract_id == contract_id))


def test_double_submitted_fact_review_is_stored_once():
    session = create_session()
    try:
        org_id, contract_id = _contract(session)
        args = dict(organization_id=org_id, contract_id=contract_id, fact_key=FACT, action="confirmed",
                    reviewer_display_name="Prüferin", system_value="X")
        first = record_fact_action(session, **args)
        second = record_fact_action(session, **args)
        assert second.id == first.id
        assert _count(session, FactReview, contract_id) == 1
        # Eine andere Aktion ist kein Duplikat.
        record_fact_action(session, **{**args, "action": "corrected", "corrected_value": "Y"})
        assert _count(session, FactReview, contract_id) == 2
        session.rollback()
    finally:
        session.close()


def test_stale_fact_review_raises_conflict_instead_of_overwriting():
    session = create_session()
    try:
        org_id, contract_id = _contract(session)
        base = dict(organization_id=org_id, contract_id=contract_id, fact_key=FACT, system_value="X")
        # Beim Laden war die Angabe ungeprüft (expected=None); inzwischen hat jemand bestätigt.
        record_fact_action(session, action="confirmed", reviewer_display_name="Kollege", **base)
        with pytest.raises(ReviewConflict):
            record_fact_action(session, action="corrected", corrected_value="Y", reviewer_display_name="Ich",
                               expected_reviewed_at=None, **base)
        assert _count(session, FactReview, contract_id) == 1
        session.rollback()
    finally:
        session.close()


def test_double_submitted_override_is_stored_once():
    session = create_session()
    try:
        org_id, contract_id = _contract(session)
        from app.contracts.overrides.keys import ALLOWED_KEYS
        key = sorted(ALLOWED_KEYS)[0]
        args = dict(organization_id=org_id, contract_id=contract_id, key=key, action="confirm", note="ok")
        assert record_override(session, **args).id == record_override(session, **args).id
        assert _count(session, ContractOverride, contract_id) == 1
        session.rollback()
    finally:
        session.close()
