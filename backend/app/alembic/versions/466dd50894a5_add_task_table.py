"""Add task table

Revision ID: 466dd50894a5
Revises: c3a7f1e9d2b4
Create Date: 2026-09-12 14:16:45.108593

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '466dd50894a5'
down_revision = 'c3a7f1e9d2b4'
branch_labels = None
depends_on = None

task_priority = postgresql.ENUM('P1', 'P2', 'P3', 'P4', name='taskpriority')


def upgrade():
    op.create_table(
        'task',
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=2000), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('priority', task_priority, nullable=True),
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('completed', sa.Boolean(), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assignee_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['assignee_id'], ['user.id'], name='task_assignee_id_fkey', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], name='task_owner_id_fkey', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], name='task_project_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='task_pkey'),
    )


def downgrade():
    op.drop_table('task')
    task_priority.drop(op.get_bind(), checkfirst=True)
