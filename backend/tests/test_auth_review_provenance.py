"""DB-free provenance tests for authenticated human review identity.

The browser may submit a display-name field for development compatibility, but
when middleware has bound an authenticated identity the persisted provenance
must come from that signed server-side identity only.
"""

import uuid

from app.auth.provenance import _apply_review_identity
from app.auth.runtime import bind_identity, reset_identity
from app.auth.service import AuthIdentity
from app.database.models.fact_review import ContractReview, FactReview


def _identity() -> AuthIdentity:
    return AuthIdentity(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        organization_slug="hospital-a",
        username="reviewer",
        display_name="Authenticated Reviewer",
        role="reviewer",
    )


def test_fact_review_authenticated_identity_overrides_spoofed_client_name():
    identity = _identity()
    row = FactReview(
        contract_id=uuid.uuid4(),
        fact_key="identity.contract_number",
        action="confirmed",
        reviewer_display_name="Spoofed Name",
        reviewer_identity_type="manual_unverified",
        authenticated_actor_id=None,
    )
    token = bind_identity(identity)
    try:
        _apply_review_identity(row)
    finally:
        reset_identity(token)

    assert row.reviewer_display_name == identity.display_name
    assert row.reviewer_identity_type == "authenticated_local"
    assert row.authenticated_actor_id == identity.user_id


def test_contract_review_authenticated_identity_overrides_spoofed_client_name():
    identity = _identity()
    row = ContractReview(
        contract_id=uuid.uuid4(),
        status="reviewed",
        reviewer_display_name="Spoofed Name",
        reviewer_identity_type="manual_unverified",
        authenticated_actor_id=None,
    )
    token = bind_identity(identity)
    try:
        _apply_review_identity(row)
    finally:
        reset_identity(token)

    assert row.reviewer_display_name == identity.display_name
    assert row.reviewer_identity_type == "authenticated_local"
    assert row.authenticated_actor_id == identity.user_id


def test_manual_review_identity_remains_explicitly_unverified_without_auth_context():
    row = FactReview(
        contract_id=uuid.uuid4(),
        fact_key="identity.contract_number",
        action="confirmed",
        reviewer_display_name="Manual Reviewer",
        reviewer_identity_type="manual_unverified",
        authenticated_actor_id=None,
    )
    _apply_review_identity(row)
    assert row.reviewer_display_name == "Manual Reviewer"
    assert row.reviewer_identity_type == "manual_unverified"
    assert row.authenticated_actor_id is None


def test_contract_review_dto_serialises_authenticated_actor_id(monkeypatch):
    """Ein angemeldet abgeschlossener Review darf die Vertragsakte nicht mit 500 brechen."""
    from app.contracts.detail.models import ContractReviewDto
    from app.contracts.review import service

    actor = uuid.uuid4()
    row = ContractReview(
        contract_id=uuid.uuid4(),
        status="reviewed",
        reviewer_display_name="Authenticated Reviewer",
        reviewer_identity_type="authenticated_local",
        authenticated_actor_id=actor,
    )
    monkeypatch.setattr(service, "get_contract_review", lambda *a, **k: row)
    dto = service.build_contract_review_dto(None, organization_id=uuid.uuid4(), contract_id=row.contract_id)
    assert ContractReviewDto.model_validate(dto).authenticated_actor_id == str(actor)
