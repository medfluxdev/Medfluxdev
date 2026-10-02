from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.documents.status import build_import_state, safe_failure_message


class _Rows:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


@pytest.mark.parametrize(
    ("run_status", "expected_state", "retry"),
    [
        ("success", "analysis_ok", False),
        ("partial", "analysis_partial", False),
        ("failed", "analysis_failed", True),
    ],
)
def test_import_state_distinguishes_analysis_outcomes(run_status, expected_state, retry):
    contract = SimpleNamespace(accepted_extraction_id=uuid4())
    version = uuid4()
    run = SimpleNamespace(status=run_status, message="some safe message", error=None)
    calls = iter([_Rows(version), _Rows(run)])
    session = SimpleNamespace(get=lambda *args: contract, scalars=lambda *args: next(calls))

    result = build_import_state(
        session, organization_id=uuid4(), contract_id=uuid4(), detail={"review": {}}
    )

    assert result["import_state"] == expected_state
    assert result["can_retry"] is retry
    assert result["requires_review"] is (expected_state != "analysis_ok")
    if expected_state == "analysis_partial":
        assert result["analysis_status"] == "partial"
        assert "Teilanalyse" in result["state_label_de"]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("HarnessFailure category=invalid_schema", "Ausgabeformat"),
        ("HarnessFailure category=insufficient_memory", "Arbeitsspeicher"),
        ("HarnessFailure category=model_runner_stopped", "beendet"),
        ("HarnessFailure category=timeout", "rechtzeitig"),
    ],
)
def test_safe_failure_message_explains_known_ai_failure_categories(error, expected):
    message = safe_failure_message(message="Analyse fehlgeschlagen.", error=error)
    assert expected in message
    assert error not in message


def test_safe_failure_message_does_not_expose_unknown_provider_payload():
    raw = "private document fragment and internal endpoint details"
    assert safe_failure_message(message="Analyse fehlgeschlagen.", error=raw) == "Analyse fehlgeschlagen."


def test_successful_run_without_accepted_extraction_is_not_reported_as_success():
    version = uuid4()
    run = SimpleNamespace(status="success", message="Analyse abgeschlossen.", error=None)
    calls = iter([_Rows(version), _Rows(run)])
    session = SimpleNamespace(
        get=lambda *args: SimpleNamespace(accepted_extraction_id=None),
        scalars=lambda *args: next(calls),
    )

    result = build_import_state(
        session, organization_id=uuid4(), contract_id=uuid4(), detail={"review": {}}
    )

    assert result["import_state"] == "analysis_failed"
    assert result["can_retry"] is True
    assert "nicht sicher übernommen" in result["message"]
