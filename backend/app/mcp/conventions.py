"""
The argument, output and refusal conventions every MCP tool shares (spec
#247, settled here by #253 against `search_tasks`, the first tool that
needs all of them). A tool after this one (#254 on) imports from here
rather than re-deriving its own version of any of these rules:

- **A caller, per call.** `open_caller` reads the bearer token and resolves
  it through `get_mcp_caller` again, the same way `app.mcp.gateway`'s own
  check did a moment earlier — nothing about a caller is cached (ADR-0012),
  so a scope edited between two calls shows in the second.
- **Ids.** `resolve_task_id` accepts a full id or the short prefix a
  compact line prints (`short_id`); an ambiguous prefix is refused with the
  candidates rather than guessed at.
- **Names.** `resolve_project` and `resolve_tag_name` accept a project or a
  tag by name, case-insensitively, as well as by id; an ambiguous project
  name is refused with the matching ids, since project names are not
  unique (tags are, so an ambiguous tag name only happens between two that
  differ by letter case alone). `resolve_project_id` is `resolve_project`
  without the access decision, for a caller that defers that decision to
  somewhere else (`create_task` (#255), to the route it calls through to).
- **Dates.** `resolve_date` reads an ISO date, `today`, `tomorrow` and
  `+<count>d`, against the server's own date.
- **Nulls.** Refused before any of the above runs at all —
  `app.mcp.server._RefuseNullArguments` is the `tools/call` interceptor
  that does it, once, for every tool's arguments.
- **Lists.** `render_task_rows` and `list_result` build the compact lines
  every tool that returns several tasks uses, with the total and, when the
  page did not hold all of them, the filter that would narrow it.
- **Refusals.** `refuse` and `refusal` turn a deliberate refusal, or an
  `HTTPException` from `app.api.access`/`app.crud`, into the one thing a
  tool ever raises to report one: a `ToolError` carrying the API's own code
  and one sentence saying what to do next — never a bare status code.
"""

import re
import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Any, NoReturn

from fastapi import HTTPException
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy import Text, cast
from sqlmodel import Session, col, func, select

from app import crud
from app.api import access
from app.api.access import TaskAction
from app.api.deps import Caller, get_mcp_caller
from app.core.db import engine
from app.crud import archived_task_ids, not_deleted, tasks_in_projects
from app.models import Project, Tag, Task

# Refusals


def refuse(code: str, message: str) -> NoReturn:
    """A tool's own deliberate refusal: the API's own code, plus one sentence saying what to do next."""
    raise ToolError(f"{code}: {message}")


# A plain-string `detail` (every 404 in `app.api.access`, and the stray 400s
# routes raise inline) never carried a machine-readable code before a human
# reading JSON was the only audience; a tool call needs one anyway.
_DEFAULT_CODE = {400: "invalid_argument", 404: "not_found", 422: "invalid_argument"}


def refusal(exc: HTTPException) -> ToolError:
    """
    An `HTTPException` from `app.api.access` or `app.crud`, read the way a
    tool reports a refusal: the code it already carries (a dict `detail`,
    every 403/409 in this codebase), or a sensible one for a plain-string
    `detail` that never needed one before this had to read it back out —
    plus the one sentence either way, never the bare status code.
    """
    detail = exc.detail
    if isinstance(detail, Mapping):
        code = str(detail.get("code", _DEFAULT_CODE.get(exc.status_code, "error")))
        message = str(detail.get("message", detail))
    else:
        code = _DEFAULT_CODE.get(exc.status_code, "error")
        message = str(detail)
    return ToolError(f"{code}: {message}")


# The caller, per call


def bearer_token(headers: Mapping[str, str] | None) -> str:
    """
    The bearer token of an MCP request, read the way `ctx.headers` carries
    it — a tool never trusts it as an identity on its own (`Context.headers`'
    own warning); `get_mcp_caller` is what actually resolves it.
    """
    header = "" if headers is None else headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


@contextmanager
def open_caller(ctx: Context) -> Iterator[tuple[Session, Caller]]:
    """
    A fresh `Session` and the caller it resolves to, for a tool body. Every
    tool calls this itself rather than trusting what `app.mcp.gateway`
    already checked on the same request: nothing about a caller is cached
    between calls (ADR-0012), so a scope edited since then still shows here,
    and a tool stays callable as a complete unit on its own.
    """
    with Session(engine) as session:
        try:
            token = bearer_token(ctx.headers)
            caller = get_mcp_caller(session, token)
        except HTTPException as exc:
            raise refusal(exc) from exc
        yield session, caller


