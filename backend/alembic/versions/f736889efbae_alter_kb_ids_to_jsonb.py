"""alter_kb_ids_to_jsonb

Revision ID: f736889efbae
Revises: 3df46a16952d
Create Date: 2026-05-27 17:27:51.045263

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f736889efbae"
down_revision: Union[str, Sequence[str], None] = "3df46a16952d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 显式使用 USING 子句进行类型转换，并创建 GIN 索引以加速包含查询
    op.alter_column(
        "semantic_query_caches",
        "knowledge_base_ids",
        existing_type=sa.JSON(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
        postgresql_using="knowledge_base_ids::jsonb",
    )
    op.create_index(
        "ix_semantic_caches_kb_ids_gin",
        "semantic_query_caches",
        ["knowledge_base_ids"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_semantic_caches_kb_ids_gin", table_name="semantic_query_caches")
    op.alter_column(
        "semantic_query_caches",
        "knowledge_base_ids",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using="knowledge_base_ids::json",
    )
