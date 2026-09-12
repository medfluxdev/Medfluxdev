"""Blocker PR-5: Frische, isolierte Datenumgebung ist LEER.

Sichert die Daten-/Umgebungs-Trennung ab (UAT-Batch 1):
- pytest laeuft gegen das isolierte Schema `test` (conftest) – niemals gegen
  das Produktschema `public`.
- Eine frisch angelegte Datenumgebung enthaelt KEINE Demo-/Benchmark-/Fixture-
  Datensaetze: 0 Vertraege, 0 Geraete, 0 Work-Items, 0 Evidenz-/Provenienz,
  0 Berechnungen/Warnungen/Reviews. Es wird nichts geseedet.
"""

from sqlalchemy import text

from app.database.session import create_session

PRODUCT_DOMAINS = [
    "contract",
    "equipment",
    "contract_equipment",
    "work_item",
    "extraction_evidence",
    "fact_review",
    "contract_warning",
    "contract_override",
    "contract_review",
    "review_action",
    "document_version",
    "document_file",
    "contract_extraction",
    "calculation_run",
    "warning_evaluation_run",
    "calculation_review_flag",
]


def _assert_empty_table(session, table: str) -> None:
    count = session.execute(
        text(f'SELECT count(*) FROM "{table}"')
    ).scalar_one()
    assert count == 0, (
        f"Frische Datenumgebung ist nicht leer: Tabelle {table} enthaelt "
        f"{count} Datensaetze. Kein Demo-/Benchmark-/Testinhalt darf in eine "
        "frische Produktumgebung gelangen."
    )


def test_isolated_schema_is_active() -> None:
    with create_session() as session:
        schema = session.execute(
            text("SHOW search_path")
        ).scalar_one()
        assert "test" in schema, (
            "pytest muss gegen das isolierte Schema `test` laufen, nicht gegen "
            f"'public'. Aktueller search_path: {schema!r}"
        )


def test_fresh_environment_contains_no_product_records() -> None:
    with create_session() as session:
        for table in PRODUCT_DOMAINS:
            _assert_empty_table(session, table)