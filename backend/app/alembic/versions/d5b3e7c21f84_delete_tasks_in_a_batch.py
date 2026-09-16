"""Delete tasks in a batch

Revision ID: d5b3e7c21f84
Revises: c4f1b8d90a62
Create Date: 2026-09-16 13:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'd5b3e7c21f84'
down_revision = 'c4f1b8d90a62'
branch_labels = None
depends_on = None


def upgrade():
    # A deletion event names the one thing the user pointed at. A batch points
    # at a selection instead, so it names neither a task nor a project, and
    # the rows carrying the event are the whole of what went down with it.
    op.drop_constraint('deletion_targets_one_thing', 'deletion', type_='check')
    op.create_check_constraint(
        'deletion_targets_one_thing',
        'deletion',
        'NOT (task_id IS NOT NULL AND project_id IS NOT NULL)',
    )


def downgrade():
    # Batch deletions have nothing to name, so they cannot satisfy the old
    # constraint; they are restored first, which empties them of rows and
    # leaves the events themselves harmless to remove.
    op.execute(
        'UPDATE task SET deletion_id = NULL WHERE deletion_id IN '
        '(SELECT id FROM deletion WHERE task_id IS NULL AND project_id IS NULL)'
    )
    op.execute(
        'DELETE FROM deletion WHERE task_id IS NULL AND project_id IS NULL'
    )
    op.drop_constraint('deletion_targets_one_thing', 'deletion', type_='check')
    op.create_check_constraint(
        'deletion_targets_one_thing',
        'deletion',
        '(task_id IS NULL) <> (project_id IS NULL)',
    )
