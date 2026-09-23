"""Persist safe message + sanitized error on processing runs.

Revision ID: 7f2c9a1e4b80
Revises: c4a1d85ef762
Create Date: 2026-09-02
"""

from typing import Sequence, Union

from alembic import op


revision: str = "7f2c9a1e4b80"
down_revision: Union[str, None] = "c4a1d85ef762"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_processing_result",
        __import__("sqlalchemy").Column("message", __import__("sqlalchemy").Text(), nullable=True),
    )
    op.add_column(
        "document_processing_result",
        __import__("sqlalchemy").Column("error", __import__("sqlalchemy").Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_processing_result", "error")
    op.drop_column("document_processing_result", "message")
