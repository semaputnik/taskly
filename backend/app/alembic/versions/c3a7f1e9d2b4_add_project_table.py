"""Add project table

Revision ID: c3a7f1e9d2b4
Revises: b8f2c1d94a37
Create Date: 2026-09-12 10:00:00.000000

"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c3a7f1e9d2b4'
down_revision = 'b8f2c1d94a37'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'project',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('is_inbox', sa.Boolean(), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], name='project_owner_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='project_pkey'),
    )

    # Backfill every existing account with the Inbox project it would have
    # received on registration, so no account is left without one.
    conn = op.get_bind()
    user_table = sa.table('user', sa.column('id', postgresql.UUID(as_uuid=True)))
    project_table = sa.table(
        'project',
        sa.column('id', postgresql.UUID(as_uuid=True)),
        sa.column('name', sa.String),
        sa.column('description', sa.String),
        sa.column('is_inbox', sa.Boolean),
        sa.column('owner_id', postgresql.UUID(as_uuid=True)),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    user_ids = conn.execute(sa.select(user_table.c.id)).scalars().all()
    now = datetime.now(UTC)
    rows = [
        {
            'id': uuid.uuid4(),
            'name': 'Inbox',
            'description': None,
            'is_inbox': True,
            'owner_id': user_id,
            'created_at': now,
        }
        for user_id in user_ids
    ]
    if rows:
        op.bulk_insert(project_table, rows)


def downgrade():
    op.drop_table('project')
