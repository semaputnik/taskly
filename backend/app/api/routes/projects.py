import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api import authorization
from app.api.deps import (
    CallerDep,
    CurrentUser,
    SessionDep,
    get_owned_project,
    require_project_writable,
)
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
    session: SessionDep,
    caller: CallerDep,
    skip: int = 0,
    limit: int = 100,
    archived: bool = False,
) -> Any:
    """
    Retrieve the current user's projects: the live ones, or only the archived
    ones when `archived` asks for the archive (FR-05.14).

    A bot user sees only the projects in its scope, and never the archive
    (FR-08.9, FR-05.13).
    """
    if archived:
        authorization.refuse_archived_for_bot(caller)
    conditions: list[Any] = [
        Project.owner_id == caller.owner_id,
        crud.not_deleted(Project),
        Project.is_archived == archived,
    ]
    if caller.bot is not None:
        conditions.append(col(Project.id).in_(caller.project_ids))
    count_statement = select(func.count()).select_from(Project).where(*conditions)
    count = session.exec(count_statement).one()

    statement = select(Project).where(*conditions).offset(skip).limit(limit)
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
    require_project_writable(project)
    if project.is_inbox and "name" in project_in.model_fields_set:
        raise HTTPException(
            status_code=400, detail="The Inbox project cannot be renamed"
        )
    return crud.update_project(
        session=session, db_project=project, project_in=project_in
    )


@router.post("/{project_id}/archive", response_model=ProjectPublic)
def archive_project(
    *, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID
) -> Any:
    """
    Archive a project, and every task in it with it: they leave the default
    views and become read-only until the project is unarchived (FR-05.10,
    FR-05.11).

    A toggle, not a deletion — nothing is recorded to restore from, and
    archiving a project that already is changes nothing.
    """
    project = get_owned_project(session, current_user, project_id)
    if project.is_inbox:
        # Tasks created without a project land in the Inbox (FR-05.4), which
        # an archived, read-only Inbox could no longer take.
        raise HTTPException(
            status_code=400, detail="The Inbox project cannot be archived"
        )
    return crud.set_project_archived(session=session, project=project, archived=True)


@router.post("/{project_id}/unarchive", response_model=ProjectPublic)
def unarchive_project(
    *, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID
) -> Any:
    """
    Unarchive a project, bringing it and its tasks back exactly as they were
    (FR-05.10, FR-05.11).
    """
    project = get_owned_project(session, current_user, project_id)
    return crud.set_project_archived(session=session, project=project, archived=False)


@router.delete("/{project_id}")
def delete_project(
    *, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID
) -> Message:
    """
    Delete a project, and every task in it with it.

    The project and its tasks are marked deleted rather than removed, so the
    deletion can be reversed from the activity log later (FR-05.8, FR-05.9).
    Archiving does not stand in the way: an archived project can be deleted
    like any other.
    """
    project = get_owned_project(session, current_user, project_id)
    if project.is_inbox:
        raise HTTPException(
            status_code=400, detail="The Inbox project cannot be deleted"
        )
    crud.delete_project(session=session, project=project)
    return Message(message="Project deleted successfully")
