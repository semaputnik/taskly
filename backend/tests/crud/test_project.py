from sqlmodel import Session, select

from app import crud
from app.models import Project, ProjectCreate, ProjectUpdate, UserCreate
from tests.utils.utils import random_email, random_lower_string


def test_create_user_creates_inbox_project(db: Session) -> None:
    user_in = UserCreate(email=random_email(), password=random_lower_string())
    user = crud.create_user(session=db, user_create=user_in)

    statement = select(Project).where(Project.owner_id == user.id)
    projects = db.exec(statement).all()

    assert len(projects) == 1
    assert projects[0].name == "Inbox"
    assert projects[0].is_inbox is True


def test_create_project(db: Session) -> None:
    user_in = UserCreate(email=random_email(), password=random_lower_string())
    user = crud.create_user(session=db, user_create=user_in)

    project_in = ProjectCreate(name="Groceries", description="Weekly shopping list")
    project = crud.create_project(
        session=db, project_create=project_in, owner_id=user.id
    )

    assert project.name == "Groceries"
    assert project.description == "Weekly shopping list"
    assert project.owner_id == user.id
    assert project.is_inbox is False


def test_update_project(db: Session) -> None:
    user_in = UserCreate(email=random_email(), password=random_lower_string())
    user = crud.create_user(session=db, user_create=user_in)
    project = crud.create_project(
        session=db, project_create=ProjectCreate(name="Old name"), owner_id=user.id
    )

    project_in = ProjectUpdate(name="New name", description="New description")
    updated = crud.update_project(session=db, db_project=project, project_in=project_in)

    assert updated.name == "New name"
    assert updated.description == "New description"
