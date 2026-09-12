"""Regression-Tests: `_collect_sensitive_values` (Verifier) darf nie crashen.

PR-1: Ein echter Vertrag (CCE) stuerzte im semantischen Verifier ab, weil die
Pipeline fuer `payment.billing_interval` ein Pydantic-`SourceEvidence`-Objekt
mit `source_text=None` lieferte. `SourceEvidence` ist IMMER truthy, daher traf
der Guard `if p.evidence else None` nicht zu und `None[:120]` warf
`TypeError`. Der Verifier ist laut Vertrag aber nie abbruchrelevant.
"""

from app.ai.groups.verifier import _collect_sensitive_values
from app.models.contract import Contract
from app.models.evidence import SourceEvidence


def test_collect_sensitive_values_no_crash_when_source_text_none():
    contract = Contract()
    # Jede Section bekommt ein truthy SourceEvidence-Objekt OHNE source_text
    # (der exakte Ausloeser des PR-1-Crashs bei payment.billing_interval).
    for section in (
        contract.identity,
        contract.dates,
        contract.termination,
        contract.costs,
        contract.payment,
    ):
        section.evidence = SourceEvidence()

    # Muss ohne Exception durchlaufen; None darf nicht indiziert werden.
    values = _collect_sensitive_values(contract)
    assert values, "sensible Felder wurden gesammelt"
    for sv in values:
        # Ohne source_text bleibt der Beleg None statt eines Crashs.
        assert sv.evidence is None


def test_collect_sensitive_values_still_captures_source_text():
    contract = Contract()
    contract.payment.evidence = SourceEvidence(source_text="jaehrliche Zahlung")
    contract.payment.billing_interval = None

    values = _collect_sensitive_values(contract)
    by_field = {sv.field: sv for sv in values}
    # Beleg wird weiterhin erfasst (Fix schwaecht die Verifikation NICHT).
    assert by_field["payment.billing_interval"].evidence == "jaehrliche Zahlung"


def test_collect_sensitive_values_truncates_long_source_text():
    contract = Contract()
    contract.identity.evidence = SourceEvidence(source_text="x" * 300)

    values = _collect_sensitive_values(contract)
    by_field = {sv.field: sv for sv in values}
    ev = by_field["identity.contract_number"].evidence
    assert ev is not None
    assert len(ev) <= 120
