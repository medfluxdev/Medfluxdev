from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_main_registers_operational_routers():
    source = read("app/main.py")
    for name in (
        "processing_jobs.router",
        "intelligence_actions.router",
        "notifications.router",
        "reports.router",
        "work_queue_collaboration.router",
        "lifecycle.router",
        "security_sessions.router",
    ):
        assert name in source


def test_intelligence_actions_are_human_controlled_and_scoped():
    source = read("app/api/routes/intelligence_actions.py")
    assert "scoped_contract_ids" in source
    assert "requires_human_approval" in source
    assert '"proposed": {"approved", "rejected", "cancelled"}' in source
    assert '"approved": {"executed", "cancelled"}' in source
    assert "ActivityLog" in source


def test_processing_jobs_reuse_processing_runs():
    source = read("app/api/routes/processing_jobs.py")
    assert "ProcessingRun" in source
    assert "ProcessingSummary" in source
    assert "scoped_contract_ids" in source
    assert "ProcessingJob" not in source


def test_notification_feed_is_projection_of_authoritative_domains():
    source = read("app/api/routes/notifications.py")
    assert "WorkItem" in source
    assert "ActionProposalRecord" in source
    assert "scoped_contract_ids" in source


def test_work_queue_collaboration_does_not_mutate_derived_work_item_fields():
    source = read("app/api/routes/work_queue_collaboration.py")
    assert "WorkItemCollaboration" in source
    assert "WorkItemComment" in source
    assert "work.status =" not in source
    assert "work.severity =" not in source
    assert "ActivityLog" in source


def test_lifecycle_workflows_preserve_canonical_contract_truth():
    source = read("app/api/routes/lifecycle.py")
    assert "ContractLifecycleDecision" in source
    assert "EquipmentLifecycleRecord" in source
    assert "scoped_contract_ids" in source
    assert ".status = status" in source
    assert "contract.status =" not in source


def test_security_and_readiness_are_registered():
    main = read("app/main.py")
    health = read("app/api/routes/health.py")
    security = read("app/security/request_context.py")
    sessions = read("app/api/routes/security_sessions.py")
    assert "RequestIdMiddleware" in main
    assert "LoginRateLimitMiddleware" in main
    assert "security_sessions.router" in main
    assert '@router.get("/ready")' in health
    assert "MAX_ATTEMPTS" in security
    assert 'router = APIRouter(prefix="/api/auth"' in sessions
    assert '@router.post("/logout-all")' in sessions
    assert "LoginSession.revoked_at" in sessions


def test_release_gate_runs_migrations_tests_frontend_and_packaging():
    workflow = (ROOT.parent / ".github/workflows/release-gate.yml").read_text(encoding="utf-8")
    assert "alembic upgrade head" in workflow
    assert "pytest -q" in workflow
    assert "npm run verify" in workflow
    assert "docker compose config" in workflow
