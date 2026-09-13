from pathlib import Path

from app.database.models.fact_review import ContractReview, FactReview
from app.database.models.override import ContractOverride


def test_unified_actor_provenance_columns_do_not_point_only_to_app_user():
    assert not FactReview.__table__.c.authenticated_actor_id.foreign_keys
    assert not ContractReview.__table__.c.authenticated_actor_id.foreign_keys
    assert not ContractOverride.__table__.c.actor_id.foreign_keys


def test_organization_user_admin_does_not_toggle_global_account_active():
    source = Path("app/api/routes/users.py").read_text(encoding="utf-8")
    assert "account.is_active = payload.is_active" not in source
    assert 'changes["membership_is_active"] = payload.is_active' in source


def test_multi_org_global_identity_mutations_are_guarded():
    source = Path("app/api/routes/users.py").read_text(encoding="utf-8")
    assert "membership_count > 1 and not actor.is_developer" in source
    assert "organisationsübergreifenden Kontos" in source


def test_non_admin_user_creation_requires_and_persists_scope_atomically():
    source = Path("app/api/routes/users.py").read_text(encoding="utf-8")
    assert 'role != "admin" and hospital_id is None' in source
    assert "membership.hospital_id = hospital_id" in source
    assert "membership.department_id = department_id" in source
    assert "membership.is_default = True" in source


def test_admin_downgrade_cannot_create_global_non_admin():
    source = Path("app/api/routes/users.py").read_text(encoding="utf-8")
    assert 'payload.role != "admin" and membership.hospital_id is None' in source
    assert "Vor dem Rollenwechsel muss ein Krankenhaus zugewiesen werden." in source
