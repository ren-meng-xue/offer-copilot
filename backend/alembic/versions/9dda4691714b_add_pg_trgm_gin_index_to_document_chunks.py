"""add_pg_trgm_gin_index_to_document_chunks

Revision ID: 9dda4691714b
Revises: d857815be3b3
Create Date: 2026-05-28 16:18:46.903154

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9dda4691714b'
down_revision: Union[str, Sequence[str], None] = 'd857815be3b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_chunks_content_trgm "
        "ON document_chunks USING gin (content gin_trgm_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_content_trgm")
