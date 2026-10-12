"""
Operations over a task: one act the product can perform, decided and
performed in one place so a human over REST and a bot over MCP both go
through the same rules rather than each re-deriving its own version of them
(#275).

`complete` is the first of them, and the slice that proves the shape (#279):
closing is the one status change that asks a question — what happens to a
parent's open subtasks — and can bring a new task into being, so it gets an
operation of its own rather than living as a branch inside
`app.api.routes.tasks.update_task`. `create`, `update` and `delete` follow in
later tickets, copying whatever shape this one establishes; `update` will
delegate to `complete` itself once it exists (#282), the way
`app.api.routes.tasks.update_task` already does below.

The helpers below (`_unique`, `_resolve_assignee`, `_check_recurrence`,
`_check_recurrence_update`) moved here from the route with `complete`: they
are not only `complete`'s — `create_task` and `bulk_update_tasks` still call
them too — but an operation is where this product's write rules now live,
not a route function, so this is where they stay even while some of their
callers are still routes.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException
from sqlalchemy import not_
from sqlmodel import Session, col, select

from app import activity, crud
from app.api import access
from app.api.access import TaskAction
from app.api.deps import Caller
from app.models import (
    BotUser,
    Comment,
    CommentBody,
    CommentCreate,
    Recurrence,
    SubtaskCompletion,
    Task,
    TaskStatus,
    TaskUpdate,
)
from app.refusals import task_has_uncompleted_subtasks

# Moving an open occurrence's due date means something different for the rest
# of its series depending on the scope, so a request that does not say which
# is malformed rather than defaulted (FR-01.17).
DUE_DATE_SCOPE_REQUIRED_STATUS = 400
DUE_DATE_SCOPE_REQUIRED_CODE = "due_date_scope_required"

# A later occurrence already exists: reopening this one would leave the series
# with two open occurrences (FR-01.16).
OCCURRENCE_SUPERSEDED_STATUS = 409
OCCURRENCE_SUPERSEDED_CODE = "occurrence_superseded"


def _unique(names: list[str]) -> list[str]:
    """
    Tag names with repeats dropped, keeping the order they were sent in. They
    arrive trimmed and non-blank from `TagName`; the same name twice is the one
    thing left that a task cannot store.
    """
    return list(dict.fromkeys(names))


def _resolve_assignee(
    session: Session,
    caller: Caller,
    assignee_id: uuid.UUID | None,
    current: crud.Assignee | None = None,
) -> crud.Assignee:
    """
    Who `assignee_id` names: the owner, or one of the owner's bot users
    (FR-01.7) — never another user or their bot users.

    A deleted bot user takes no new tasks, but stays on the ones it already
    has (FR-08.21), so resending `current` is not a new assignment.
    """
    if assignee_id is None:
        return crud.Assignee()
    if assignee_id == caller.owner_id:
        return crud.Assignee(user_id=assignee_id)
    bot = session.get(BotUser, assignee_id)
    if bot is None or bot.owner_id != caller.owner_id:
        raise HTTPException(
            status_code=400,
            detail="A task can only be assigned to you or to one of your bot users",
        )
    assignee = crud.Assignee(bot_user_id=bot.id)
    if bot.deleted_at is not None and assignee != current:
        raise HTTPException(
            status_code=400,
            detail=f"The bot user “{bot.name}” is deleted and takes no new tasks",
        )
    return assignee


def _check_recurrence(
    *,
    parent_id: uuid.UUID | None,
    recurrence: Recurrence | None,
    due_date: date | None,
    status: TaskStatus | None = None,
) -> None:
    """
    A recurring task is an open root task with a due date: its next
    occurrence's due date is counted from this one's, a subtask's routine is
    its root's, and a series always has one open occurrence.
    """
    if recurrence is None:
        return
    if status is TaskStatus.DONE:
        raise HTTPException(
            status_code=400,
            detail="Only an open task can recur",
        )
    if parent_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Only a task at the top of its tree can recur",
        )
    if due_date is None:
        raise HTTPException(status_code=400, detail="A recurring task needs a due date")


def _check_recurrence_update(
    *, session: Session, task: Task, task_in: TaskUpdate
) -> Recurrence | None:
    """
    Everything an update has to get right about the task's series. Returns
    the recurrence the task has now, which it read to decide.
    """
    fields_set = task_in.model_fields_set
    current = crud.get_recurrences(session=session, tasks=[task])[task.id]
    recurrence = task_in.recurrence if "recurrence" in fields_set else current
    due_date = task_in.due_date if "due_date" in fields_set else task.due_date
    recurrence_changes = recurrence != current
    is_done = task.status is TaskStatus.DONE

    if recurrence_changes:
        if is_done:
            # Its series has already moved on, or it would start one that
            # nothing ever moves to done to create a next occurrence.
            raise HTTPException(
                status_code=400,
                detail="Only an open task can change how it recurs",
            )
        _check_recurrence(
            parent_id=task.parent_id, recurrence=recurrence, due_date=due_date
        )
    elif recurrence is not None and due_date is None:
        raise HTTPException(status_code=400, detail="A recurring task needs a due date")

    # A new rule restarts the schedule from this occurrence anyway, so only a
    # date moving on its own asks what happens to the rest of the series.
    reschedules = (
        current is not None
        and not is_done
        and not recurrence_changes
        and due_date != task.due_date
    )
    if reschedules and task_in.due_date_scope is None:
        raise HTTPException(
            status_code=DUE_DATE_SCOPE_REQUIRED_STATUS,
            detail={
                "code": DUE_DATE_SCOPE_REQUIRED_CODE,
                "message": (
                    "This task recurs. Say whether the new due date applies to "
                    "this occurrence only or to this and all following ones."
                ),
            },
        )
    if not reschedules and task_in.due_date_scope is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "`due_date_scope` only applies to changing the due date of a "
                "recurring task that is open"
            ),
        )

    if (
        task_in.status is not None
        and task_in.status is not TaskStatus.DONE
        and is_done
        and crud.is_superseded(session=session, task=task)
    ):
        raise HTTPException(
            status_code=OCCURRENCE_SUPERSEDED_STATUS,
            detail={
                "code": OCCURRENCE_SUPERSEDED_CODE,
                "message": (
                    "A later occurrence of this recurring task already exists. "
                    "Only the latest occurrence can be reopened."
                ),
            },
        )
    return current


@dataclass(frozen=True)
class CompleteResult:
    """
    What closing a task produced (#275, #279): the task exactly as
    `crud.update_task` left it, the next occurrence when the close spawned
    one (FR-01.14), whether the task was already done before this call, and
    the comment when the caller left one as part of the same act.

    Its own type rather than one shared result with optional fields: a
    shared result would reproduce the lie `app.api.routes.tasks.update_task`
    told as `-> Any` for exactly the field this result exists to carry.
    """

    task: Task
    next_occurrence: Task | None
    already_done: bool
    comment: Comment | None


def _set_actor(session: Session, caller: Caller) -> None:
    """
    Attribute whatever this transaction commits to the caller itself
    (FR-10.2): a bot user's close is never recorded as its owner's. Set here
    rather than relied on from wherever `caller` was resolved — every path
    today happens to run through the one `app.api.deps` dependency that
    already does this, but a second caller already exists (#275), so this
    operation does not take that on faith.
    """
    if caller.bot is not None:
        activity.set_bot_actor(session, caller.bot.id)
    else:
        activity.set_actor(session, caller.owner_id)


def _open_occurrence(session: Session, series_id: uuid.UUID) -> Task | None:
    """
    The one open occurrence of `series_id`, if there is one — the occurrence
    closing a task just created (FR-01.14), read back here so a caller never
    has to ask for it with a query of its own.
    """
    return session.exec(
        select(Task).where(
            Task.series_id == series_id, not_(col(Task.status) == TaskStatus.DONE)
        )
    ).first()


def complete(
    session: Session,
    caller: Caller,
    task_id: uuid.UUID,
    task_in: TaskUpdate,
    comment: CommentBody | None = None,
) -> CompleteResult:
    """
    Close a task: move it to `status: done` (FR-01.5), or apply whatever else
    `task_in` asks of it alongside that move — the same single request
    `PATCH /tasks/{id}` has always accepted (`title`, `project_id`,
    `assignee_id`, tags, the due date, all optional and all independent of
    the status move), now performed in one place for both callers that
    perform it (#275).

    Decides access itself (`app.api.access.get_task`), rather than taking it
    as already settled: an operation is the one place this product's write
    rules live, not whichever caller happened to check first.

    A parent with open subtasks is refused (`task_has_uncompleted_subtasks`,
    FR-02.6) unless `task_in.subtasks` says what happens to them — `complete`
    closes them too, `leave_uncompleted` leaves each where it is
    (FR-02.5–FR-02.7) — and the refusal carries the open subtasks themselves,
    so a caller that wants to name them never queries the subtree twice.
    Closing the open occurrence of a recurring task creates the next one
    (FR-01.14); it rides back as `CompleteResult.next_occurrence` rather than
    needing a query of its own to find.

    `comment` is part of the same act (#279): checked against the
    `add_comments` grant before anything closes, so a refusal over it aborts
    the whole act and nothing is closed either, and written only after the
    close itself succeeds. This does not make the two one transaction — this
    ticket introduces no unit of work (#284 does) — it is the same two
    commits `app.mcp.tools.complete_task` already made, now made from here.
    """
    _set_actor(session, caller)

    resolved = access.get_task(session, caller, task_id, TaskAction.UPDATE)
    task = resolved.task

    # The comment grant is its own check, ahead of anything that closes, so a
    # call that cannot leave its note closes nothing either — never refused
    # only after the fact.
    if comment is not None:
        access.get_task(session, caller, task_id, TaskAction.COMMENT)

    already_done = task.status is TaskStatus.DONE

    tag_names = _unique(task_in.tags) if task_in.tags is not None else None
    access.authorize_tag_names(session, caller, tag_names)
    _check_recurrence_update(session=session, task=task, task_in=task_in)

    if "project_id" in task_in.model_fields_set:
        if task_in.project_id is None:
            raise HTTPException(
                status_code=400, detail="A task must belong to a project"
            )
        if task.parent_id is not None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "A subtask follows its parent's project; move the task at "
                    "the top of the tree instead"
                ),
            )
        # Moving a task in is as much a change to the destination as creating
        # one there. For a bot the source was checked above, so work can
        # neither leave its scope nor enter from outside it.
        access.get_project(session, caller, task_in.project_id, TaskAction.UPDATE)

    assignee = None
    if "assignee_id" in task_in.model_fields_set:
        assignee = _resolve_assignee(
            session,
            caller,
            task_in.assignee_id,
            current=crud.Assignee(task.assignee_id, task.assignee_bot_user_id),
        )

    if task_in.subtasks is not None and task_in.status is not TaskStatus.DONE:
        raise HTTPException(
            status_code=400,
            detail="`subtasks` only applies to a request that moves the task to done",
        )

    if task_in.status is TaskStatus.DONE and crud.has_open_subtasks(
        session=session, task=task
    ):
        if task_in.subtasks is None:
            raise task_has_uncompleted_subtasks(
                crud.open_subtasks(session=session, task=task)
            )
        if task_in.subtasks is SubtaskCompletion.COMPLETE:
            crud.complete_subtasks(session=session, task=task)

    task = crud.update_task(
        session=session,
        db_task=task,
        task_in=task_in,
        assignee=assignee,
        tag_names=tag_names,
    )

    next_occurrence = None
    if not already_done and task.status is TaskStatus.DONE and task.series_id is not None:
        next_occurrence = _open_occurrence(session, task.series_id)

    comment_row = None
    if comment is not None:
        comment_row = crud.create_comment(
            session=session,
            comment_create=CommentCreate(body=comment),
            task_id=task_id,
            owner_id=caller.owner_id,
            author_bot_user_id=caller.bot.id if caller.bot else None,
        )

    return CompleteResult(
        task=task,
        next_occurrence=next_occurrence,
        already_done=already_done,
        comment=comment_row,
    )


__all__ = [
    "DUE_DATE_SCOPE_REQUIRED_CODE",
    "DUE_DATE_SCOPE_REQUIRED_STATUS",
    "OCCURRENCE_SUPERSEDED_CODE",
    "OCCURRENCE_SUPERSEDED_STATUS",
    "CompleteResult",
    "complete",
]
