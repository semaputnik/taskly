import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep, require_project_writable
from app.models import (
    ActivityAction,
    ActivityEntriesPublic,
    ActivityEntry,
    ActivityEntryPublic,
    Deletion,
    Message,
    Project,
    Task,
)

router = APIRouter(prefix="/activity-log", tags=["activity"])

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
) -> Any:
    """
    Retrieve the current user's activity log, newest first.

    Always the requesting user's own entries and nothing wider: there is no
    parameter or role that reaches another user's log, the superuser's
    included (FR-10.7).
    """
    count = session.exec(
        select(func.count())
        .select_from(ActivityEntry)
        .where(ActivityEntry.owner_id == current_user.id)
    ).one()
    entries = session.exec(
        select(ActivityEntry)
        .where(ActivityEntry.owner_id == current_user.id)
        .order_by(col(ActivityEntry.position).desc())
        .offset(skip)
        .limit(limit)
    ).all()

    # The tasks that can still be opened, and where: deleted ones are left out
    # of this map, so their entries carry no link.
    task_projects = crud.get_task_project_ids(session=session, owner_id=current_user.id)
    # The deletion events on this page that still have rows to bring back.
    deletion_ids = {
        entry.deletion_id
        for entry in entries
        if entry.action == ActivityAction.TASK_DELETED and entry.deletion_id
    }
    still_deleted = (
        set(
            session.exec(
                select(Task.deletion_id).where(col(Task.deletion_id).in_(deletion_ids))
            ).all()
        )
        if deletion_ids
        else set()
    )

    return ActivityEntriesPublic(
        data=[
            ActivityEntryPublic.model_validate(
                entry,
                update={
                    "entity_exists": entry.entity_id in task_projects,
                    "entity_project_id": task_projects.get(entry.entity_id),
                    "restorable": entry.action == ActivityAction.TASK_DELETED
                    and entry.deletion_id in still_deleted,
                },
            )
            for entry in entries
        ],
        count=count,
    )


@router.post("/{entry_id}/restore", response_model=Message)
def restore_from_activity_entry(
    *, session: SessionDep, current_user: CurrentUser, entry_id: uuid.UUID
) -> Message:
    """
    Restore what a deletion entry records as deleted (FR-10.4).

    The deletion entry is the handle: there is no trash to restore from. The
    task comes back with exactly the subtasks that went down in the same
    deletion, so a subtask deleted on its own before stays deleted (FR-01.10).
    A restore is refused, with a code naming the cause, when the task would
    have nowhere to come back to. Restoring what is already back changes
    nothing.
    """
    entry = session.get(ActivityEntry, entry_id)
    if not entry or entry.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Activity entry not found")
    if entry.action != ActivityAction.TASK_DELETED or entry.deletion_id is None:
        raise HTTPException(status_code=400, detail="Only a deletion can be restored")

    deletion = session.get_one(Deletion, entry.deletion_id)
    assert deletion.task_id is not None
    task = session.get_one(Task, deletion.task_id)
    rows = crud.get_deletion_rows(session=session, deletion_id=deletion.id)

    if not rows:
        if task.deletion_id is None:
            return Message(message="Already restored")
        raise _refuse(
            DELETED_AGAIN_CODE,
            "This task was restored and then deleted again. Restore it from "
            "the later deletion instead.",
        )

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

    if crud.restoring_reopens_a_series(session=session, tasks=rows):
        raise _refuse(
            SERIES_HAS_OPEN_OCCURRENCE_CODE,
            f"“{task.title}” repeats, and another occurrence of it is already "
            "open. Complete or delete that one first.",
        )

    crud.restore_deletion(session=session, tasks=rows)
    return Message(message="Task restored")
