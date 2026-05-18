"""add_pg_trgm_index

Revision ID: 0d308e6af591
Revises: 9b1c2d3e4f50
Create Date: 2026-05-17 20:47:27.604719

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d308e6af591'
down_revision: Union[str, Sequence[str], None] = '9b1c2d3e4f50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute(
        """
        CREATE INDEX ix_document_chunks_content_trgm
        ON document_chunks
        USING gin (content gin_trgm_ops);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_trgm;")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
