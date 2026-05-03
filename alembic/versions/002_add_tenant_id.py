"""Add tenant_id to auth tables for multi-tenant support

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add tenant_id to users table
    op.add_column('users', sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=True))
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])

    # Add tenant_id to sessions table (nullable, optional)
    op.add_column('sessions', sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=True))
    op.create_index('ix_sessions_tenant_id', 'sessions', ['tenant_id'])

    # Add tenant_id to refresh_tokens table (nullable, optional)
    op.add_column('refresh_tokens', sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=True))
    op.create_index('ix_refresh_tokens_tenant_id', 'refresh_tokens', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_refresh_tokens_tenant_id', 'refresh_tokens')
    op.drop_column('refresh_tokens', 'tenant_id')
    op.drop_index('ix_sessions_tenant_id', 'sessions')
    op.drop_column('sessions', 'tenant_id')
    op.drop_index('ix_users_tenant_id', 'users')
    op.drop_column('users', 'tenant_id')