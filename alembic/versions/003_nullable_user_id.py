"""Make user_id nullable in auth tables

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # user_id was NOT NULL in the old schema but is now optional for tenant-based auth
    op.alter_column('refresh_tokens', 'user_id', nullable=True)
    op.alter_column('sessions', 'user_id', nullable=True)
    op.alter_column('users', 'tenant_id', nullable=True)


def downgrade() -> None:
    op.alter_column('users', 'tenant_id', nullable=False)
    op.alter_column('sessions', 'user_id', nullable=False)
    op.alter_column('refresh_tokens', 'user_id', nullable=False)