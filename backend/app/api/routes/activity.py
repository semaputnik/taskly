import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep, require_project_writable
from app.models import (
    ActivityAction,
    ActivityEntityType,
    ActivityEntriesPublic,
    ActivityEntry,
    ActivityEntryPublic,
    Attachment,
    BotUser,
    Comment,
    Deletion,
    Message,
    Project,
    Task,
)

router = APIRouter(prefix="/activity-log", tags=["activity"])

# The entries a restore can start from.
_DELETIONS = (ActivityAction.TASK_DELETED, ActivityAction.PROJECT_DELETED)

# A restore that cannot go ahead is a state the user can resolve, not a
# malformed request: each cause has its own code so the client can say which
# thing is in the way (semaputnik/taskly#8, story 27).
RESTORE_REFUSED_STATUS = 409
PARENT_DELETED_CODE = "parent_deleted"
PROJECT_DELETED_CODE = "project_deleted"
SERIES_HAS_OPEN_OCCURRENCE_CODE = "series_has_open_occurrence"
DELETED_AGAIN_CODE = "deleted_again"


def _refuse(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=RESTORE_REFUSED_STATUS, detail={"code": code, "message": message}
    )


@router.get("/", response_model=ActivityEntriesPublic)
def read_activity_log(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    actor_bot_user_id: uuid.UUID | None = Query(default=None),
) -> Any:
    """
    Retrieve the current user's activity log, newest first.

    `actor_bot_user_id` narrows it to one bot user's own changes — what an
    operator asks when they want to read an integration rather than their
    whole account (FR-10.2). A deleted bot user's entries stay readable under
    it (FR-08.19).

    Always the requesting user's own entries and nothing wider: there is no
    parameter or role that reaches another user's log, the superuser's
    included (FR-10.7). Narrowing by a bot user somebody else owns is
    therefore an empty feed rather than a refusal — the caller's own entries,
    of which that actor made none — so the filter says nothing about whose
    bot user it is, or whether it exists at all.
    """
    where: list[Any] = [ActivityEntry.owner_id == current_user.id]
    if actor_bot_user_id is not None:
        where.append(ActivityEntry.actor_bot_user_id == actor_bot_user_id)

    count = session.exec(
        select(func.count()).select_from(ActivityEntry).where(*where)
    ).one()
    entries = session.exec(
        select(ActivityEntry)
        .where(*where)
        .order_by(col(ActivityEntry.position).desc())
        .offset(skip)
        .limit(limit)
    ).all()

    locations = _locate(session, current_user.id, entries)
    bot_names = dict(
        session.exec(
            select(BotUser.id, BotUser.name).where(
                col(BotUser.id).in_(
                    {e.actor_bot_user_id for e in entries if e.actor_bot_user_id}
                )
            )
        ).all()
    )
    # The deletion events on this page that still have rows to bring back.
    deletion_ids = {
        entry.deletion_id
        for entry in entries
        if entry.action in _DELETIONS and entry.deletion_id
    }
    still_deleted: set[uuid.UUID | None] = set()
    if deletion_ids:
        for model in (Task, Project):
            still_deleted.update(
                session.exec(
                    select(model.deletion_id).where(
                        col(model.deletion_id).in_(deletion_ids)
                    )
                ).all()
            )

    return ActivityEntriesPublic(
        data=[
            ActivityEntryPublic.model_validate(
                entry,
                update={
                    "entity_exists": entry.entity_id in locations,
                    "entity_project_id": locations.get(entry.entity_id),
                    "restorable": entry.action in _DELETIONS
                    and entry.deletion_id in still_deleted,
                    "actor_bot_user_name": bot_names.get(entry.actor_bot_user_id)
                    if entry.actor_bot_user_id
                    else None,
                },
            )
            for entry in entries
        ],
        count=count,
    )


def _locate(
    session: SessionDep, owner_id: uuid.UUID, entries: Sequence[ActivityEntry]
) -> dict[uuid.UUID, uuid.UUID]:
    """
    Where each entry's entity can still be opened: the project to open it in,
    keyed by entity id. An entity that is gone, or hangs off a task that is,
    has no entry here, so its log entry carries no link.
    """
    by_type: dict[str, set[uuid.UUID]] = {}
    for entry in entries:
        by_type.setdefault(entry.entity_type, set()).add(entry.entity_id)

    # The task each comment and attachment hangs off, so that one lookup
    # resolves every task this page of the log touches.
    parents: dict[uuid.UUID, uuid.UUID] = {}
    for model, entity_type in (
        (Comment, ActivityEntityType.COMMENT),
        (Attachment, ActivityEntityType.ATTACHMENT),
    ):
        if ids := by_type.get(entity_type):
            parents.update(
                session.exec(
                    select(model.id, model.task_id).where(col(model.id).in_(ids))
                ).all()
            )
    task_ids = by_type.get(ActivityEntityType.TASK, set())
    task_projects = crud.get_task_project_ids(
        session=session,
        owner_id=owner_id,
        task_ids=task_ids | set(parents.values()),
    )

    locations = {
        task_id: task_projects[task_id]
        for task_id in task_ids
        if task_id in task_projects
    }
    locations.update(
        {
            row_id: task_projects[task_id]
            for row_id, task_id in parents.items()
            if task_id in task_projects
        }
    )
    if project_ids := by_type.get(ActivityEntityType.PROJECT):
        live = session.exec(
            select(Project.id).where(
                col(Project.id).in_(project_ids), crud.not_deleted(Project)
            )
        ).all()
        locations.update({project_id: project_id for project_id in live})
    return locations


