import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, select

from app import deletions
from app.activity_log import _KIND_ACTIONS as _KIND_ACTIONS  # re-export, see below
from app.activity_log import ActivityNarrowing
from app.activity_log import read_activity as _read_activity
from app.api.access import archived_refusal
from app.api.deps import CallerDep, CurrentUser, SessionDep
from app.deletions import DeletionKind, Restorability, RestoreRefusal
from app.models import (
    ActivityAction,
    ActivityEntriesPublic,
    ActivityEntry,
    ActivityEntryPublic,
    ActivityKind,
    ActivityOrder,
    BotActivityEntriesPublic,
    BotActivityEntryPublic,
    BotUser,
    Message,
)

router = APIRouter(prefix="/activity-log", tags=["activity"])

# The entries a restore can start from.
_DELETIONS = (ActivityAction.TASK_DELETED, ActivityAction.PROJECT_DELETED)

# `tests/api/routes/test_activity_by_kind.py::test_every_action_belongs_to_
# exactly_one_kind` imports `_KIND_ACTIONS` from this module by name: kept
# importable from here, re-exported from where the reader (#298) now owns
# it (`app.activity_log`), rather than moving that test.


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


@router.get("/", response_model=ActivityEntriesPublic | BotActivityEntriesPublic)
def read_activity_log(
    session: SessionDep,
    caller: CallerDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    actor_bot_user_id: uuid.UUID | None = Query(default=None),
    kind: ActivityKind | None = Query(default=None),
    by_bots: bool = Query(default=False),
    by_user: bool = Query(default=False),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    task_id: uuid.UUID | None = Query(default=None),
    project_id: uuid.UUID | None = Query(default=None),
    order: ActivityOrder = Query(default=ActivityOrder.NEWEST),
) -> ActivityEntriesPublic | BotActivityEntriesPublic:
    """
    Retrieve the caller's activity log, newest first unless `order` says
    `oldest` (FR-10.10).

    A human session reads exactly what it always has (spec #246): this
    endpoint only widens who may call it. A bot user needs the
    `read_activity` grant, off by default and checked before anything else
    (FR-08.9), and then reads only the entries about the projects, tasks,
    comments, attachments and tags of its scope — never an archived project,
    whatever the scope lists, and never a batch that touched a task outside
    it (`app.activity_log.read_activity`, `app.access.activity_log_scope`).
    Its response is declared as `BotActivityEntriesPublic`, which has no
    `restorable` or deletion id at all (#298, ADR-0011); restoring stays a
    human-only action.

    `actor_bot_user_id` narrows it to one bot user's own changes — what an
    operator asks when they want to read an integration rather than their
    whole account (FR-10.2). A deleted bot user's entries stay readable under
    it (FR-08.19).

    `kind` narrows it to one group of changes — what the reader finished,
    filed or threw away — so that a log which records everything (FR-10.3)
    can still answer one question at a time. The groups do not overlap. The
    two narrowings are independent and combine: what this integration
    finished is both of them at once.

    `by_user` keeps the user's own changes, the other side of `by_bots`: what
    "You" is in the log's actor menu.

    `by_bots` keeps the changes any of the user's bot users made, and `since`
    the entries written after a moment. Together they are what the dashboard
    counts when it says how many changes the user's bot users made since their
    last visit (FR-06.12). A moment without an offset is read as UTC.

    `until` is the upper bound to `since`, inclusive of its own moment, so a
    closed period — "last month" — can be asked for in one request instead
    of paged until the dates run out. Read as UTC when given without an
    offset, like `since`, and combines with every other narrowing.

    `task_id` narrows it to one task's history: the entries about the task,
    about the comments and files on it, and the batches that touched it. It
    is what the task panel's Activity section reads, and it combines with the
    other narrowings. A task is one of the caller's own records, and — for a
    bot user — one its scope reaches, so one that is not theirs, does not
    exist, or is outside the scope is a 404 — the same answer for all three —
    rather than a history that looks empty. A deleted task's history still
    reads.

    `project_id` narrows it to one project's chronology, the way `task_id`
    does a task's: the entries about the project, the tasks in it and their
    comments and files. It is what the project panel's Activity section
    reads, and a project the caller cannot reach is a 404 like a task.

    `order` turns the log around. It changes which end a page starts from and
    nothing about what the log holds, so it combines with every narrowing and
    with `skip` and `limit`.

    Always the caller's own owner's entries and nothing wider: there is no
    parameter or role that reaches another user's log, the superuser's
    included (FR-10.7). Narrowing by a bot user somebody else owns is
    therefore an empty feed rather than a refusal — the caller's own entries,
    of which that actor made none — so the filter says nothing about whose
    bot user it is, or whether it exists at all.
    """
    page = _read_activity(
        session,
        caller,
        ActivityNarrowing(
            kind=kind,
            task_id=task_id,
            project_id=project_id,
            actor_bot_user_id=actor_bot_user_id,
            by_bots=by_bots,
            by_user=by_user,
            since=since,
            until=until,
            order=order,
            skip=skip,
            limit=limit,
        ),
    )
    entries = page.entries
    locations = page.locations

    bot_names = dict(
        session.exec(
            select(BotUser.id, BotUser.name).where(
                col(BotUser.id).in_(
                    {e.actor_bot_user_id for e in entries if e.actor_bot_user_id}
                )
            )
        ).all()
    )

    if caller.bot is not None:
        # A bot user's own projection: everything but `restorable` and the
        # deletion id (ADR-0011) — never computed for a bot at all, rather
        # than computed and then excluded from a hand-built response.
        bot_entries = [
            BotActivityEntryPublic.model_validate(
                entry,
                update={
                    "entity_exists": entry.entity_id in locations,
                    "entity_project_id": locations.get(entry.entity_id),
                    "actor_bot_user_name": bot_names.get(entry.actor_bot_user_id)
                    if entry.actor_bot_user_id
                    else None,
                },
            )
            for entry in entries
        ]
        return BotActivityEntriesPublic(data=bot_entries, count=page.total)

    # The deletion events on this page, and whether each still has something
    # to bring back: the same answer a restore of it would act on. A human's
    # own projection alone carries this and the deletion id (ADR-0011).
    verdicts = deletions.restorability(
        session,
        caller.owner_id,
        {
            entry.deletion_id
            for entry in entries
            if entry.action in _DELETIONS and entry.deletion_id
        },
    )
    public_entries = [
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
    ]
    return ActivityEntriesPublic(data=public_entries, count=page.total)


def _restorable(
    entry: ActivityEntry, verdicts: dict[uuid.UUID, deletions.Restorability]
) -> bool:
    """Whether the entry is a deletion that still has something to bring back."""
    deletion_id = entry.deletion_id
    if entry.action not in _DELETIONS or deletion_id is None:
        return False
    verdict = verdicts.get(deletion_id)
    return verdict is not None and verdict.restorable


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
