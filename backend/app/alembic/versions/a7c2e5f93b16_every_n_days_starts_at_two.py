"""Start every N days at two days

Revision ID: a7c2e5f93b16
Revises: d5b3e7c21f84
Create Date: 2026-09-16 15:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a7c2e5f93b16'
down_revision = 'd5b3e7c21f84'
branch_labels = None
depends_on = None


def upgrade():
    # Every one day is the daily rule spelt a second way. A series written that
    # way keeps its schedule exactly under its one spelling, and has to move
    # before the check below can hold — the API could not read it back either.
    op.execute(
        "UPDATE series SET frequency = 'daily', interval_days = NULL "
        "WHERE frequency = 'every_n_days' AND interval_days < 2"
    )
    op.create_check_constraint(
        'series_interval_days_minimum',
        'series',
        'interval_days >= 2',
    )


def downgrade():
    # A series moved to daily is the same schedule, so nothing moves back.
    op.drop_constraint('series_interval_days_minimum', 'series', type_='check')
