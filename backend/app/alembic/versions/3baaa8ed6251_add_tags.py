"""Add tags

Revision ID: 3baaa8ed6251
Revises: 45f76d0e533c
Create Date: 2026-09-12 19:41:08.827411

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3baaa8ed6251'
down_revision = '45f76d0e533c'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tag',
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], name='tag_owner_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='tag_pkey'),
        # A tag belongs to its user, so two users can use the same name without
        # meeting each other (FR-01.21).
        sa.UniqueConstraint('owner_id', 'name', name='tag_owner_id_name_key'),
    )
    op.create_table(
        'tasktag',
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tag_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['task.id'], name='tasktag_task_id_fkey', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tag.id'], name='tasktag_tag_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('task_id', 'tag_id', name='tasktag_pkey'),
    )


def downgrade():
    op.drop_table('tasktag')
    op.drop_table('tag')
