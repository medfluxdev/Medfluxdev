from app.ai.groups.normalize import ground_source_identity, ground_source_services
from app.documents.extraction.schemas import ExtractionUnit, SourceType
from app.models.contract import Contract
from app.models.enums import ContractType


def _unit(source_type: SourceType, index: int, text: str) -> ExtractionUnit:
    return ExtractionUnit(source_type=source_type, index=index, text=text)


def test_ground_source_identity_rejects_order_number_as_contract_number():
    contract = Contract()
    contract.identity.contract_number = "452664"
    units = [
        _unit(
            SourceType.PARAGRAPH,
            1,
            "Anbei erhalten Sie die Bestellung 452664 und den unterschriebenen Servicevertrag Guard TOP.",
        )
    ]
    issues = ground_source_identity(contract, units)
    assert contract.identity.contract_number is None
    assert any("Bestellnummer" in issue for issue in issues)


def test_ground_source_identity_rejects_bestell_nr_variant():
    contract = Contract()
    contract.identity.contract_number = "452664"
    ground_source_identity(contract, [_unit(SourceType.PARAGRAPH, 1, "Bestell-Nr. 452664")])
    assert contract.identity.contract_number is None


def test_ground_source_identity_keeps_explicit_contract_number():
    contract = Contract()
    contract.identity.contract_number = "452664"
    units = [
        _unit(SourceType.PARAGRAPH, 1, "Bestellung 452664"),
        _unit(SourceType.PARAGRAPH, 2, "Vertragsnummer: 452664"),
    ]
    ground_source_identity(contract, units)
    assert contract.identity.contract_number == "452664"


def test_ground_source_identity_keeps_vertrags_nr_variant():
    contract = Contract()
    contract.identity.contract_number = "452664"
    units = [
        _unit(SourceType.PARAGRAPH, 1, "Bestell-Nr. 452664"),
        _unit(SourceType.PARAGRAPH, 2, "Vertrags-Nr. 452664"),
    ]
    ground_source_identity(contract, units)
    assert contract.identity.contract_number == "452664"


def test_ground_source_identity_keeps_explicit_offer_number():
    contract = Contract()
    contract.identity.contract_number = "A-7788"
    ground_source_identity(contract, [_unit(SourceType.PARAGRAPH, 1, "Angebots-Nr. A-7788")])
    assert contract.identity.contract_number == "A-7788"


def test_ground_source_identity_canonicalizes_ocr_party_name_from_clean_source():
    contract = Contract()
    contract.identity.customer = "KRANKENHAUS N07;fPNEST GMRH"
    units = [
        _unit(SourceType.TABLE, 1, "Auftraggeber | Auftragnehmer\nKRANKENHAUS N07;fPNEST GMRH | MEDTRON AG"),
        _unit(SourceType.PARAGRAPH, 27, "Monique Arras / MPG Koordinatorin / Krankenhaus Nordwest GmbH / Steinbacher Hohl 2-26"),
    ]
    issues = ground_source_identity(contract, units)
    assert contract.identity.customer == "Krankenhaus Nordwest GmbH"
    assert any("customer" in issue for issue in issues)


def test_ground_source_identity_collapses_concatenated_customer_to_role_grounded_company():
    contract = Contract()
    contract.identity.customer = (
        "Krankenhaus Nordwest GmbH; Hospital zum Heiligen Geist GmbH; "
        "FÄZ Fachärztezentrum Frankfurt GmbH; Stiftung Hospital zum Heiligen Geist"
    )
    units = [
        _unit(SourceType.TABLE, 1, "Auftraggeber | Auftragnehmer\nKRANKENHAUS N07;fPNEST GMRH | MEDTRON AG"),
        _unit(SourceType.PARAGRAPH, 27, "Monique Arras / MPG Koordinatorin / Krankenhaus Nordwest GmbH / Steinbacher Hohl 2-26"),
        _unit(SourceType.PARAGRAPH, 28, "Hospital zum Heiligen Geist GmbH"),
    ]
    ground_source_identity(contract, units)
    assert contract.identity.customer == "Krankenhaus Nordwest GmbH"


def test_ground_source_identity_reads_role_row_after_embedded_table_lines():
    contract = Contract()
    contract.identity.supplier = "MED TRON AG (Valentina Malvaso, Customer Service DACH)"
    units = [
        _unit(
            SourceType.TABLE,
            1,
            "Auftraggeber | Auftragnehmer\nStraße Auftraggeber\nPLZ Auftraggeber\nKontakt Auftraggeber\nTelefon Auftraggeber\n"
            "KRANKENHAUS N07;fPNEST GMRH | MEDTRON AG",
        ),
        _unit(SourceType.PARAGRAPH, 20, "MED TRON AG (Valentina Malvaso, Customer Service DACH)"),
    ]
    ground_source_identity(contract, units)
    assert contract.identity.supplier == "MEDTRON AG"


