"""initial schema

Revision ID: 4d930fb1d75e
Revises:
Create Date: 2026-08-31 10:42:12.818688+00:00

Der zirkuläre FK document_artifact.processing_run_id <-> document_processing_result
wird bewusst in zwei Schritten angelegt: erst die Tabellen ohne den zirkulären
FK, dann der betreffende FK per ALTER TABLE, nachdem beide Tabellen existieren.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '4d930fb1d75e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('organization',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_organization')),
    sa.UniqueConstraint('slug', name=op.f('uq_organization_slug'))
    )
    op.create_table('document_file',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('external_id', sa.String(length=64), nullable=True),
    sa.Column('original_filename', sa.Text(), nullable=False),
    sa.Column('stored_filename', sa.Text(), nullable=False),
    sa.Column('file_extension', sa.String(length=16), nullable=False),
    sa.Column('mime_type', sa.String(length=128), nullable=True),
    sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('storage_key', sa.Text(), nullable=False),
    sa.Column('imported_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('import_status', sa.String(length=16), nullable=False),
    sa.Column('duplicate_detected', sa.Boolean(), nullable=False),
    sa.Column('duplicate_of_id', sa.UUID(), nullable=True),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("import_status IN ('duplicate', 'failed', 'imported', 'rejected')", name=op.f('ck_document_file_import_status')),
    sa.ForeignKeyConstraint(['duplicate_of_id'], ['document_file.id'], name=op.f('fk_document_file_duplicate_of_id_document_file'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_document_file_organization_id_organization'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_file')),
    sa.UniqueConstraint('sha256', name=op.f('uq_document_file_sha256'))
    )
    op.create_index('ix_document_file_imported_at', 'document_file', ['imported_at'], unique=False)
    op.create_table('document_version',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('document_file_id', sa.UUID(), nullable=False),
    sa.Column('version_no', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('storage_key', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_file_id'], ['document_file.id'], name=op.f('fk_document_version_document_file_id_document_file'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_document_version_organization_id_organization'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_version')),
    sa.UniqueConstraint('sha256', name=op.f('uq_document_version_sha256'))
    )
    op.create_index('ix_document_version_document_file_id', 'document_version', ['document_file_id'], unique=False)
    op.create_table('document_artifact',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('document_version_id', sa.UUID(), nullable=False),
    sa.Column('processing_run_id', sa.UUID(), nullable=True),
    sa.Column('artifact_type', sa.String(length=32), nullable=False),
    sa.Column('storage_key', sa.Text(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('format_version', sa.String(length=64), nullable=True),
    sa.Column('media_type', sa.String(length=128), nullable=True),
    sa.Column('lifecycle_state', sa.String(length=24), nullable=False),
    sa.Column('deletion_owner', sa.String(length=120), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("artifact_type IN ('canonical', 'contract_snapshot', 'debug', 'layout_diagnostics', 'ocr_diagnostics', 'original_file', 'other', 'preview', 'rendered')", name=op.f('ck_document_artifact_type')),
    sa.CheckConstraint("lifecycle_state IN ('active', 'deleted', 'orphan', 'pending_deletion')", name=op.f('ck_document_artifact_lifecycle_state')),
    sa.ForeignKeyConstraint(['document_version_id'], ['document_version.id'], name=op.f('fk_document_artifact_document_version_id_document_version'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_document_artifact_organization_id_organization'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_artifact'))
    )
    op.create_index('ix_document_artifact_type', 'document_artifact', ['artifact_type'], unique=False)
    op.create_index('ix_document_artifact_version_id', 'document_artifact', ['document_version_id'], unique=False)
    op.create_table('document_processing_result',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('document_version_id', sa.UUID(), nullable=False),
    sa.Column('schema_version', sa.String(length=64), nullable=True),
    sa.Column('provider', sa.String(length=64), nullable=True),
    sa.Column('provider_version', sa.String(length=64), nullable=True),
    sa.Column('ocr_engine', sa.String(length=64), nullable=True),
    sa.Column('ocr_engine_version', sa.String(length=64), nullable=True),
    sa.Column('do_ocr', sa.Boolean(), nullable=False),
    sa.Column('do_table_structure', sa.Boolean(), nullable=False),
    sa.Column('dpi', sa.Integer(), nullable=True),
    sa.Column('geometry_provider', sa.String(length=64), nullable=True),
    sa.Column('processing_duration', sa.Float(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('canonical_artifact_id', sa.UUID(), nullable=True),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('failed', 'partial', 'running', 'succeeded')", name=op.f('ck_document_processing_result_status')),
    sa.ForeignKeyConstraint(['canonical_artifact_id'], ['document_artifact.id'], name=op.f('fk_result_canonical_artifact_id_docartifact'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['document_version_id'], ['document_version.id'], name=op.f('fk_result_document_version_id_docversion'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_document_processing_result_organization_id_organization'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_processing_result'))
    )
    op.create_index('ix_document_processing_result_version_id', 'document_processing_result', ['document_version_id'], unique=False)
    # Zirkulärer FK: erst nachdem beide Tabellen existieren.
    op.create_foreign_key(
        'fk_artifact_processing_run_id_result',
        'document_artifact', 'document_processing_result',
        ['processing_run_id'], ['id'], ondelete='SET NULL',
    )
    op.create_table('contract_extraction',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('document_version_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('validation_status', sa.String(length=16), nullable=False),
    sa.Column('requires_review', sa.Boolean(), nullable=False),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('model', sa.String(length=120), nullable=True),
    sa.Column('prompt_version', sa.String(length=64), nullable=True),
    sa.Column('chunk_count', sa.Integer(), nullable=True),
    sa.Column('processing_duration', sa.Numeric(precision=12, scale=4), nullable=True),
    sa.Column('timeout_count', sa.Integer(), nullable=True),
    sa.Column('retry_count', sa.Integer(), nullable=True),
    sa.Column('truncated_chunks', sa.Integer(), nullable=True),
    sa.Column('ai_call_count', sa.Integer(), nullable=True),
    sa.Column('groups_processed', sa.Integer(), nullable=True),
    sa.Column('evidence_issues', sa.Integer(), nullable=True),
    sa.Column('verifier_issues', sa.Integer(), nullable=True),
    sa.Column('normalization_issues', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('contract_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('contract_snapshot_artifact_id', sa.UUID(), nullable=True),
    sa.Column('snapshot_sha256', sa.String(length=64), nullable=True),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('failed', 'partial', 'success')", name=op.f('ck_contract_extraction_status')),
    sa.CheckConstraint("validation_status IN ('invalid', 'unknown', 'valid')", name=op.f('ck_contract_extraction_validation_status')),
    sa.ForeignKeyConstraint(['contract_snapshot_artifact_id'], ['document_artifact.id'], name=op.f('fk_extraction_snapshot_artifact_id_docartifact'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['document_version_id'], ['document_version.id'], name=op.f('fk_contract_extraction_document_version_id_document_version'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_contract_extraction_organization_id_organization'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_contract_extraction'))
    )
    op.create_index('ix_contract_extraction_version_id', 'contract_extraction', ['document_version_id'], unique=False)
    op.create_table('processing_summary',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('document_version_id', sa.UUID(), nullable=False),
    sa.Column('file_key', sa.Text(), nullable=False),
    sa.Column('page_count', sa.Integer(), nullable=False),
    sa.Column('doc_type', sa.String(length=64), nullable=True),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('success_count', sa.Integer(), nullable=False),
    sa.Column('failure_count', sa.Integer(), nullable=False),
    sa.Column('last_success_run_id', sa.UUID(), nullable=True),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_version_id'], ['document_version.id'], name=op.f('fk_processing_summary_document_version_id_document_version'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['last_success_run_id'], ['document_processing_result.id'], name=op.f('fk_summary_last_success_run_id_docresult'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_processing_summary_organization_id_organization'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_processing_summary')),
    sa.UniqueConstraint('document_version_id', name=op.f('uq_processing_summary_document_version_id'))
    )
    op.create_table('calculation_run',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('extraction_id', sa.UUID(), nullable=False),
    sa.Column('as_of_date', sa.Date(), nullable=False),
    sa.Column('calculation_version', sa.String(length=64), nullable=True),
    sa.Column('overall_review_required', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('result_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('computed', 'failed', 'partial')", name=op.f('ck_calculation_run_status')),
    sa.ForeignKeyConstraint(['extraction_id'], ['contract_extraction.id'], name=op.f('fk_calculation_run_extraction_id_contract_extraction'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_calculation_run_organization_id_organization'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_calculation_run'))
    )
    op.create_index('ix_calculation_run_extraction_date', 'calculation_run', ['extraction_id', 'as_of_date'], unique=False)
    op.create_table('extraction_evidence',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('extraction_id', sa.UUID(), nullable=False),
    sa.Column('field_ref', sa.String(length=120), nullable=False),
    sa.Column('source_type', sa.String(length=16), nullable=False),
    sa.Column('page', sa.Integer(), nullable=False),
    sa.Column('paragraph_index', sa.Integer(), nullable=True),
    sa.Column('table_index', sa.Integer(), nullable=True),
    sa.Column('source_text', sa.Text(), nullable=True),
    sa.Column('bounding_box', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('ocr_confidence', sa.Numeric(precision=5, scale=4), nullable=True),
    sa.Column('confidence', sa.Numeric(precision=5, scale=4), nullable=True),
    sa.Column('requires_review', sa.Boolean(), nullable=False),
    sa.Column('extraction_method', sa.String(length=16), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("extraction_method IN ('ai', 'manual', 'programmatic')", name=op.f('ck_extraction_evidence_method')),
    sa.CheckConstraint("source_type IN ('page', 'paragraph', 'table')", name=op.f('ck_extraction_evidence_source_type')),
    sa.CheckConstraint('confidence IS NULL OR (confidence >= 0 AND confidence <= 1)', name=op.f('ck_extraction_evidence_confidence_range')),
    sa.CheckConstraint('ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)', name=op.f('ck_extraction_evidence_ocr_confidence_range')),
    sa.CheckConstraint('page > 0', name=op.f('ck_extraction_evidence_page_positive')),
    sa.ForeignKeyConstraint(['extraction_id'], ['contract_extraction.id'], name=op.f('fk_extraction_evidence_extraction_id_contract_extraction'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_extraction_evidence_organization_id_organization'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_extraction_evidence')),
    sa.UniqueConstraint('extraction_id', 'field_ref', 'paragraph_index', 'table_index', name='uq_extraction_evidence_source')
    )
    op.create_index('ix_extraction_evidence_extraction_id', 'extraction_evidence', ['extraction_id'], unique=False)
    op.create_index('ix_extraction_evidence_field_ref', 'extraction_evidence', ['field_ref'], unique=False)
    op.create_index('ix_extraction_evidence_page', 'extraction_evidence', ['page'], unique=False)
    op.create_table('calculation_result',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('field_key', sa.String(length=120), nullable=False),
    sa.Column('status', sa.String(length=24), nullable=True),
    sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=True),
    sa.Column('value', sa.String(length=255), nullable=True),
    sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_calculation_result_organization_id_organization'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['run_id'], ['calculation_run.id'], name=op.f('fk_calculation_result_run_id_calculation_run'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_calculation_result'))
    )
    op.create_index('ix_calculation_result_run_id', 'calculation_result', ['run_id'], unique=False)
    op.create_table('calculation_review_flag',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('calculation_run_id', sa.UUID(), nullable=False),
    sa.Column('flag_key', sa.String(length=120), nullable=False),
    sa.Column('severity', sa.String(length=16), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.Column('inputs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("severity IN ('critical', 'info', 'warning')", name=op.f('ck_calculation_review_flag_severity')),
    sa.ForeignKeyConstraint(['calculation_run_id'], ['calculation_run.id'], name=op.f('fk_calculation_review_flag_calculation_run_id_calculation_run'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_calculation_review_flag_organization_id_organization'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_calculation_review_flag'))
    )
    op.create_index('ix_calculation_review_flag_run_id', 'calculation_review_flag', ['calculation_run_id'], unique=False)
    op.create_table('contract',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('accepted_extraction_id', sa.UUID(), nullable=True),
    sa.Column('accepted_calculation_run_id', sa.UUID(), nullable=True),
    sa.Column('supplier', sa.String(length=255), nullable=True),
    sa.Column('contract_number', sa.String(length=120), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=24), nullable=True),
    sa.Column('risk_level', sa.String(length=24), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('lifecycle_state', sa.String(length=24), nullable=False),
    sa.Column('deletion_owner', sa.String(length=120), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("lifecycle_state IN ('active', 'deleted', 'orphan', 'pending_deletion')", name=op.f('ck_contract_lifecycle_state')),
    sa.ForeignKeyConstraint(['accepted_calculation_run_id'], ['calculation_run.id'], name=op.f('fk_contract_accepted_calculation_run_id_calculation_run'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['accepted_extraction_id'], ['contract_extraction.id'], name=op.f('fk_contract_accepted_extraction_id_contract_extraction'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_contract_organization_id_organization'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_contract'))
    )
    op.create_index('ix_contract_accepted_extraction_id', 'contract', ['accepted_extraction_id'], unique=False)
    op.create_index('ix_contract_risk_level', 'contract', ['risk_level'], unique=False)
    op.create_index('ix_contract_status', 'contract', ['status'], unique=False)
    op.create_table('contract_document',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('contract_id', sa.UUID(), nullable=False),
    sa.Column('document_version_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=32), nullable=True),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IS NULL OR role IN ('amendment', 'appendix', 'main', 'price_adjustment', 'renewal_letter', 'sla_attachment', 'unknown')", name=op.f('ck_contract_document_role')),
    sa.ForeignKeyConstraint(['contract_id'], ['contract.id'], name=op.f('fk_contract_document_contract_id_contract'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_version_id'], ['document_version.id'], name=op.f('fk_contract_document_document_version_id_document_version'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_contract_document_organization_id_organization'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_contract_document')),
    sa.UniqueConstraint('contract_id', 'document_version_id', name='uq_contract_document_pair')
    )
    op.create_index('ix_contract_document_contract_id', 'contract_document', ['contract_id'], unique=False)
    op.create_index('ix_contract_document_version_id', 'contract_document', ['document_version_id'], unique=False)
    op.create_table('contract_equipment',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('contract_id', sa.UUID(), nullable=False),
    sa.Column('device_name', sa.String(length=255), nullable=True),
    sa.Column('manufacturer', sa.String(length=120), nullable=True),
    sa.Column('model', sa.String(length=120), nullable=True),
    sa.Column('serial_number', sa.String(length=120), nullable=True),
    sa.Column('system_name', sa.String(length=120), nullable=True),
    sa.Column('equipment_category', sa.String(length=64), nullable=True),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['contract_id'], ['contract.id'], name=op.f('fk_contract_equipment_contract_id_contract'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_contract_equipment_organization_id_organization'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_contract_equipment'))
    )
    op.create_index('ix_contract_equipment_contract_id', 'contract_equipment', ['contract_id'], unique=False)
    op.create_table('review_action',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('contract_id', sa.UUID(), nullable=False),
    sa.Column('extraction_id', sa.UUID(), nullable=False),
    sa.Column('field_ref', sa.String(length=120), nullable=False),
    sa.Column('status', sa.String(length=24), nullable=False),
    sa.Column('old_value', sa.String(length=1024), nullable=True),
    sa.Column('new_value', sa.String(length=1024), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('evidence_id', sa.UUID(), nullable=True),
    sa.Column('reviewer', sa.String(length=120), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('approved', 'needs_review', 'rejected')", name=op.f('ck_review_action_status')),
    sa.ForeignKeyConstraint(['contract_id'], ['contract.id'], name=op.f('fk_review_action_contract_id_contract'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['evidence_id'], ['extraction_evidence.id'], name=op.f('fk_review_action_evidence_id_extraction_evidence'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['extraction_id'], ['contract_extraction.id'], name=op.f('fk_review_action_extraction_id_contract_extraction'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_review_action_organization_id_organization'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_review_action'))
    )
    op.create_index('ix_review_action_contract_id', 'review_action', ['contract_id'], unique=False)
    op.create_index('ix_review_action_extraction_id', 'review_action', ['extraction_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_review_action_extraction_id', table_name='review_action')
    op.drop_index('ix_review_action_contract_id', table_name='review_action')
    op.drop_table('review_action')
    op.drop_index('ix_contract_equipment_contract_id', table_name='contract_equipment')
    op.drop_table('contract_equipment')
    op.drop_index('ix_contract_document_version_id', table_name='contract_document')
    op.drop_index('ix_contract_document_contract_id', table_name='contract_document')
    op.drop_table('contract_document')
    op.drop_index('ix_contract_status', table_name='contract')
    op.drop_index('ix_contract_risk_level', table_name='contract')
    op.drop_index('ix_contract_accepted_extraction_id', table_name='contract')
    op.drop_table('contract')
    op.drop_index('ix_calculation_review_flag_run_id', table_name='calculation_review_flag')
    op.drop_table('calculation_review_flag')
    op.drop_index('ix_calculation_result_run_id', table_name='calculation_result')
    op.drop_table('calculation_result')
    op.drop_index('ix_extraction_evidence_page', table_name='extraction_evidence')
    op.drop_index('ix_extraction_evidence_field_ref', table_name='extraction_evidence')
    op.drop_index('ix_extraction_evidence_extraction_id', table_name='extraction_evidence')
    op.drop_table('extraction_evidence')
    op.drop_index('ix_calculation_run_extraction_date', table_name='calculation_run')
    op.drop_table('calculation_run')
    op.drop_table('processing_summary')
    op.drop_index('ix_contract_extraction_version_id', table_name='contract_extraction')
    op.drop_table('contract_extraction')
    # Alter zuerst den zirkulären FK, dann die Tabelle.
    op.drop_constraint('fk_artifact_processing_run_id_result', 'document_artifact', type_='foreignkey')
    op.drop_index('ix_document_processing_result_version_id', table_name='document_processing_result')
    op.drop_table('document_processing_result')
    op.drop_index('ix_document_artifact_version_id', table_name='document_artifact')
    op.drop_index('ix_document_artifact_type', table_name='document_artifact')
    op.drop_table('document_artifact')
    op.drop_index('ix_document_version_document_file_id', table_name='document_version')
    op.drop_table('document_version')
    op.drop_index('ix_document_file_imported_at', table_name='document_file')
    op.drop_table('document_file')
    op.drop_table('organization')
