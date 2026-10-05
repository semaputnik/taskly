from sqlmodel import create_engine

from app.core.config import settings

engine = create_engine(str(settings.DATABASE_URL), pool_pre_ping=True)


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28

# Tables should be created with Alembic migrations
# But if you don't want to use migrations, create
# the tables un-commenting the next lines
# from sqlmodel import SQLModel

# This works because the models are already imported and registered from app.models
# SQLModel.metadata.create_all(engine)

# Nothing is seeded: the first superuser is whoever registers the address
# FIRST_SUPERUSER names while there is none (FR-09.6).
