#!/usr/bin/env bash

set -e
set -x

# Run against a separate test database: the test session deletes all users when it
# finishes. Environment variables take priority over .env in pydantic-settings,
# so exporting DATABASE_URL redirects the app engine and Alembic together.
DATABASE_URL="$(FASTAPI_ENV=development python -c '
from sqlalchemy.engine import make_url
from app.core.config import settings
url = make_url(str(settings.DATABASE_URL)).set(database=settings.TEST_DB_NAME)
print(url.render_as_string(hide_password=False))
')"
export DATABASE_URL
python scripts/create_test_db.py
alembic upgrade head

FASTAPI_ENV=development coverage run -m pytest tests/
coverage report
coverage html --title "${@-coverage}"
