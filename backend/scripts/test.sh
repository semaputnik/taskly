#!/usr/bin/env bash

set -e
set -x

# Run against a separate test database: the test session deletes all users when it
# finishes. Environment variables take priority over .env in pydantic-settings,
# so exporting DATABASE_URL redirects the app engine and Alembic together.
#
# `set -e` does not catch a failure inside a command substitution used in an
# assignment (`VAR="$(cmd)"` "succeeds" even when cmd fails), and pydantic-settings'
# env_ignore_empty means an empty DATABASE_URL is silently ignored in favor of
# .env's — the development database. Without the check below, a broken or empty
# computation here would run the whole suite, teardown included, against the
# database this repo actually uses for real work.
read -r DATABASE_URL TEST_DB_NAME <<EOF
$(FASTAPI_ENV=development python -c '
from sqlalchemy.engine import make_url
from app.core.config import settings
url = make_url(str(settings.DATABASE_URL)).set(database=settings.TEST_DB_NAME)
print(url.render_as_string(hide_password=False), settings.TEST_DB_NAME)
')
EOF
case "$DATABASE_URL" in
  */"$TEST_DB_NAME")
    ;;
  *)
    echo "Refusing to run tests: DATABASE_URL did not resolve to the test database ('$TEST_DB_NAME')." >&2
    echo "Got: '${DATABASE_URL:-<empty>}'" >&2
    exit 1
    ;;
esac
export DATABASE_URL
python scripts/create_test_db.py
alembic upgrade head

FASTAPI_ENV=development coverage run -m pytest tests/
coverage report
coverage html --title "${@-coverage}"
