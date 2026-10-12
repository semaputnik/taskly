"""
Operations over a task: one act the product can perform, decided and
performed in one place so a human over REST and a bot over MCP both go
through the same rules rather than each re-deriving its own version of them
(#275).

`complete` was the first of them (#279), and the slice that proved the
shape: closing is the one status change that asks a question — what happens
to a parent's open subtasks — and can bring a new task into being, so it
got an operation of its own rather than living as a branch inside
`app.api.routes.tasks.update_task`. `create` (#281) and now `update` and
`delete` (#282) are the rest: `app.api.routes.tasks.update_task` and
`.delete_task` are left binding the request and shaping the response, same
as `.create_task` already does. `update` delegates to `complete` itself,
the way `app.api.routes.tasks.update_task` used to.

Every raise in this module is a `Refusal` (`app.refusals`), never an
`HTTPException` (#282's first correction): an operation knows nothing about
HTTP, and the one handler that used to have no way to render a bare-string
body (`app.main.refusal_refused`) now can. `resolve_task_assignee` stays
public because `app.api.routes.tasks.bulk_update_tasks` still needs it for
its own assignee changes — `bulk_update_tasks` is human-only and is not
becoming an operation. `_unique_tag_names` and `_check_recurrence_update`
went private once `update_task` (the route) had nothing left to call them
for: `update` is the only caller left, now that it is this module's own.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import not_
from sqlmodel import Session, col, select

from app import crud, deletions, refusals
from app.api import access
from app.api.access import TaskAction
from app.caller import Caller, set_caller_actor
from app.models import (
    BotUser,
    Comment,
    CommentBody,
    CommentCreate,
    Project,
    Recurrence,
    SubtaskCompletion,
    Task,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
)


def _unique_tag_names(names: list[str]) -> list[str]:
    """
    Tag names with repeats dropped, keeping the order they were sent in. They
    arrive trimmed and non-blank from `TagName`; the same name twice is the
    one thing left that a task cannot store.

    Private: `create` and `update`, below, are this module's only callers
    now that `update_task` (the route) delegates to `update` instead of
    calling this itself (#282).
    """
    return list(dict.fromkeys(names))


def resolve_task_assignee(
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

    Public: `app.api.routes.tasks.bulk_update_tasks` still calls this across
    the module boundary for its own assignee changes — it is human-only and
    is not becoming an operation (#275). `update` (below) is this module's
    own caller for everything else; `update_task` (the route) has nothing
    left to call this for, now that `update` calls it instead (#282).
    """
    if assignee_id is None:
        return crud.Assignee()
    if assignee_id == caller.owner_id:
        return crud.Assignee(user_id=assignee_id)
    bot = session.get(BotUser, assignee_id)
    if bot is None or bot.owner_id != caller.owner_id:
        raise refusals.plain(
            400, "A task can only be assigned to you or to one of your bot users"
        )
    assignee = crud.Assignee(bot_user_id=bot.id)
    if bot.deleted_at is not None and assignee != current:
        raise refusals.plain(
            400, f"The bot user “{bot.name}” is deleted and takes no new tasks"
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
        raise refusals.plain(400, "Only an open task can recur")
    if parent_id is not None:
        raise refusals.plain(400, "Only a task at the top of its tree can recur")
    if due_date is None:
        raise refusals.plain(400, "A recurring task needs a due date")


def _check_recurrence_update(
    *, session: Session, task: Task, task_in: TaskUpdate
) -> Recurrence | None:
    """
    Everything an update has to get right about the task's series. Returns
    the recurrence the task has now, which it read to decide.

    Private: `update`, below, is this module's only caller now that
    `update_task` (the route) delegates to it instead of calling this
    itself (#282).
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
            raise refusals.plain(400, "Only an open task can change how it recurs")
        _check_recurrence(
            parent_id=task.parent_id, recurrence=recurrence, due_date=due_date
        )
    elif recurrence is not None and due_date is None:
        raise refusals.plain(400, "A recurring task needs a due date")

    # A new rule restarts the schedule from this occurrence anyway, so only a
    # date moving on its own asks what happens to the rest of the series.
    reschedules = (
        current is not None
        and not is_done
        and not recurrence_changes
        and due_date != task.due_date
    )
    if reschedules and task_in.due_date_scope is None:
        raise refusals.due_date_scope_required()
    if not reschedules and task_in.due_date_scope is not None:
        raise refusals.plain(
            400,
            "`due_date_scope` only applies to changing the due date of a "
            "recurring task that is open",
        )

    if (
        task_in.status is not None
        and task_in.status is not TaskStatus.DONE
        and is_done
        and crud.is_superseded(session=session, task=task)
    ):
        raise refusals.occurrence_superseded()
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
    set_caller_actor(session, caller)

    resolved = access.get_task(session, caller, task_id, TaskAction.UPDATE)
    task = resolved.task

    # The comment grant is its own check, ahead of anything that closes, so a
    # call that cannot leave its note closes nothing either — never refused
    # only after the fact.
    if comment is not None:
        access.get_task(session, caller, task_id, TaskAction.COMMENT)

    already_done = task.status is TaskStatus.DONE

    tag_names = _unique_tag_names(task_in.tags) if task_in.tags is not None else None
    access.authorize_tag_names(session, caller, tag_names)
    _check_recurrence_update(session=session, task=task, task_in=task_in)

    if "project_id" in task_in.model_fields_set:
        if task_in.project_id is None:
            raise refusals.plain(400, "A task must belong to a project")
        if task.parent_id is not None:
            raise refusals.plain(
                400,
                "A subtask follows its parent's project; move the task at "
                "the top of the tree instead",
            )
        # Moving a task in is as much a change to the destination as creating
        # one there. For a bot the source was checked above, so work can
        # neither leave its scope nor enter from outside it.
        access.get_project(session, caller, task_in.project_id, TaskAction.UPDATE)

    assignee = None
    if "assignee_id" in task_in.model_fields_set:
        assignee = resolve_task_assignee(
            session,
            caller,
            task_in.assignee_id,
            current=crud.Assignee(task.assignee_id, task.assignee_bot_user_id),
        )

    if task_in.subtasks is not None and task_in.status is not TaskStatus.DONE:
        raise refusals.plain(
            400, "`subtasks` only applies to a request that moves the task to done"
        )

    if task_in.status is TaskStatus.DONE and crud.has_open_subtasks(
        session=session, task=task
    ):
        if task_in.subtasks is None:
            raise refusals.task_has_uncompleted_subtasks(
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
    if (
        not already_done
        and task.status is TaskStatus.DONE
        and task.series_id is not None
    ):
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


@dataclass(frozen=True)
class CreateResult:
    """
    What filing a task produced (#275, #281): the task exactly as
    `crud.create_task` left it, and the project it landed in.

    The project rides along rather than being read back off the task,
    because a subtask's own row carries none — it derives its project from
    its parent's tree (FR-01.2) — so whoever shapes the response (`app.api.
    routes.tasks.create_task`, `app.mcp.tools.create_task`) would otherwise
    have to walk that tree a second time for exactly what this operation
    already resolved to decide access.
    """

    task: Task
    project: Project


def _reporter(caller: Caller) -> crud.Reporter:
    """
    Who is filing this task: the caller, and nobody the request can name
    instead (FR-01.29). A bot user's work is recorded as its own, never as
    its owner's, so the two are never interchangeable here.
    """
    if caller.bot is not None:
        return crud.Reporter(bot_user_id=caller.bot.id)
    return crud.Reporter(user_id=caller.owner_id)


def create(session: Session, caller: Caller, task_in: TaskCreate) -> CreateResult:
    """
    File a task, or a subtask of one (FR-01.1, FR-01.2, #281) — `create`'s
    own act, alongside `complete`'s (#279): decides access itself, rather
    than taking it as already settled, and sets the activity actor itself
    from `caller`, the same way `complete` does.

    Where the task lands is settled first, so a bot user is refused by its
    scope, and anyone by the archive, before anything about the request
    itself is looked at: no project names the Inbox, which has to be in a
    bot's scope like any other project; a subtask instead takes its
    parent's own project, and naming `project_id` alongside `parent_id` is
    refused rather than picked between.

    A task starts in `backlog` unless `task_in.status` names another. A
    recurring task needs a due date, must be a root task, and cannot be
    created done (`_check_recurrence`). The assignee is the owner or one of
    the owner's bot users, and a deleted bot user takes no new task
    (`resolve_task_assignee`, FR-01.7, FR-08.21). A tag name that is not one
    of the owner's yet needs the `create_tags` grant
    (`access.authorize_tag_names`), and the refusal names which names were
    new.

    The reporter is the caller itself (FR-01.29): nothing in `task_in` can
    set it — the request body this takes has no field for it at all.
    """
    set_caller_actor(session, caller)

    is_subtask = task_in.parent_id is not None
    if task_in.parent_id is not None:
        project = access.get_task(
            session, caller, task_in.parent_id, TaskAction.CREATE
        ).project
    elif task_in.project_id is not None:
        project = access.get_project(
            session, caller, task_in.project_id, TaskAction.CREATE
        )
    else:
        project = access.get_project(
            session,
            caller,
            crud.get_inbox_project(session=session, owner_id=caller.owner_id).id,
            TaskAction.CREATE,
        )
    tag_names = _unique_tag_names(task_in.tags)
    access.authorize_tag_names(session, caller, tag_names)

    assignee = resolve_task_assignee(session, caller, task_in.assignee_id)
    _check_recurrence(
        parent_id=task_in.parent_id,
        recurrence=task_in.recurrence,
        due_date=task_in.due_date,
        status=task_in.status,
    )

    if is_subtask and task_in.project_id is not None:
        raise refusals.plain(400, "A subtask belongs to the project of its parent")

    task = crud.create_task(
        session=session,
        task_create=task_in,
        # A subtask's own project is derived from its parent's tree.
        project_id=None if is_subtask else project.id,
        owner_id=caller.owner_id,
        reporter=_reporter(caller),
        assignee=assignee,
        tag_names=tag_names,
    )
    return CreateResult(task=task, project=project)


@dataclass(frozen=True)
class UpdateResult:
    """
    What changing a task — short of closing it — produced (#275, #282): the
    task exactly as `crud.update_task` left it, the project it belongs to
    now (so a caller never re-derives where it landed after a move), and the
    recurrence `_check_recurrence_update` already read while deciding
    whether a due-date move needed a scope (so a caller never reads it back
    a second time just to report it).

    Never what `update` returns for a request that closes the task: that
    case is `complete`'s own act, delegated to whole, and `CompleteResult`
    is what comes back instead.
    """

    task: Task
    project: Project
    recurrence: Recurrence | None


def update(
    session: Session, caller: Caller, task_id: uuid.UUID, task_in: TaskUpdate
) -> UpdateResult | CompleteResult:
    """
    Change a task: its fields, status between open ones, assignee, or
    project — every rule `PATCH /tasks/{id}` has ever enforced, now this
    operation's own (#275, #282) rather than split between a route and the
    helpers above it used to reach across this module's own boundary for.

    A request that moves `status` to `done` is `complete`'s own act (#279):
    delegated to it whole, `task_in` unchanged, and its result
    (`CompleteResult`) returned exactly as `complete` left it — the
    open-subtasks directive, the next occurrence a recurring close spawns,
    and an optional comment are all `complete`'s rules, not repeated here.

    Every other request is this operation's own: the due-date scope an open
    occurrence's move needs and the superseded-occurrence refusal
    (`_check_recurrence_update`, FR-01.16, FR-01.17), a task belonging to a
    project and a subtask following its parent's tree rather than moving on
    its own, moving into or out of a bot's scope (`access.get_project`),
    tags replacing wholesale, the assignee rules (`resolve_task_assignee`,
    FR-01.7, FR-08.21) — and refusing `subtasks` on a request that closes
    nothing, since that argument only ever answers the question closing
    asks.
    """
    if task_in.status is TaskStatus.DONE:
        return complete(session, caller, task_id, task_in)

    set_caller_actor(session, caller)

    resolved = access.get_task(session, caller, task_id, TaskAction.UPDATE)
    task, project = resolved.task, resolved.project

    tag_names = _unique_tag_names(task_in.tags) if task_in.tags is not None else None
    access.authorize_tag_names(session, caller, tag_names)
    recurrence = _check_recurrence_update(session=session, task=task, task_in=task_in)

    if "project_id" in task_in.model_fields_set:
        if task_in.project_id is None:
            raise refusals.plain(400, "A task must belong to a project")
        if task.parent_id is not None:
            raise refusals.plain(
                400,
                "A subtask follows its parent's project; move the task at "
                "the top of the tree instead",
            )
        # Moving a task in is as much a change to the destination as creating
        # one there. For a bot the source was checked with the task, so work
        # can neither leave its scope nor enter from outside it.
        project = access.get_project(
            session, caller, task_in.project_id, TaskAction.UPDATE
        )

    assignee = None
    if "assignee_id" in task_in.model_fields_set:
        assignee = resolve_task_assignee(
            session,
            caller,
            task_in.assignee_id,
            current=crud.Assignee(task.assignee_id, task.assignee_bot_user_id),
        )

    if task_in.subtasks is not None:
        # `status: done` returned above before this line is ever reached, so
        # a `subtasks` sent here is never paired with it.
        raise refusals.plain(
            400, "`subtasks` only applies to a request that moves the task to done"
        )

    task = crud.update_task(
        session=session,
        db_task=task,
        task_in=task_in,
        assignee=assignee,
        tag_names=tag_names,
    )
    return UpdateResult(task=task, project=project, recurrence=recurrence)


def delete(
    session: Session,
    caller: Caller,
    task_id: uuid.UUID,
    delete_subtasks: bool = False,
) -> Task:
    """
    Delete a task, and its subtasks with it (FR-01.8, FR-01.11, FR-01.12,
    #275, #282).

    Decides access itself (`app.api.access.get_task`), the same as every
    other operation. A task with subtasks is refused until `delete_subtasks`
    confirms the cascade; the refusal carries the whole live subtree — done
    descendants included, since the cascade takes them along with the open
    ones (`crud.subtasks`, not `crud.open_subtasks`, which only reads what
    `complete`'s own refusal needs) — so a caller that wants to name them
    (`app.mcp.tools.delete_task`) reads them off the refusal itself, never
    with a subtree query of its own.

    Recorded as one event over the whole subtree (`app.deletions.
    delete_task`), restorable as the one act it was, and only by the owner —
    restoring is `app.deletions.restore`'s own rule, unchanged by this
    operation existing.
    """
    set_caller_actor(session, caller)
    task = access.get_task(session, caller, task_id, TaskAction.DELETE).task
    if not delete_subtasks and crud.has_subtasks(session=session, task=task):
        raise refusals.task_has_subtasks(crud.subtasks(session=session, task=task))
    deletions.delete_task(session, task)
    return task


__all__ = [
    "CompleteResult",
    "CreateResult",
    "UpdateResult",
    "complete",
    "create",
    "delete",
    "resolve_task_assignee",
    "update",
]
