"""merge JAMAL STEP18/auth branch with Ahmad multi-org/account branch

Revision ID: i8d9e0f1a2b3
Revises: d7e1f2a5b3c6, h7c8d9e0f1a2
Create Date: 2026-09-13
"""

from alembic import op

revision = "i8d9e0f1a2b3"
down_revision = ("d7e1f2a5b3c6", "h7c8d9e0f1a2")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The integrated product supports both JAMAL app_user identities and Ahmad
    # account identities. These UUID provenance columns therefore cannot retain
    # a foreign key to only one of the two identity stores. The identity type,
    # display-name snapshot and role snapshot keep provenance explicit.
    op.drop_constraint(
        "fk_fact_review_authenticated_actor_id_app_user",
        "fact_review",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_contract_review_authenticated_actor_id_app_user",
        "contract_review",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_contract_override_actor_id_app_user",
        "contract_override",
        type_="foreignkey",
    )


def downgrade() -> None:
    # Downgrade is only valid after account-based provenance has been removed or
    # migrated back to app_user UUIDs.
    op.create_foreign_key(
        "fk_fact_review_authenticated_actor_id_app_user",
        "fact_review",
        "app_user",
        ["authenticated_actor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_contract_review_authenticated_actor_id_app_user",
        "contract_review",
        "app_user",
        ["authenticated_actor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_contract_override_actor_id_app_user",
        "contract_override",
        "app_user",
        ["actor_id"],
        ["id"],
        ondelete="SET NULL",
    )
