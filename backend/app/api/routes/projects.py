import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app import crud, deletions
from app.api import access
from app.api.access import TaskAction
from app.api.deps import Caller, CallerDep, CurrentUser, SessionDep
from app.models import (
    Message,
    Project,
    ProjectCreate,
    ProjectPublic,
    ProjectsPublic,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _task_count(session: SessionDep, project: Project) -> int:
    """What one project holds, for the responses that report a single one."""
    counts = crud.get_project_task_counts(
        session=session, owner_id=project.owner_id, project_ids=[project.id]
    )
    return counts.get(project.id, 0)


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
        access.refuse_archived_for_bot(caller)
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
    task_counts = crud.get_project_task_counts(
        session=session,
        owner_id=caller.owner_id,
        project_ids=[project.id for project in projects],
    )
    return ProjectsPublic(
        data=[
            crud.project_public(project, task_counts.get(project.id, 0))
            for project in projects
        ],
        count=count,
    )


@router.get("/{project_id}", response_model=ProjectPublic)
def read_project(
    *, session: SessionDep, caller: CallerDep, project_id: uuid.UUID
) -> Any:
    """
    Retrieve one project by its id: what the project's panel is addressed by,
    so a link opens a project the list in view would exclude.

    A bot user reads only the projects in its scope, and never an archived one
    (FR-08.9, FR-05.13). No task permission is asked for: a bot that may write
    into a project has to be able to resolve the project it writes into.
    """
    project = access.get_project(session, caller, project_id, action=None)
    return crud.project_public(project, _task_count(session, project))


@router.post("/", response_model=ProjectPublic)
def create_project(
    *, session: SessionDep, current_user: CurrentUser, project_in: ProjectCreate
) -> Any:
    """
    Create a new project.
    """
    project = crud.create_project(
        session=session, project_create=project_in, owner_id=current_user.id
    )
    return crud.project_public(project)


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
    project = access.get_project(
        session, Caller(owner_id=current_user.id), project_id, TaskAction.UPDATE
    )
    if project.is_inbox and "name" in project_in.model_fields_set:
        raise HTTPException(
            status_code=400, detail="The Inbox project cannot be renamed"
        )
    project = crud.update_project(
        session=session, db_project=project, project_in=project_in
    )
    return crud.project_public(project, _task_count(session, project))


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
    project = access.get_project(
        session, Caller(owner_id=current_user.id), project_id, action=None
    )
    if project.is_inbox:
        # Tasks created without a project land in the Inbox (FR-05.4), which
        # an archived, read-only Inbox could no longer take.
        raise HTTPException(
            status_code=400, detail="The Inbox project cannot be archived"
        )
    project = crud.set_project_archived(session=session, project=project, archived=True)
    return crud.project_public(project, _task_count(session, project))


@router.post("/{project_id}/unarchive", response_model=ProjectPublic)
def unarchive_project(
    *, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID
) -> Any:
    """
    Unarchive a project, bringing it and its tasks back exactly as they were
    (FR-05.10, FR-05.11).
    """
    project = access.get_project(
        session, Caller(owner_id=current_user.id), project_id, action=None
    )
    project = crud.set_project_archived(
        session=session, project=project, archived=False
    )
    return crud.project_public(project, _task_count(session, project))


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
    project = access.get_project(
        session, Caller(owner_id=current_user.id), project_id, action=None
    )
    if project.is_inbox:
        raise HTTPException(
            status_code=400, detail="The Inbox project cannot be deleted"
        )
    deletions.delete_project(session, project)
    return Message(message="Project deleted successfully")
