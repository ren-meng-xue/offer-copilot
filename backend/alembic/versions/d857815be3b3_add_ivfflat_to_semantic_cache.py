"""add_ivfflat_to_semantic_cache

Revision ID: d857815be3b3
Revises: f736889efbae
Create Date: 2026-05-27 17:46:05.179905
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d857815be3b3"
down_revision: Union[str, Sequence[str], None] = "f736889efbae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_semantic_caches_query_vector "
        "ON semantic_query_caches USING ivfflat (query_vector vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_semantic_caches_query_vector")
