from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, select

from app import crud
from app.models import Project, User, UserCreate, UserUpdate
from tests.utils.utils import random_email, random_lower_string


def test_create_user(db: Session) -> None:
    email = random_email()
    user_in = UserCreate(email=email)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.email == email
    assert user.session_version == 0


def test_create_user_gets_an_inbox(db: Session) -> None:
    user = crud.create_user(session=db, user_create=UserCreate(email=random_email()))
    inbox = db.exec(
        select(Project).where(Project.owner_id == user.id, Project.is_inbox == True)  # noqa: E712
    ).first()
    assert inbox is not None


def test_create_user_without_committing_leaves_it_to_the_caller(db: Session) -> None:
    email = random_email()
    crud.create_user(session=db, user_create=UserCreate(email=email), commit=False)
    db.rollback()
    assert crud.get_user_by_email(session=db, email=email) is None


def test_check_if_user_is_active(db: Session) -> None:
    user = crud.create_user(session=db, user_create=UserCreate(email=random_email()))
    assert user.is_active is True


def test_check_if_user_is_active_inactive(db: Session) -> None:
    user_in = UserCreate(email=random_email(), is_active=False)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_active is False


def test_check_if_user_is_superuser(db: Session) -> None:
    user_in = UserCreate(email=random_email(), is_superuser=True)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_superuser is True


def test_check_if_user_is_superuser_normal_user(db: Session) -> None:
    user = crud.create_user(session=db, user_create=UserCreate(email=random_email()))
    assert user.is_superuser is False


def test_get_user(db: Session) -> None:
    user_in = UserCreate(email=random_email(), is_superuser=True)
    user = crud.create_user(session=db, user_create=user_in)
    user_2 = db.get(User, user.id)
    assert user_2
    assert user.email == user_2.email
    assert jsonable_encoder(user) == jsonable_encoder(user_2)


def test_update_user(db: Session) -> None:
    user_in = UserCreate(email=random_email(), is_superuser=True)
    user = crud.create_user(session=db, user_create=user_in)
    full_name = random_lower_string()
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(full_name=full_name))
    user_2 = db.get(User, user.id)
    assert user_2
    assert user_2.full_name == full_name
