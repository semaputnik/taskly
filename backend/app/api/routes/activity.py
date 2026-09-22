import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, not_
from sqlmodel import col, func, select

from app import crud, deletions
from app.api.access import archived_refusal
from app.api.deps import CurrentUser, SessionDep
from app.deletions import DeletionKind, Restorability, RestoreRefusal
from app.models import (
    ActivityAction,
    ActivityEntityType,
    ActivityEntriesPublic,
    ActivityEntry,
    ActivityEntryPublic,
    ActivityKind,
    Attachment,
    BotUser,
    Comment,
    Message,
    Project,
    Tag,
    TaskStatus,
)

router = APIRouter(prefix="/activity-log", tags=["activity"])

# The entries a restore can start from.
_DELETIONS = (ActivityAction.TASK_DELETED, ActivityAction.PROJECT_DELETED)


# A batch that moved its tasks to done. It is logged as the one act it was —
# a single entry naming the new status, not a completion per task — so the
# only way to recognise it as finished work is to read what the batch did.
#
# `IS NOT DISTINCT FROM` rather than `=`: a batch that changed something else
# records no status at all, and comparing that missing key to a string yields
# NULL rather than false. Under plain `=`, negating this to find the changes
# would drop every such batch instead of keeping it.
_BULK_COMPLETION = and_(
    col(ActivityEntry.action) == ActivityAction.TASKS_BULK_CHANGED,
    col(ActivityEntry.details)["changes"]["status"].astext.is_not_distinct_from(
        TaskStatus.DONE.value
    ),
)

# Which actions each kind gathers. Every action belongs to exactly one kind:
# `tests/api/routes/test_activity_by_kind.py` holds the list to that, so a
# new kind of entry cannot quietly become unreachable from the filter.
_KIND_ACTIONS: dict[ActivityKind, tuple[ActivityAction, ...]] = {
    ActivityKind.COMPLETED: (ActivityAction.TASK_COMPLETED,),
    ActivityKind.CREATED: (
        ActivityAction.TASK_CREATED,
        ActivityAction.PROJECT_CREATED,
    ),
    ActivityKind.CHANGED: (
        ActivityAction.TASK_CHANGED,
        ActivityAction.TASKS_BULK_CHANGED,
        ActivityAction.TASK_REOPENED,
        ActivityAction.TASK_STATUS_CHANGED,
        ActivityAction.TASK_MOVED,
        ActivityAction.TASK_ASSIGNED,
        ActivityAction.TASK_UNASSIGNED,
        ActivityAction.PROJECT_CHANGED,
    ),
    ActivityKind.DELETED: (
        ActivityAction.TASK_DELETED,
        ActivityAction.TASK_RESTORED,
        ActivityAction.PROJECT_DELETED,
        ActivityAction.PROJECT_RESTORED,
    ),
    ActivityKind.COMMENTS: (
        ActivityAction.COMMENT_ADDED,
        ActivityAction.COMMENT_EDITED,
        ActivityAction.COMMENT_DELETED,
        ActivityAction.ATTACHMENT_ADDED,
        ActivityAction.ATTACHMENT_DELETED,
    ),
    ActivityKind.TAGS: (
        ActivityAction.TAG_CREATED,
        ActivityAction.TAG_RENAMED,
        ActivityAction.TAG_DELETED,
        ActivityAction.TAG_MERGED,
    ),
}


