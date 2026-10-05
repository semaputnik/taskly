#! /usr/bin/env bash

set -e
set -x

# Run migrations. Nothing is seeded: the first superuser registers like anyone
# else, with the address FIRST_SUPERUSER names (FR-09.6).
alembic upgrade head
