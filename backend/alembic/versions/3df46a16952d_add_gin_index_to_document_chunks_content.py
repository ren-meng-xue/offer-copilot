"""add_gin_index_to_document_chunks_content

Revision ID: 3df46a16952d
Revises: 95f879bb63ba
Create Date: 2026-05-27 13:40:24.891968

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3df46a16952d'
down_revision: Union[str, Sequence[str], None] = '95f879bb63ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 确保 pg_trgm 扩展已启用（通常应该已经在之前的迁移中开启，这里做幂等保护）
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # 为 document_chunks 的 content 字段创建 GIN 索引，加速全模糊匹配/全文检索
    op.create_index(
        "ix_document_chunks_content_gin",
        "document_chunks",
        ["content"],
        postgresql_using="gin",
        postgresql_ops={"content": "gin_trgm_ops"},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_document_chunks_content_gin", table_name="document_chunks")