@router.post("/{entry_id}/restore", response_model=Message)
def restore_from_activity_entry(
    *, session: SessionDep, current_user: CurrentUser, entry_id: uuid.UUID
) -> Message:
    """
    Restore what a deletion entry records as deleted (FR-10.4).

    The deletion entry is the handle: there is no trash to restore from. What
    comes back is exactly what went down in that deletion — a task with its
    subtasks (FR-01.10), or a project with its tasks (FR-05.9) — so anything
    deleted on its own before stays deleted. A restore is refused, with a code
    naming the cause, when it has nowhere to come back to. Restoring what is
    already back changes nothing.
    """
    entry = session.get(ActivityEntry, entry_id)
    if not entry or entry.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Activity entry not found")
    if entry.action not in _DELETIONS or entry.deletion_id is None:
        raise HTTPException(status_code=400, detail="Only a deletion can be restored")

    deletion = session.get_one(Deletion, entry.deletion_id)
    tasks = crud.get_deletion_rows(session=session, deletion_id=deletion.id)
    if deletion.project_id is not None:
        project = session.get_one(Project, deletion.project_id)
        if project.deletion_id is None:
            return Message(message="Already restored")
        _check_project_restore(session, deletion, project, tasks)
        crud.restore_deletion(session=session, tasks=tasks, project=project)
        return Message(message="Project restored")

    if deletion.task_id is None:
        # A batch: the event names no single task, so every task it took down
        # on its own account is checked, and they come back together or not at
        # all — the act being undone was one act (semaputnik/taskly#66).
        if not tasks:
            return Message(message="Already restored")
        for restored in tasks:
            if restored.parent_id is None or restored.parent_id not in {
                task.id for task in tasks
            }:
                _check_task_restore(session, restored, tasks)
        crud.restore_deletion(session=session, tasks=tasks)
        return Message(message="Tasks restored")

    task = session.get_one(Task, deletion.task_id)
    if not tasks:
        if task.deletion_id is None:
            return Message(message="Already restored")
        raise _refuse(
            DELETED_AGAIN_CODE,
            "This task was restored and then deleted again. Restore it from "
            "the later deletion instead.",
        )
    _check_task_restore(session, task, tasks)
    crud.restore_deletion(session=session, tasks=tasks)
    return Message(message="Task restored")


def _check_task_restore(session: SessionDep, task: Task, tasks: Sequence[Task]) -> None:
    """Refuse a task restore that has nowhere to come back to."""
    if task.parent_id is not None:
        parent = session.get_one(Task, task.parent_id)
        if parent.deletion_id is not None:
            raise _refuse(
                PARENT_DELETED_CODE,
                f"“{task.title}” is a subtask of “{parent.title}”, which is "
                "deleted. Restore that task first.",
            )

    project = session.get_one(
        Project, crud.get_task_project_id(session=session, task=task)
    )
    if project.deletion_id is not None:
        raise _refuse(
            PROJECT_DELETED_CODE,
            f"“{task.title}” belongs to the project “{project.name}”, which is "
            "deleted. Restore the project first.",
        )
    # Restoring writes into the project, so an archived one refuses it the
    # same way it refuses any other change.
    require_project_writable(project)

    if crud.restoring_reopens_a_series(session=session, tasks=tasks):
        raise _refuse(
            SERIES_HAS_OPEN_OCCURRENCE_CODE,
            f"“{task.title}” repeats, and another occurrence of it is already "
            "open. Complete or delete that one first.",
        )


def _check_project_restore(
    session: SessionDep, deletion: Deletion, project: Project, tasks: Sequence[Task]
) -> None:
    """
    Refuse a project restore that cannot be done whole.

    A project comes back archived if it was archived when deleted: the two
    states are independent (FR-05.10), so that is no reason to refuse.
    """
    if project.deletion_id != deletion.id:
        raise _refuse(
            DELETED_AGAIN_CODE,
            "This project was restored and then deleted again. Restore it "
            "from the later deletion instead.",
        )
    if crud.restoring_reopens_a_series(session=session, tasks=tasks):
        # Refused as a whole: bringing the project back without one of its
        # tasks would be a restore nobody asked for.
        raise _refuse(
            SERIES_HAS_OPEN_OCCURRENCE_CODE,
            f"A repeating task in “{project.name}” has another occurrence "
            "already open. Complete or delete that one first.",
        )
