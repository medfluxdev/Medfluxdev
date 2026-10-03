"""DB-free tests for item-level included/excluded service grounding."""

from app.ai.groups.list_claim_verifier import verify_service_list_claims
from app.documents.extraction.schemas import ExtractionUnit, SourceType
from app.models.contract import Contract
from app.models.evidence import SourceEvidence


def _unit(text: str, index: int = 1) -> ExtractionUnit:
    return ExtractionUnit(source_type=SourceType.PARAGRAPH, index=index, text=text)


def test_each_included_service_must_exist_in_source():
    contract = Contract()
    contract.services.included_services = ["Wartung", "Software-Updates"]
    contract.services.evidence = SourceEvidence(source_text="Wartung ist enthalten")

    issues = verify_service_list_claims(contract, [_unit("Wartung ist enthalten")])
    assert any("Software-Updates" in issue for issue in issues)
    assert contract.services.evidence.requires_review is True


def test_included_service_list_passes_when_every_item_is_present():
    contract = Contract()
    contract.services.included_services = ["Wartung", "Software-Updates"]
    issues = verify_service_list_claims(
        contract,
        [
            _unit("Wartung ist enthalten", 1),
            _unit("Notwendige Software-Updates sind enthalten", 2),
        ],
    )
    assert issues == []


def test_excluded_service_requires_explicit_negative_semantics():
    contract = Contract()
    contract.services.excluded_services = ["Verbrauchsmaterial"]

    positive_only = verify_service_list_claims(
        contract, [_unit("Verbrauchsmaterial kann geliefert werden")]
    )
    assert any("Ausschluss nicht explizit" in issue for issue in positive_only)

    explicit_exclusion = verify_service_list_claims(
        contract, [_unit("Verbrauchsmaterial ist nicht enthalten")]
    )
    assert explicit_exclusion == []


def test_neighbor_clause_negation_does_not_prove_exclusion():
    contract = Contract()
    contract.services.excluded_services = ["Software-Updates"]

    issues = verify_service_list_claims(
        contract,
        [_unit("Wartung ist nicht enthalten; Software-Updates sind enthalten")],
    )

    assert any("Software-Updates" in issue for issue in issues)
