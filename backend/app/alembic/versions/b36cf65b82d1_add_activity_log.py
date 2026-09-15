"""Add activity log

Revision ID: b36cf65b82d1
Revises: 8b31a6e07580
Create Date: 2026-09-15 16:35:23.148703

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b36cf65b82d1'
down_revision = '8b31a6e07580'
branch_labels = None
depends_on = None


def upgrade():
    # Starts empty: changes made before the log existed were never recorded,
    # and there is nothing to reconstruct them from.
    op.create_table(
        'activityentry',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('position', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('entity_type', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('deletion_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], name='activityentry_owner_id_fkey', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actor_id'], ['user.id'], name='activityentry_actor_id_fkey', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['deletion_id'], ['deletion.id'], name='activityentry_deletion_id_fkey', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='activityentry_pkey'),
    )
    op.create_index('ix_activityentry_owner_id_position', 'activityentry', ['owner_id', 'position'])


def downgrade():
    op.drop_index('ix_activityentry_owner_id_position', table_name='activityentry')
    op.drop_table('activityentry')
