"""
`search_tasks` (spec #247, #253): the task list's own narrowing (F-06), read
by an agent as one call instead of a `GET /tasks` query string. Every
convention the rest of this slice's tools (and the six after it) share is
exercised here first — see `app.mcp.conventions` for what each one means;
this module only maps `search_tasks`'s own arguments onto them and onto
`app.models.TaskQuery`, the same query `app.api.routes.tasks.read_tasks`
already runs.

**`status` and `open_only`.** `status` accepts any of the six fixed statuses
(ADR-0004), matching `TaskQuery.status` exactly — no narrowing invented that
the task list does not have. `open_only` (true by default, FR-06.8's own
baseline) additionally excludes `done` from whatever `status` says; set it
to `false` to reach `done` work too, the one way `search_tasks` differs from
the task list a human reads, which cannot show `done` at all (completed work
is otherwise the activity log's, a later ticket's tool). A `status` left
entirely outside what `open_only` allows (`status=["done"]` with the default
`open_only=true`) can never match anything, so the tool answers an empty
list rather than asking the database a query that would always come back
empty too.

**`preset`.** Each one is a name for filters `search_tasks` already has
(`ready_for_me`: `status=["todo"], assignee="self"`; `my_overdue`:
`assignee="self", overdue=true`; `recently_filed`:
`sort="created_at", order="desc"`) — never a narrowing of its own. Setting a
filter a preset already sets is refused rather than silently overridden
either way, the same "never resolved by guessing" rule an ambiguous id or
project name follows.
"""

import uuid
from enum import StrEnum
from typing import Annotated, Any

from fastapi import HTTPException
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError

from app import crud
from app.api import access
from app.api.access import TaskAction
from app.api.deps import Caller
from app.mcp.conventions import (
    list_result,
    open_caller,
    refusal,
    refuse,
    render_task_rows,
    resolve_date,
    resolve_project,
    resolve_tag_name,
    resolve_task_id,
)
from app.mcp.server import mcp_server
from app.models import SortOrder, TaskPriority, TaskQuery, TaskSort, TaskStatus

# The five statuses the task list itself ever shows (FR-06.8); `done` leaves
# the list the moment a task reaches it (ADR-0006) and is never filtered for
# there, so it is never in this set — see `_effective_status`.
_OPEN_STATUSES = frozenset(
    {
        TaskStatus.BACKLOG,
        TaskStatus.TODO,
        TaskStatus.IN_PROGRESS,
        TaskStatus.REVIEW,
        TaskStatus.WAITING,
    }
)


class SearchAssignee(StrEnum):
    """Who a task is assigned to, named the way an agent asks rather than by id (spec #247)."""

    SELF = "self"
    OWNER = "owner"
    ANY_BOT = "any_bot"
    NOBODY = "nobody"
    ANY = "any"


class SearchPreset(StrEnum):
    """A name for a combination of filters `search_tasks` already has (spec #247)."""

    READY_FOR_ME = "ready_for_me"
    MY_OVERDUE = "my_overdue"
    RECENTLY_FILED = "recently_filed"


class _NoPossibleMatch(Exception):
    """
    `status` and `open_only` together can never match a task (e.g.
    `status=["done"]` with `open_only` left at its default `true`) — a
    narrowing to nothing, not a mistake, so it is answered with an empty
    list rather than refused.
    """


