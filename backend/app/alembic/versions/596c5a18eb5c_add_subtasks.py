"""Add subtasks

Revision ID: 596c5a18eb5c
Revises: 466dd50894a5
Create Date: 2026-09-12 15:43:27.426762

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '596c5a18eb5c'
down_revision = '466dd50894a5'
branch_labels = None
depends_on = None

# A subtask stores no project: it derives one from its root ancestor, so the
# project is only ever recorded on the task at the top of a tree.
ROOT_HAS_PROJECT = '(parent_id IS NULL) <> (project_id IS NULL)'

BACKFILL_PROJECT_FROM_ROOT = """
WITH RECURSIVE tree AS (
    SELECT id, project_id FROM task WHERE parent_id IS NULL
    UNION ALL
    SELECT task.id, tree.project_id
    FROM task JOIN tree ON task.parent_id = tree.id
)
UPDATE task SET project_id = tree.project_id
FROM tree
WHERE task.id = tree.id AND task.project_id IS NULL
"""


def upgrade():
    op.add_column('task', sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('task_parent_id_fkey', 'task', 'task', ['parent_id'], ['id'], ondelete='CASCADE')
    op.create_index(op.f('ix_task_parent_id'), 'task', ['parent_id'])
    op.alter_column('task', 'project_id', existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.create_check_constraint('task_root_has_project', 'task', ROOT_HAS_PROJECT)


def downgrade():
    op.drop_constraint('task_root_has_project', 'task', type_='check')
    # Subtasks survive the downgrade as plain tasks, each keeping the project
    # it resolved to.
    op.execute(BACKFILL_PROJECT_FROM_ROOT)
    op.alter_column('task', 'project_id', existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.drop_index(op.f('ix_task_parent_id'), table_name='task')
    op.drop_constraint('task_parent_id_fkey', 'task', type_='foreignkey')
    op.drop_column('task', 'parent_id')
