"""add conversation knowledge scope items

Revision ID: 9b1c2d3e4f50
Revises: 516fb5f3589f
Create Date: 2026-05-13 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b1c2d3e4f50"
down_revision: Union[str, Sequence[str], None] = "516fb5f3589f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_knowledge_scope_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=True),
        sa.Column(
            "knowledge_base_name_snapshot", sa.String(length=255), nullable=False
        ),
        sa.Column("source_url_snapshot", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("route_score", sa.Float(), nullable=True),
        sa.Column("route_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"], ["knowledge_bases.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "knowledge_base_id",
            name="uq_conversation_scope_conversation_knowledge_base",
        ),
    )
    op.create_index(
        op.f("ix_conversation_knowledge_scope_items_id"),
        "conversation_knowledge_scope_items",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_knowledge_scope_items_conversation_id"),
        "conversation_knowledge_scope_items",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_knowledge_scope_items_knowledge_base_id"),
        "conversation_knowledge_scope_items",
        ["knowledge_base_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_conversation_knowledge_scope_items_knowledge_base_id"),
        table_name="conversation_knowledge_scope_items",
    )
    op.drop_index(
        op.f("ix_conversation_knowledge_scope_items_conversation_id"),
        table_name="conversation_knowledge_scope_items",
    )
    op.drop_index(
        op.f("ix_conversation_knowledge_scope_items_id"),
        table_name="conversation_knowledge_scope_items",
    )
    op.drop_table("conversation_knowledge_scope_items")
