"""backfill unambiguous legacy ownership

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-09-12
"""

from alembic import op

revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        WITH single_hospital AS (
            SELECT organization_id, (array_agg(id))[1] AS hospital_id
            FROM hospital
            WHERE is_active = true
            GROUP BY organization_id
            HAVING count(*) = 1
        )
        UPDATE contract c
        SET hospital_id = sh.hospital_id,
            scope_type = CASE WHEN c.scope_type = 'organization' THEN 'hospital' ELSE c.scope_type END
        FROM single_hospital sh
        WHERE c.organization_id = sh.organization_id
          AND c.hospital_id IS NULL
    """)
    op.execute("""
        WITH single_hospital AS (
            SELECT organization_id, (array_agg(id))[1] AS hospital_id
            FROM hospital
            WHERE is_active = true
            GROUP BY organization_id
            HAVING count(*) = 1
        )
        UPDATE equipment e
        SET hospital_id = sh.hospital_id
        FROM single_hospital sh
        WHERE e.organization_id = sh.organization_id
          AND e.hospital_id IS NULL
    """)
    op.execute("""
        WITH single_department AS (
            SELECT hospital_id, (array_agg(id))[1] AS department_id
            FROM department
            WHERE is_active = true
            GROUP BY hospital_id
            HAVING count(*) = 1
        )
        UPDATE equipment e
        SET department_id = sd.department_id
        FROM single_department sd
        WHERE e.hospital_id = sd.hospital_id
          AND e.department_id IS NULL
    """)
    op.execute("""
        WITH single_department AS (
            SELECT hospital_id, (array_agg(id))[1] AS department_id
            FROM department
            WHERE is_active = true
            GROUP BY hospital_id
            HAVING count(*) = 1
        )
        INSERT INTO contract_department (organization_id, contract_id, department_id)
        SELECT c.organization_id, c.id, sd.department_id
        FROM contract c
        JOIN single_department sd ON sd.hospital_id = c.hospital_id
        WHERE NOT EXISTS (
            SELECT 1 FROM contract_department cd
            WHERE cd.contract_id = c.id AND cd.department_id = sd.department_id
        )
    """)
    op.execute("""
        UPDATE contract c
        SET scope_type = 'department'
        WHERE EXISTS (SELECT 1 FROM contract_department cd WHERE cd.contract_id = c.id)
    """)


def downgrade() -> None:
    # Data backfill is intentionally non-destructive and is not reversed.
    pass
