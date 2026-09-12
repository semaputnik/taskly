import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_owned_project
from app.models import (
    Message,
    Project,
    ProjectCreate,
    ProjectPublic,
    ProjectsPublic,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=ProjectsPublic)
def read_projects(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve the current user's projects.
    """
    count_statement = (
        select(func.count())
        .select_from(Project)
        .where(Project.owner_id == current_user.id, crud.not_deleted(Project))
    )
    count = session.exec(count_statement).one()

    statement = (
        select(Project)
        .where(Project.owner_id == current_user.id, crud.not_deleted(Project))
        .offset(skip)
        .limit(limit)
    )
    projects = session.exec(statement).all()
    return ProjectsPublic(data=projects, count=count)


@router.post("/", response_model=ProjectPublic)
def create_project(
    *, session: SessionDep, current_user: CurrentUser, project_in: ProjectCreate
) -> Any:
    """
    Create a new project.
    """
    return crud.create_project(
        session=session, project_create=project_in, owner_id=current_user.id
    )


@router.patch("/{project_id}", response_model=ProjectPublic)
def update_project(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    project_in: ProjectUpdate,
) -> Any:
    """
    Update a project's name and/or description.
    """
    project = get_owned_project(session, current_user, project_id)
    if project.is_inbox and "name" in project_in.model_fields_set:
        raise HTTPException(
            status_code=400, detail="The Inbox project cannot be renamed"
        )
    return crud.update_project(
        session=session, db_project=project, project_in=project_in
    )


@router.delete("/{project_id}")
def delete_project(
    *, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID
) -> Message:
    """
    Delete a project, and every task in it with it.

    The project and its tasks are marked deleted rather than removed, so the
    deletion can be reversed from the activity log later (FR-05.8, FR-05.9).
    """
    project = get_owned_project(session, current_user, project_id)
    if project.is_inbox:
        raise HTTPException(
            status_code=400, detail="The Inbox project cannot be deleted"
        )
    crud.delete_project(session=session, project=project)
    return Message(message="Project deleted successfully")
