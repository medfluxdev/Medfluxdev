"""Phase 2D: actual legacy-row CRUD in a rolled-back disposable migration DB.

No application code, global fixture or schema migration is changed. The fixture
uses synthetic metadata only; no file is written to artifact storage.
"""
import os

import pytest
from sqlalchemy import create_engine, text

from tests.test_drift1_migrated_integration import approved_url


@pytest.mark.skipif(not os.environ.get("DRIFT1_MIGRATED_TEST_DATABASE_URL"), reason="Opt-in disposable migrated DB only")
def test_real_legacy_null_and_recorded_equipment_rows_rollback():
    raw = approved_url(os.environ["DRIFT1_MIGRATED_TEST_DATABASE_URL"])
    engine = create_engine(raw, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            name, port = conn.execute(text("SELECT current_database(), inet_server_port()")).one()
            assert (name, port) == (engine.url.database, 55432)
            assert conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one() == "b3c5d7e90928"
            baseline = conn.execute(text("SELECT count(*) FROM public.contract_equipment")).scalar_one()

            # End the implicit read transaction before starting the write scope.
            conn.rollback()
            # One transaction for the complete FK chain, updates and assertions.
            # NEVER commit: close/rollback even if an assertion fails.
            tx = conn.begin()
            try:
                org = conn.execute(text(
                    "INSERT INTO public.organization (name, slug) "
                    "VALUES ('DRIFT1 disposable fixture', :slug) RETURNING id"
                ), {"slug": "drift1-legacy-fixture-" + os.urandom(6).hex()}).scalar_one()
                contract = conn.execute(text(
                    "INSERT INTO public.contract (organization_id, scope_type, lifecycle_state) "
                    "VALUES (:org, 'organization', 'active') RETURNING id"
                ), {"org": org}).scalar_one()
                doc = conn.execute(text(
                    "INSERT INTO public.document_file "
                    "(organization_id, original_filename, stored_filename, file_extension, "
                    "file_size_bytes, sha256, storage_key, import_status, duplicate_detected) "
                    "VALUES (:org, 'synthetic.pdf', 'synthetic.pdf', '.pdf', 0, :sha, "
                    "'drift1-disposable-only/no-file', 'imported', false) RETURNING id"
                ), {"org": org, "sha": os.urandom(32).hex()}).scalar_one()
                version = conn.execute(text(
                    "INSERT INTO public.document_version "
                    "(organization_id, document_file_id, version_no, sha256, storage_key) "
                    "VALUES (:org, :doc, 1, :sha, 'drift1-disposable-only/no-file') RETURNING id"
                ), {"org": org, "doc": doc, "sha": os.urandom(32).hex()}).scalar_one()
                extraction = conn.execute(text(
                    "INSERT INTO public.contract_extraction "
                    "(organization_id, document_version_id, status, validation_status, requires_review) "
                    "VALUES (:org, :version, 'partial', 'unknown', true) RETURNING id"
                ), {"org": org, "version": version}).scalar_one()

                legacy = conn.execute(text(
                    "INSERT INTO public.contract_equipment "
                    "(organization_id, contract_id, extraction_id, device_name, "
                    "identification_quality, relationship_quality, requires_review) "
                    "VALUES (:org, :contract, :extraction, 'Synthetic legacy unknown', "
                    "NULL, NULL, NULL) RETURNING id"
                ), {"org": org, "contract": contract, "extraction": extraction}).scalar_one()
                recorded = conn.execute(text(
                    "INSERT INTO public.contract_equipment "
                    "(organization_id, contract_id, extraction_id, device_name, "
                    "identification_quality, relationship_quality, requires_review) "
                    "VALUES (:org, :contract, :extraction, 'Synthetic recorded verdict', "
                    "'unknown', 'ambiguous', true) RETURNING id"
                ), {"org": org, "contract": contract, "extraction": extraction}).scalar_one()

                rows = conn.execute(text(
                    "SELECT id, identification_quality, relationship_quality, requires_review "
                    "FROM public.contract_equipment WHERE id IN (:legacy, :recorded)"
                ), {"legacy": legacy, "recorded": recorded}).all()
                by_id = {r.id: r for r in rows}
                assert len(by_id) == 2
                assert tuple(by_id[legacy][1:]) == (None, None, None)
                assert tuple(by_id[recorded][1:]) == ("unknown", "ambiguous", True)

                counts = conn.execute(text(
                    "SELECT count(*) AS total, "
                    "count(*) FILTER (WHERE identification_quality IS NULL), "
                    "count(*) FILTER (WHERE relationship_quality IS NULL), "
                    "count(*) FILTER (WHERE requires_review IS NULL) "
                    "FROM public.contract_equipment WHERE id IN (:legacy, :recorded)"
                ), {"legacy": legacy, "recorded": recorded}).one()
                assert tuple(counts) == (2, 1, 1, 1)

                # Exercise an actual update without converting legacy NULLs
                # or inventing an identification/relationship verdict.
                conn.execute(text(
                    "UPDATE public.contract_equipment SET device_name = :name WHERE id = :id"
                ), {"name": "Synthetic legacy renamed", "id": legacy})
                assert conn.execute(text(
                    "SELECT device_name, identification_quality, relationship_quality, "
                    "requires_review FROM public.contract_equipment WHERE id = :id"
                ), {"id": legacy}).one() == ("Synthetic legacy renamed", None, None, None)
            finally:
                tx.rollback()

            assert conn.execute(text(
                "SELECT count(*) FROM public.contract_equipment"
            )).scalar_one() == baseline
            assert conn.execute(text(
                "SELECT count(*) FROM public.organization WHERE id = :id"
            ), {"id": org}).scalar_one() == 0
    finally:
        engine.dispose()
