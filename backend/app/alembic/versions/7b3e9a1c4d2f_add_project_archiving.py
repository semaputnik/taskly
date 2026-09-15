"""Add project archiving

Revision ID: 7b3e9a1c4d2f
Revises: 90f55891a218
Create Date: 2026-09-15 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '7b3e9a1c4d2f'
down_revision = '90f55891a218'
branch_labels = None
depends_on = None


def upgrade():
    # Every project that already exists is live. The server default only
    # backfills those rows; the application always writes the value itself,
    # so the column ends up matching the model, which has none.
    op.add_column(
        'project',
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('project', 'is_archived', server_default=None)


def downgrade():
    op.drop_column('project', 'is_archived')