def _of_kind(kind: ActivityKind) -> Any:
    """
    What an entry has to satisfy to belong to `kind`.

    Completing a batch is the one change that two kinds could both claim, so
    the two say the same thing from opposite sides: it is a completion, and
    for that reason not one of the changes.
    """
    actions = col(ActivityEntry.action).in_(_KIND_ACTIONS[kind])
    if kind is ActivityKind.COMPLETED:
        return actions | _BULK_COMPLETION
    if kind is ActivityKind.CHANGED:
        return and_(actions, not_(_BULK_COMPLETION))
    return actions


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
    kind: ActivityKind | None = Query(default=None),
) -> Any:
    """
    Retrieve the current user's activity log, newest first.

    `actor_bot_user_id` narrows it to one bot user's own changes — what an
    operator asks when they want to read an integration rather than their
    whole account (FR-10.2). A deleted bot user's entries stay readable under
    it (FR-08.19).

    `kind` narrows it to one group of changes — what the reader finished,
    filed or threw away — so that a log which records everything (FR-10.3)
    can still answer one question at a time. The groups do not overlap. The
    two narrowings are independent and combine: what this integration
    finished is both of them at once.

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
    if kind is not None:
        where.append(_of_kind(kind))

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
    # The deletion events on this page, and whether each still has something
    # to bring back: the same answer a restore of it would act on.
    verdicts = deletions.restorability(
        session,
        current_user.id,
        {
            entry.deletion_id
            for entry in entries
            if entry.action in _DELETIONS and entry.deletion_id
        },
    )

    return ActivityEntriesPublic(
        data=[
            ActivityEntryPublic.model_validate(
                entry,
                update={
                    "entity_exists": entry.entity_id in locations,
                    "entity_project_id": locations.get(entry.entity_id),
                    "restorable": _restorable(entry, verdicts),
                    "actor_bot_user_name": bot_names.get(entry.actor_bot_user_id)
                    if entry.actor_bot_user_id
                    else None,
                },
            )
            for entry in entries
        ],
        count=count,
    )


def _restorable(
    entry: ActivityEntry, verdicts: dict[uuid.UUID, deletions.Restorability]
) -> bool:
    """Whether the entry is a deletion that still has something to bring back."""
    deletion_id = entry.deletion_id
    if entry.action not in _DELETIONS or deletion_id is None:
        return False
    verdict = verdicts.get(deletion_id)
    return verdict is not None and verdict.restorable


def _locate(
    session: SessionDep, owner_id: uuid.UUID, entries: Sequence[ActivityEntry]
) -> dict[uuid.UUID, uuid.UUID | None]:
    """
    Where each entry's entity can still be opened: the project to open it in,
    keyed by entity id — None for a tag, which belongs to no project. An
    entity that is gone, or hangs off a task that is, has no entry here, so
    its log entry carries no link.
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

    locations: dict[uuid.UUID, uuid.UUID | None] = {
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
    if tag_ids := by_type.get(ActivityEntityType.TAG):
        tags = session.exec(select(Tag.id).where(col(Tag.id).in_(tag_ids))).all()
        locations.update(dict.fromkeys(tags))
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

    verdict = deletions.restore(session, current_user.id, entry.deletion_id)
    if verdict.refusal is RestoreRefusal.ALREADY_RESTORED:
        return Message(message="Already restored")
    if verdict.refusal is not None:
        raise _refusal(verdict)
    return Message(message=_RESTORED[verdict.kind])


_RESTORED = {
    DeletionKind.TASK: "Task restored",
    DeletionKind.PROJECT: "Project restored",
    DeletionKind.BATCH: "Tasks restored",
}


def _refusal(verdict: Restorability) -> HTTPException:
    """A restore that cannot go ahead, said the way the API says it."""
    subject = verdict.subject
    match verdict.refusal:
        case RestoreRefusal.PROJECT_ARCHIVED:
            # Restoring writes into the project, so an archived one refuses
            # it the same way it refuses any other change.
            assert verdict.project is not None
            return archived_refusal(verdict.project)
        case RestoreRefusal.PARENT_DELETED:
            return _refuse(
                PARENT_DELETED_CODE,
                f"“{subject}” is a subtask of “{verdict.parent}”, which is "
                "deleted. Restore that task first.",
            )
        case RestoreRefusal.PROJECT_DELETED:
            assert verdict.project is not None
            return _refuse(
                PROJECT_DELETED_CODE,
                f"“{subject}” belongs to the project “{verdict.project.name}”, "
                "which is deleted. Restore the project first.",
            )
        case RestoreRefusal.SERIES_HAS_OPEN_OCCURRENCE if (
            verdict.kind is DeletionKind.PROJECT
        ):
            return _refuse(
                SERIES_HAS_OPEN_OCCURRENCE_CODE,
                f"A repeating task in “{subject}” has another occurrence "
                "already open. Complete or delete that one first.",
            )
        case RestoreRefusal.SERIES_HAS_OPEN_OCCURRENCE:
            return _refuse(
                SERIES_HAS_OPEN_OCCURRENCE_CODE,
                f"“{subject}” repeats, and another occurrence of it is already "
                "open. Complete or delete that one first.",
            )
        case _:
            what = "project" if verdict.kind is DeletionKind.PROJECT else "task"
            return _refuse(
                DELETED_AGAIN_CODE,
                f"This {what} was restored and then deleted again. Restore it "
                "from the later deletion instead.",
            )
