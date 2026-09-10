"""Create the database named in DATABASE_URL if it does not exist yet.

Used by scripts/test.sh to prepare the test database. It lives in scripts/ rather than
app/ on purpose: coverage measures app/ against a 90% threshold, and the test suite
never exercises this helper.
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main() -> None:
    url = make_url(os.environ["DATABASE_URL"])
    database = url.database
    # CREATE DATABASE cannot run inside a transaction, hence AUTOCOMMIT
    engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        exists = connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": database},
        )
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{database}"'))
    engine.dispose()


if __name__ == "__main__":
    main()
