"""Remember dismissed groups of duplicate tags

Revision ID: b4e8d1c7a352
Revises: a7c2e5f93b16
Create Date: 2026-09-16 17:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b4e8d1c7a352'
down_revision = 'a7c2e5f93b16'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tagduplicatedismissal',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('signature', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'owner_id', 'signature', name='tagduplicatedismissal_owner_signature_key'
        ),
    )


def downgrade():
    # Dismissals are only suggestions withheld; dropping them offers the groups
    # again and loses nothing else.
    op.drop_table('tagduplicatedismissal')
