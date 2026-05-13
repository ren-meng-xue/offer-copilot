"""enforce username required

Revision ID: 516fb5f3589f
Revises: c1f1a9af32dd
Create Date: 2026-05-13 16:40:04.309354

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '516fb5f3589f'
down_revision: Union[str, Sequence[str], None] = 'c1f1a9af32dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("users", "username", existing_type=sa.String(length=50), nullable=False)
    op.create_check_constraint(
        "ck_users_username_not_blank",
        "users",
        "length(trim(username)) > 0",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_users_username_not_blank", "users", type_="check")
