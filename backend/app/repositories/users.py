"""
Users: creating, updating and reading one by email. Creating a user always
creates its Inbox project in the same transaction — `create_user` does that
insert itself rather than calling into `app.repositories.projects`, so the
one transaction a reader of either module sees is the whole of it.
"""

import uuid
from typing import Any

from sqlmodel import Session, select

from app.models import Project, User, UserCreate, UserUpdate


def create_user(
    *,
    session: Session,
    user_create: UserCreate,
    user_id: uuid.UUID | None = None,
    commit: bool = True,
) -> User:
    """
    Create a user and their Inbox. `user_id` is for registering, where the
    account's id is fixed before it exists: it is what the first passkey is
    made under. With `commit=False` the caller commits, so the account and
    its first passkey land together.
    """
    db_obj = User.model_validate(user_create)
    if user_id is not None:
        db_obj.id = user_id
    session.add(db_obj)
    # Flush so the user row exists before the FK-dependent Inbox insert, while
    # keeping both inserts in the same transaction as the eventual commit.
    session.flush()
    session.add(Project(name="Inbox", is_inbox=True, owner_id=db_obj.id))
    if commit:
        session.commit()
        session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user