def test_ground_source_identity_reconstructs_multiline_customer_cell_before_pipe_separator():
    contract = Contract()
    contract.identity.customer = (
        "Krankenhaus Nordwest GmbH; Hospital zum Heiligen Geist GmbH; "
        "FÄZ Fachärztezentrum Frankfurt GmbH"
    )
    units = [
        _unit(
            SourceType.TABLE,
            1,
            "Auftraggeber | Auftragnehmer\n"
            "KRANKENHAUS N07;fPNEST GMRH\n"
            "Steinbacher Hohl 2-26\n"
            "6e480 Frank;furt am Main | MEDTRON AG\n"
            "Hauptstraße 255\nD-66128 Saarbrücken",
        ),
        _unit(SourceType.PARAGRAPH, 27, "Krankenhaus Nordwest GmbH / Steinbacher Hohl 2-26"),
    ]
    ground_source_identity(contract, units)
    assert contract.identity.customer == "Krankenhaus Nordwest GmbH"
    assert contract.identity.supplier == "MEDTRON AG"


def test_ground_source_identity_never_promotes_address_line_to_customer():
    contract = Contract()
    units = [
        _unit(
            SourceType.TABLE,
            1,
            "Auftraggeber | Auftragnehmer\n"
            "Steinbacher Hohl 2-26\n"
            "6e480 Frank;furt am Main | MEDTRON AG\n"
            "Hauptstraße 255\nD-66128 Saarbrücken",
        )
    ]
    ground_source_identity(contract, units)
    assert contract.identity.customer is None
    assert contract.identity.supplier == "MEDTRON AG"


def test_ground_source_identity_fills_supplier_only_from_explicit_table_role():
    contract = Contract()
    units = [_unit(SourceType.TABLE, 1, "Auftraggeber | Auftragnehmer\nKrankenhaus Nordwest GmbH | MEDTRON AG")]
    ground_source_identity(contract, units)
    assert contract.identity.customer == "Krankenhaus Nordwest GmbH"
    assert contract.identity.supplier == "MEDTRON AG"


def test_ground_source_identity_fills_explicit_title_and_type():
    contract = Contract()
    units = [
        _unit(SourceType.PARAGRAPH, 1, "MEDTRON Guard Servicevereinbarung Accutron MR"),
        _unit(SourceType.PARAGRAPH, 2, "Weitere Vertragsinformationen"),
    ]
    ground_source_identity(contract, units)
    assert contract.identity.contract_title == "MEDTRON Guard Servicevereinbarung Accutron MR"
    assert contract.identity.contract_type == ContractType.SERVICE


def test_ground_source_identity_prioritizes_explicit_heading_over_email_subject():
    contract = Contract()
    contract.identity.contract_title = "Servicevertrag Guard TOP für Accutron MR"
    units = [
        _unit(SourceType.PARAGRAPH, 1, "MEDTRON Guard Servicevereinbarung Accutron MR"),
        _unit(SourceType.PARAGRAPH, 14, "Betreff: Servicevertrag Guard TOP für Accutron MR"),
    ]
    ground_source_identity(contract, units)
    assert contract.identity.contract_title == "MEDTRON Guard Servicevereinbarung Accutron MR"
    assert contract.identity.contract_type == ContractType.SERVICE


def test_ground_source_identity_does_not_infer_title_from_generic_prose():
    contract = Contract()
    units = [
        _unit(SourceType.PARAGRAPH, 1, "Vielen Dank für Ihre Bestellung."),
        _unit(SourceType.PARAGRAPH, 2, "Das Gerät wird im Krankenhaus eingesetzt."),
    ]
    ground_source_identity(contract, units)
    assert contract.identity.contract_title is None
    assert contract.identity.contract_type == ContractType.UNKNOWN


def test_ground_source_identity_does_not_replace_distinct_company():
    contract = Contract()
    contract.identity.customer = "Krankenhaus Süd GmbH"
    units = [
        _unit(SourceType.TABLE, 1, "Auftraggeber | Krankenhaus Süd GmbH"),
        _unit(SourceType.PARAGRAPH, 2, "Lieferant MEDTRON AG"),
        _unit(SourceType.PARAGRAPH, 3, "Krankenhaus Nordwest GmbH"),
    ]
    ground_source_identity(contract, units)
    assert contract.identity.customer == "Krankenhaus Süd GmbH"


def test_ground_source_services_promotes_supported_null_flags_to_true():
    contract = Contract()
    contract.services.included_services = [
        "Wartung inkl. Austausch von Verschleißteilen",
        "Notwendige Software-Updates",
        "Kostenlose Reparaturen",
    ]
    units = [
        _unit(
            SourceType.TABLE,
            2,
            "Wartung inkl. Austausch von Verschleißteilen | X\n"
            "Notwendige Software-Updates | X\nKostenlose Reparaturen | X",
        )
    ]
    issues = ground_source_services(contract, units)
    assert contract.services.maintenance is True
    assert contract.services.repair is True
    assert contract.services.software_updates is True
    assert len(issues) == 3


def test_ground_source_services_never_turns_absence_into_false_or_true():
    contract = Contract()
    contract.services.included_services = ["Arbeitszeit", "Fahrtkosten"]
    units = [_unit(SourceType.TABLE, 2, "Arbeitszeit | X\nFahrtkosten | X")]
    ground_source_services(contract, units)
    assert contract.services.maintenance is None
    assert contract.services.repair is None
    assert contract.services.software_updates is None
