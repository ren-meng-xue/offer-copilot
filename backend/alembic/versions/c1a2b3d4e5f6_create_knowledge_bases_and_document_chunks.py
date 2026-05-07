"""create knowledge_bases and document_chunks

Revision ID: c1a2b3d4e5f6
Revises: 7e4ae1ff1391
Create Date: 2026-05-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "7e4ae1ff1391"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `op` 是 Alembic 提供的操作入口（operations）。
    # 建表、删表、执行原生 SQL 等迁移动作，都通过 `op` 发给数据库。
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # knowledge_bases: 知识库主表。
    # 一条记录代表一个待处理或已完成的知识库，例如一个文档 URL 或一份 PDF。
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        # 预留给多用户隔离；当前阶段允许为空，表示还未强制绑定用户。
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        # 知识库展示名称。
        sa.Column("name", sa.String(255), nullable=False),
        # 数据来源类型，当前默认是 URL，后续也可以扩展为 pdf 等。
        sa.Column("source_type", sa.String(50), nullable=False, server_default="url"),
        # 原始数据来源地址，用于回溯和展示。
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "done", "failed", name="knowledgebasestatus"),
            nullable=False,
            server_default="pending",
        ),
        # 异步处理失败时记录原因，便于前端展示和排查。
        sa.Column("error_message", sa.Text(), nullable=True),
        # 创建时间。
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # 更新时间。
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # document_chunks: 文档分块表。
    # 每一条记录代表一个可检索的 chunk，既保存原文，也保存 embedding。
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        # 外键指向所属知识库；知识库删除时，相关 chunk 一并级联删除。
        sa.Column("knowledge_base_id", sa.Integer(), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True),
        # chunk 原文内容，供检索命中后直接喂给 LLM。
        sa.Column("content", sa.Text(), nullable=False),
        # 向量列，1536 对应 text-embedding-3-small 的输出维度。
        sa.Column("embedding", Vector(1536), nullable=False),
        # chunk 来源 URL，用于引用溯源。
        sa.Column("source_url", sa.Text(), nullable=False),
        # 标题层级路径，例如 "Getting Started > Install"。
        sa.Column("heading_path", sa.String(1024), nullable=True),
        # chunk 在同一文档内的顺序编号，便于定位和调试。
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        # 预留 token 数量，便于后续控制上下文拼接和成本。
        sa.Column("token_count", sa.Integer(), nullable=True),
        # 创建时间。
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # 更新时间。
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # ivfflat 是 pgvector 的近似最近邻索引。
    # 这里对 embedding 列建立基于余弦距离的向量索引，用于加速相似度检索。
    # `vector_cosine_ops` 表示按余弦距离计算相似度。
    # `lists=100` 可以理解为把向量粗分成 100 个簇，查询时先缩小候选范围再精排。
    # 之所以使用 op.execute 而不是 op.create_index，是因为 ivfflat / vector_cosine_ops
    # 属于 pgvector 扩展能力，直接写原生 SQL 更直观，也更贴近数据库真实执行语句。
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding ON document_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("knowledge_bases")
    op.execute("DROP TYPE IF EXISTS knowledgebasestatus")