@mcp_server.tool(
    annotations=ToolAnnotations(read_only_hint=True),
)
def search_tasks(
    ctx: Context,
    query: str | None = None,
    project: str | None = None,
    status: list[TaskStatus] | None = None,
    open_only: bool = True,
    assignee: SearchAssignee | None = None,
    tag: str | None = None,
    priority: TaskPriority | None = None,
    due_before: str | None = None,
    due_after: str | None = None,
    overdue: bool = False,
    parent_task_id: str | None = None,
    preset: SearchPreset | None = None,
    sort: TaskSort | None = None,
    order: SortOrder | None = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> dict[str, Any]:
    """
    Find tasks by title text, project, status, assignee, tag, priority, due
    date, overdue-ness and parent task, ordered the way the task list orders
    (`sort`/`order`), or by a ready-made `preset`. Combining filters narrows:
    a task is listed only if it satisfies every one set.

    `project` and `tag` take a name, case-insensitively, as well as an id.
    `parent_task_id` takes a full id or the short prefix a compact line's
    own `id` prints. `due_before`/`due_after` take an ISO date, `today`,
    `tomorrow`, or `+<count>d`, read against the server's date.

    Results are compact lines — id, status, priority, due date, title,
    project, tags, subtask counts — never full records; `get_task` reads
    one in full. `count` is every task the filters matched, not only this
    page; a `truncated` answer names the one filter (`narrow_with`) still
    free to ask again with.
    """
    if preset is not None:
        _refuse_preset_conflicts(
            preset,
            status=status,
            assignee=assignee,
            overdue=overdue,
            sort=sort,
            order=order,
        )
        status, assignee, overdue, sort, order = _apply_preset(
            preset,
            status=status,
            assignee=assignee,
            overdue=overdue,
            sort=sort,
            order=order,
        )

    try:
        effective_status = _effective_status(status, open_only)
    except _NoPossibleMatch:
        return list_result([], count=0, offset=offset, narrow_with=None)

    with open_caller(ctx) as (session, caller):
        try:
            project_id = None
            if project is not None:
                project_id = resolve_project(
                    session, caller, project, TaskAction.READ
                ).id
            else:
                access.authorize_tasks(caller, TaskAction.READ)

            parent_id = None
            if parent_task_id is not None:
                parent_id = resolve_task_id(session, caller, parent_task_id)
                # `resolve_task_id` only decided which task was meant;
                # `access` still makes the real decision (outside the
                # scope, archived, lacking the permission).
                access.get_task(session, caller, parent_id, TaskAction.READ)

            tag_name = (
                resolve_tag_name(session, caller.owner_id, tag)
                if tag is not None
                else None
            )
            due_before_date = (
                resolve_date(due_before) if due_before is not None else None
            )
            due_after_date = resolve_date(due_after) if due_after is not None else None
            assignee_id, unassigned, assigned_to_bots = _assignee_filters(
                assignee, caller
            )

            built_query = TaskQuery(
                title=query,
                project_id=project_id,
                parent_id=parent_id,
                assignee_id=assignee_id,
                unassigned=unassigned,
                assigned_to_bots=assigned_to_bots,
                tag=tag_name,
                priority=priority,
                status=effective_status,
                due_from=due_after_date,
                due_to=due_before_date,
                overdue=overdue,
                sort=sort,
                order=order,
                skip=offset,
                limit=limit,
            )
        except HTTPException as exc:
            raise refusal(exc) from exc
        except ValidationError as exc:
            first = exc.errors()[0]
            field = ".".join(str(part) for part in first["loc"])
            refuse("invalid_argument", f"{field}: {first['msg']}")

        tasks, count = crud.get_tasks(
            session=session,
            owner_id=caller.owner_id,
            query=built_query,
            project_ids=caller.project_ids if caller.bot else None,
        )
        rows = render_task_rows(session, tasks, caller.owner_id)

    narrow_with = _narrow_hint(
        project=project,
        status=status,
        assignee=assignee,
        tag=tag,
        priority=priority,
        due_before=due_before,
        due_after=due_after,
    )
    return list_result(rows, count=count, offset=offset, narrow_with=narrow_with)


def _effective_status(
    status: list[TaskStatus] | None, open_only: bool
) -> list[TaskStatus] | None:
    """
    `status` as `TaskQuery` should see it, once `open_only` has had its say.
    `None` means "every status" to `TaskQuery` (an empty list is falsy and
    would mean the same, so a narrowing to nothing cannot be spelled as one
    — `_NoPossibleMatch` is raised instead, which the caller turns into an
    empty result rather than a query that would always come back empty too).
    """
    if not open_only:
        return status
    if status is None:
        return list(_OPEN_STATUSES)
    narrowed = [one for one in status if one in _OPEN_STATUSES]
    if not narrowed:
        raise _NoPossibleMatch()
    return narrowed


def _assignee_filters(
    assignee: SearchAssignee | None, caller: Caller
) -> tuple[uuid.UUID | None, bool, bool]:
    """`assignee` as the three `TaskQuery` fields it resolves to: `assignee_id`, `unassigned`, `assigned_to_bots`."""
    if assignee is None or assignee is SearchAssignee.ANY:
        return None, False, False
    if assignee is SearchAssignee.SELF:
        # Every MCP caller is a bot (`get_mcp_caller` never returns one that
        # is not): "self" names the bot the connecting token belongs to.
        assert caller.bot is not None, "an MCP caller is always a bot"
        return caller.bot.id, False, False
    if assignee is SearchAssignee.OWNER:
        return caller.owner_id, False, False
    if assignee is SearchAssignee.ANY_BOT:
        return None, False, True
    return None, True, False  # NOBODY


_PRESET_FILTERS: dict[SearchPreset, tuple[str, ...]] = {
    SearchPreset.READY_FOR_ME: ("status", "assignee"),
    SearchPreset.MY_OVERDUE: ("assignee", "overdue"),
    SearchPreset.RECENTLY_FILED: ("sort", "order"),
}


def _refuse_preset_conflicts(
    preset: SearchPreset,
    *,
    status: list[TaskStatus] | None,
    assignee: SearchAssignee | None,
    overdue: bool,
    sort: TaskSort | None,
    order: SortOrder | None,
) -> None:
    """
    A preset is a name for the filters it stands for (spec #247); setting
    one of those same filters by hand in the same call is a contradiction
    this tool refuses rather than silently picking a side of.
    """
    set_args = {
        "status": status is not None,
        "assignee": assignee is not None,
        "overdue": overdue,
        "sort": sort is not None,
        "order": order is not None,
    }
    conflicts = [name for name in _PRESET_FILTERS[preset] if set_args[name]]
    if conflicts:
        named = " and ".join(f"`{name}`" for name in conflicts)
        refuse(
            "preset_conflict",
            f"`preset={preset.value}` already sets {named}. Ask for the "
            "preset or for its own filters, not both.",
        )


def _apply_preset(
    preset: SearchPreset,
    *,
    status: list[TaskStatus] | None,
    assignee: SearchAssignee | None,
    overdue: bool,
    sort: TaskSort | None,
    order: SortOrder | None,
) -> tuple[
    list[TaskStatus] | None,
    SearchAssignee | None,
    bool,
    TaskSort | None,
    SortOrder | None,
]:
    """The filters `preset` stands for, equivalent to setting them by hand (spec #247)."""
    if preset is SearchPreset.READY_FOR_ME:
        return [TaskStatus.TODO], SearchAssignee.SELF, overdue, sort, order
    if preset is SearchPreset.MY_OVERDUE:
        return status, SearchAssignee.SELF, True, sort, order
    return (
        status,
        assignee,
        overdue,
        TaskSort.CREATED_AT,
        SortOrder.DESC,
    )  # RECENTLY_FILED


def _narrow_hint(
    *,
    project: str | None,
    status: list[TaskStatus] | None,
    assignee: SearchAssignee | None,
    tag: str | None,
    priority: TaskPriority | None,
    due_before: str | None,
    due_after: str | None,
) -> str | None:
    """
    The one filter, among those not already set, most likely to turn a
    truncated answer into a complete one — named, not applied, so the
    caller stays the one deciding what it actually meant.
    """
    if project is None:
        return "project"
    if not status:
        return "status"
    if assignee is None:
        return "assignee"
    if tag is None:
        return "tag"
    if priority is None:
        return "priority"
    if due_before is None and due_after is None:
        return "due_before or due_after"
    return None