# Ids


def short_id(task_id: uuid.UUID) -> str:
    """
    The id a compact line prints (spec #247): the task id's first 8 hex
    characters, dashes dropped — enough to pick one task out of a short list
    and quote straight back into `resolve_task_id`, without spending a whole
    UUID's width on every line.
    """
    return task_id.hex[:8]


def resolve_task_id(session: Session, caller: Caller, raw: str) -> uuid.UUID:
    """
    A task id, the way every tool that names one reads it: a full id, or the
    short prefix a compact line prints instead.

    A prefix is matched only among tasks this caller could otherwise reach —
    live, unarchived, and (a bot always) inside its scope — so an ambiguous
    prefix's candidates never name a task `app.api.access` would refuse
    outright anyway; that refusal still happens afterwards, on whichever id
    this resolves to, so a found task's own permission and archive rules are
    never bypassed by having been named this way instead of by its full id.
    """
    try:
        return uuid.UUID(raw)
    except ValueError:
        pass

    hex_id = func.replace(cast(col(Task.id), Text), "-", "")
    conditions: list[Any] = [
        Task.owner_id == caller.owner_id,
        not_deleted(Task),
        ~col(Task.id).in_(archived_task_ids(caller.owner_id)),
        hex_id.ilike(f"{raw.lower()}%"),
    ]
    if caller.bot is not None:
        conditions.append(col(Task.id).in_(tasks_in_projects(caller.project_ids)))
    candidates = session.exec(
        select(Task.id, Task.title).where(*conditions).order_by(col(Task.created_at))
    ).all()

    if not candidates:
        refuse("not_found", f"No task's id starts with “{raw}”.")
    if len(candidates) > 1:
        listed = "; ".join(f"{task_id} “{title}”" for task_id, title in candidates)
        refuse(
            "ambiguous_id",
            f"“{raw}” matches {len(candidates)} tasks: {listed}. Use the full id.",
        )
    return candidates[0][0]


# Names


def resolve_project_id(session: Session, caller: Caller, raw: str) -> uuid.UUID:
    """
    Which project `raw` names, by a full id or by name case-insensitively —
    the half of `resolve_project` that only decides which project was meant,
    with no access decision made yet. `create_task` (#255) uses this on its
    own for a root task's `project`, deferring the access decision itself to
    `app.api.routes.tasks.create_task`, the route it calls through to; a
    subtask that also names a project is refused before any name needs
    resolving at all, so that refusal never reaches here.
    """
    try:
        return uuid.UUID(raw)
    except ValueError:
        return _project_id_by_name(session, caller.owner_id, raw)


def resolve_project(
    session: Session, caller: Caller, raw: str, action: TaskAction
) -> Project:
    """
    A project, by a full id or by name, case-insensitively — project names
    are not unique, so a name matching more than one is refused with their
    ids rather than picked between. Either way, `app.api.access.get_project`
    makes the real decision (not found, outside scope, archived, lacking the
    permission): this only decides which project the caller meant.
    """
    project_id = resolve_project_id(session, caller, raw)
    return access.get_project(session, caller, project_id, action)


def _project_id_by_name(session: Session, owner_id: uuid.UUID, name: str) -> uuid.UUID:
    matches = session.exec(
        select(Project.id).where(
            Project.owner_id == owner_id,
            not_deleted(Project),
            func.lower(col(Project.name)) == name.lower(),
        )
    ).all()
    if not matches:
        refuse("not_found", f"No project is named “{name}”.")
    if len(matches) > 1:
        ids = ", ".join(str(project_id) for project_id in matches)
        refuse(
            "ambiguous_project_name",
            f"“{name}” names {len(matches)} projects: {ids}. Use one of their ids.",
        )
    return matches[0]


