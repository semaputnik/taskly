"""Add comments

Revision ID: d1f6d21ccfb0
Revises: 3baaa8ed6251
Create Date: 2026-09-13 00:00:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd1f6d21ccfb0'
down_revision = '3baaa8ed6251'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'comment',
        sa.Column('body', sqlmodel.sql.sqltypes.AutoString(length=10000), nullable=False),
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['task.id'], name='comment_task_id_fkey', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], name='comment_owner_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='comment_pkey'),
    )
    op.create_index(op.f('ix_comment_task_id'), 'comment', ['task_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_comment_task_id'), table_name='comment')
    op.drop_table('comment')