def resolve_tag_name(session: Session, owner_id: uuid.UUID, raw: str) -> str:
    """
    A tag's own stored name, by a full id or by name, case-insensitively —
    tags belong to the owner alone (FR-08.9), never narrowed by a bot's
    scope. An exact match wins outright; two tags differing only by letter
    case are refused the way an ambiguous project name is. A name (or id)
    that is not a tag at all is not a refusal: filtering by it is simply a
    filter nothing satisfies, the same as the REST API's own `tag` filter
    already behaves for a name it has never heard of — so the raw text is
    returned unchanged, to go on narrowing to nothing.
    """
    try:
        tag_id = uuid.UUID(raw)
    except ValueError:
        tag_id = None
    if tag_id is not None:
        tag = session.get(Tag, tag_id)
        return tag.name if tag is not None and tag.owner_id == owner_id else raw

    exact = session.exec(
        select(Tag.name).where(Tag.owner_id == owner_id, Tag.name == raw)
    ).first()
    if exact is not None:
        return exact
    matches = session.exec(
        select(Tag.name).where(
            Tag.owner_id == owner_id, func.lower(col(Tag.name)) == raw.lower()
        )
    ).all()
    if len(matches) > 1:
        refuse(
            "ambiguous_tag_name",
            f"“{raw}” names {len(matches)} tags that differ only by letter "
            f"case: {', '.join(matches)}. Use the exact name.",
        )
    return matches[0] if matches else raw


# Dates

_PLUS_DAYS = re.compile(r"\+(\d+)d")


def resolve_date(raw: str) -> date:
    """
    A date, the way every tool that takes one reads it (spec #247): an ISO
    date, `today`, `tomorrow`, or `+<count>d`, resolved against the server's own
    date — the caller's clock is not this installation's, and a due date is
    a date with no time of day.
    """
    if raw == "today":
        return date.today()
    if raw == "tomorrow":
        return date.today() + timedelta(days=1)
    if (plus_days := _PLUS_DAYS.fullmatch(raw)) is not None:
        return date.today() + timedelta(days=int(plus_days.group(1)))
    try:
        return date.fromisoformat(raw)
    except ValueError:
        refuse(
            "invalid_date",
            f"“{raw}” is not a date. Use an ISO date (YYYY-MM-DD), “today”, "
            "“tomorrow”, or “+<count>d”.",
        )


# Lists


def render_task_rows(
    session: Session, tasks: Sequence[Task], owner_id: uuid.UUID
) -> list[dict[str, Any]]:
    """
    `tasks` as a compact line each (spec #247): id, status, priority, due
    date, title, project, tags and subtask counts — never a full record,
    which only `get_task` and the tools that write return.
    """
    if not tasks:
        return []
    task_ids = [task.id for task in tasks]
    project_ids = crud.get_task_project_ids(
        session=session, owner_id=owner_id, task_ids=task_ids
    )
    projects = {
        project.id: project.name
        for project in session.exec(
            select(Project).where(col(Project.id).in_(set(project_ids.values())))
        ).all()
    }
    tags = crud.get_task_tags(session=session, task_ids=task_ids)
    subtasks = crud.get_subtask_counts(session=session, task_ids=task_ids)

    rows = []
    for task in tasks:
        counts = subtasks.get(task.id)
        project_id = project_ids.get(task.id)
        row: dict[str, Any] = {
            "id": short_id(task.id),
            "status": task.status.value,
            "priority": task.priority.value if task.priority is not None else None,
            "due_date": task.due_date.isoformat()
            if task.due_date is not None
            else None,
            "title": task.title,
            "project": projects.get(project_id) if project_id is not None else None,
            "tags": tags.get(task.id, []),
        }
        if counts is not None and counts.total:
            row["subtasks"] = {"total": counts.total, "done": counts.done}
        rows.append(row)
    return rows


def list_result(
    rows: list[dict[str, Any]], *, count: int, offset: int, narrow_with: str | None
) -> dict[str, Any]:
    """
    The envelope a tool that returns several tasks replies with (spec #247):
    the compact rows, the total the filters matched (not just this page),
    and, only when the page did not hold all of them, the filter that would
    narrow it — named by the caller, since only it knows which of its own
    arguments is still free to narrow with.
    """
    result: dict[str, Any] = {"tasks": rows, "count": count}
    if offset + len(rows) < count:
        result["truncated"] = True
        if narrow_with is not None:
            result["narrow_with"] = narrow_with
    return result
