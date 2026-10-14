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
  somewhere else (`create_task` (#255), `update_task` (#256), to the route
  each calls through to). `resolve_task_id`, `resolve_project_id`,
  `resolve_tag_name` and the bot-name half of `resolve_actor` (below) are
  four variants of the same algorithm — try a uuid, else match a name or
  prefix case-insensitively, refuse with the candidates if ambiguous — and
  share `_resolve_by_name` for exactly that part (#301); each stays its own
  public function because they genuinely differ at the one step the shared
  helper does not own: what a resolved id means to its own caller, and what
  no match at all means (a refusal for a task, a project or a bot user; a
  pass-through, for a tag, since a tag name is a filter, not a reference).
- **Assignees.** `resolve_assignee` reads `self`, `owner` or a bot user's
  id, the way `create_task` (#255) and `update_task` (#256) both take one;
  whether the bot it names is really one of this owner's, and not deleted,
  is still the route's own decision a moment later.
- **Actors.** `resolve_actor` reads `self`, `owner`, `any_bot`, or a sibling
  bot user by name or id, the way `search_activity` (#259) and
  `list_completions` (#260) both narrow by who acted; moved here once a
  second tool needed the exact same reading rather than its own copy.
  `actor_label` is the other half of the same convention, read backwards:
  who a recorded actor turns out to have been, "owner" or a bot user by
  name, "(deleted)" appended if it no longer exists (FR-08.19) — shared by
  `search_activity`, `list_completions` and `get_task`'s own comment rows
  rather than three copies of the same two lines (#301).
- **Dates.** `resolve_date` reads an ISO date, `today`, `tomorrow` and
  `+<count>d`, against the server's own date. `since_datetime`/
  `until_datetime` widen such a date to the whole day it names, the way
  `search_activity` and `list_completions` both read a period's two bounds.
- **Nulls.** Refused before any of the above runs at all —
  `app.mcp.server._RefuseNullArguments` is the `tools/call` interceptor
  that does it, once, for every tool's arguments.
- **Lists.** `render_task_rows` and `list_result` build the compact lines
  every tool that returns several tasks uses, with the total and, when the
  page did not hold all of them, the filter that would narrow it.
  `narrow_hint` is what names that filter: the first, in the order its own
  caller lists them, among a tool's own filters that is still unset — one
  function three tools each call with their own priority order, rather
  than three copies of the same loop (#301).
- **Refusals.** `refuse` and `refusal` turn a deliberate refusal — an
  `app.refusals.Refusal`, raised by an operation (#279), by `app.access`
  itself (#309), or, since #322, by `app.activity_log`'s own task/project
  narrowing too, now that it reaches `app.access` for that rule rather than
  raising `HTTPException` inline — into the one thing a tool ever raises to
  report one: a `ToolError` carrying the refusal's own code and one sentence
  saying what to do next — never a bare status code, and never a guess at a
  `Refusal`'s code, which it already carries. `refusal` still also reads a
  plain `HTTPException`, the shape authentication answers in
  (`app.api.deps`, raised before a tool body is even reached) — the one
  place below `app.api` nothing moved off it (#322): signing in is answered
  the same way whichever front door asks, and `app.api.deps` is itself one
  of the two front doors' own wiring, not a layer below either (`tests/
  migrations/test_layering.py`). Every tool body's own `except` now reads
  `Refusal` alone; only `open_caller`'s still reads `HTTPException` too.
"""

import re
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, NoReturn, Protocol

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
from app.models import BotUser, BotUserRef, Project, Tag, Task
from app.refusals import Refusal

# Refusals


def refuse(code: str, message: str) -> NoReturn:
    """A tool's own deliberate refusal: the API's own code, plus one sentence saying what to do next."""
    raise ToolError(f"{code}: {message}")


# A plain-string `detail` (every bare-string `app.refusals.plain`, and the
# stray 400s a route raises inline) never carried a machine-readable code
# before a human reading JSON was the only audience; a tool call needs one
# anyway.
_DEFAULT_CODE = {400: "invalid_argument", 404: "not_found", 422: "invalid_argument"}


def refusal(exc: HTTPException | Refusal) -> ToolError:
    """
    A refusal, read the way a tool reports one: an `app.refusals.Refusal`
    (raised by an operation, `app.tasks` and its siblings, by `app.access`
    itself since #309, or by `app.activity_log`'s own task/project narrowing
    since #322, which now reaches `app.access` for that rule too) reads its
    own `code` and `message` straight off, the typed vocabulary #279
    introduced for exactly this — unless `code` is `None`, the shape #282
    taught this module too, for a refusal pinned as a bare string
    (`app.refusals.plain`): read the same way a code-less `HTTPException`
    already was, guessed from its status, since an MCP call needs one either
    way. An `HTTPException` is, since #322, only ever the one authentication
    gives (`app.api.deps`, read by `open_caller` before a tool body even
    starts) — nothing below `app.api` raises one any more
    (`tests/migrations/test_layering.py` asserts it) — still read the same
    way: its code out of a dict `detail` where it carries one, or guessed
    from its status for a plain-string `detail`. Either way, one sentence,
    never the bare status code.
    """
    if isinstance(exc, Refusal):
        code = (
            exc.code.value
            if exc.code is not None
            else _DEFAULT_CODE.get(exc.status, "error")
        )
        return ToolError(f"{code}: {exc.message}")
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

    A recurring misreading, worth heading off here: a tool body that
    validates its own arguments *before* calling this (a preset conflict, a
    parent/project conflict) is not skipping authentication to do it.
    `app.mcp.gateway`'s `_BotGateway.__call__` resolves the bearer token and
    denies the request before any MCP message on it is read at all, so an
    unauthenticated call never reaches a tool body in the first place — the
    order a body validates its own arguments in never precedes that check,
    whichever side of this call it runs on.
    """
    with Session(engine) as session:
        try:
            token = bearer_token(ctx.headers)
            caller = get_mcp_caller(session, token)
        except HTTPException as exc:
            raise refusal(exc) from exc
        yield session, caller


# Resolving by id or by name


@dataclass(frozen=True)
class _Table[T]:
    """
    What `_resolve_by_name` matches `raw` against once it does not parse as
    a bare uuid, and what its own ambiguity refusal says about it: `by_id`
    turns an id that did parse into what it names (`None` for one that
    names nothing this owner has — only `resolve_tag_name` ever reads one
    back this way, since the other three callers defer whether a parsed id
    is real to whoever resolves it next); `candidates` runs the actual
    name-or-prefix match and returns each hit paired with how the refusal
    below lists it; `noun`, `ambiguous_code` and `instruction` are the code
    and the words that refusal's own message uses. `separator` joins the
    candidates' own labels — `resolve_task_id`'s own labels carry a title,
    which can itself contain a comma, so it joins with `"; "` rather than
    the default `", "` a bare id never needs escaping from.
    """

    by_id: Callable[[uuid.UUID], T | None]
    candidates: Callable[[], Sequence[tuple[T, str]]]
    noun: str
    ambiguous_code: str
    instruction: str = "Use one of their ids."
    separator: str = ", "


def _resolve_by_name[T](raw: str, table: _Table[T], not_found: Callable[[], T]) -> T:
    """
    The one algorithm `resolve_task_id`, `resolve_project_id`,
    `resolve_tag_name` and the bot-name half of `resolve_actor` each used
    to write out on their own (#301): try `raw` as a uuid; failing that,
    run `table`'s own case-insensitive match; refuse with every candidate
    listed if more than one comes back, in the one shared shape ("“raw”
    names N <noun>: <candidates>. <instruction>") an ambiguous prefix, an
    ambiguous project name and an ambiguous bot name all now share — what
    a candidate's own label says still differs by table, since a project
    or a bot user sharing the same name is only told apart by its id,
    while two tasks sharing a prefix need their full id either way (an
    ambiguous prefix as long as `short_id` itself would otherwise list the
    same eight characters twice) plus the title beside it, since the id
    alone does not say which task is which.

    `not_found` is the one step that legitimately differs per caller —
    everywhere but `resolve_tag_name`, no match at all is refused the same
    way (worded by the caller, since "no task's id starts with" and "no
    project is named" are not the same sentence); for `resolve_tag_name`
    alone, it is a pass-through instead, since a tag name is a filter
    nothing satisfies, never a reference that could be wrong.
    """
    try:
        parsed = uuid.UUID(raw)
    except ValueError:
        parsed = None
    if parsed is not None:
        found = table.by_id(parsed)
        return found if found is not None else not_found()

    matches = table.candidates()
    if not matches:
        return not_found()
    if len(matches) > 1:
        listed = table.separator.join(label for _, label in matches)
        refuse(
            table.ambiguous_code,
            f"“{raw}” names {len(matches)} {table.noun}: {listed}. {table.instruction}",
        )
    return matches[0][0]


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
    A caller's own full id is taken as-is, unvalidated here either way, by
    `_resolve_by_name`'s shared `by_id` step.

    The scope and the archive check are both one `in_()` against a
    `tree_walk` (`archived_task_ids`, `tasks_in_projects`, #305) inside the
    same statement the prefix match itself runs in, not two separate
    queries, so the two walks it compiles stay the cache-stable pair
    `tests/crud/test_predicates.py` checks for (#305).
    """

    def candidates() -> Sequence[tuple[uuid.UUID, str]]:
        hex_id = func.replace(cast(col(Task.id), Text), "-", "")
        conditions: list[Any] = [
            Task.owner_id == caller.owner_id,
            not_deleted(Task),
            ~col(Task.id).in_(archived_task_ids(caller.owner_id)),
            hex_id.ilike(f"{raw.lower()}%"),
        ]
        if caller.bot is not None:
            conditions.append(col(Task.id).in_(tasks_in_projects(caller.project_ids)))
        rows = session.exec(
            select(Task.id, Task.title)
            .where(*conditions)
            .order_by(col(Task.created_at))
        ).all()
        return [(task_id, f"{task_id} “{title}”") for task_id, title in rows]

    return _resolve_by_name(
        raw,
        _Table(
            by_id=lambda parsed: parsed,
            candidates=candidates,
            noun="tasks",
            ambiguous_code="ambiguous_id",
            separator="; ",
        ),
        not_found=lambda: refuse("not_found", f"No task's id starts with “{raw}”."),
    )


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
    owner_id = caller.owner_id

    def candidates() -> Sequence[tuple[uuid.UUID, str]]:
        rows = session.exec(
            select(Project.id).where(
                Project.owner_id == owner_id,
                not_deleted(Project),
                func.lower(col(Project.name)) == raw.lower(),
            )
        ).all()
        return [(project_id, str(project_id)) for project_id in rows]

    return _resolve_by_name(
        raw,
        _Table(
            by_id=lambda parsed: parsed,
            candidates=candidates,
            noun="projects",
            ambiguous_code="ambiguous_project_name",
        ),
        not_found=lambda: refuse("not_found", f"No project is named “{raw}”."),
    )


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


def resolve_tag_name(session: Session, owner_id: uuid.UUID, raw: str) -> str:
    """
    A tag's own stored name, by a full id or by name, case-insensitively —
    tags belong to the owner alone (FR-08.9), never narrowed by a bot's
    scope. An exact match wins outright; two tags differing only by letter
    case are refused the way an ambiguous project name is, though worded
    for what is actually ambiguous here (two names that differ only by
    case), rather than the shared "names N tags" shape `resolve_task_id`,
    `resolve_project_id` and the bot-name resolver all share — a name that
    merely matches more than one tag never happens, since a tag name is
    unique up to letter case (FR-08.9). A name (or id) that is not a tag at
    all is not a refusal: filtering by it is simply a filter nothing
    satisfies, the same as the REST API's own `tag` filter already behaves
    for a name it has never heard of — so the raw text is returned
    unchanged, to go on narrowing to nothing. This is `_resolve_by_name`'s
    only caller whose `not_found` is a pass-through rather than a refusal,
    and whose `by_id` is a real lookup rather than the identity the other
    three use, since a tag id still has to come back as the name every
    other reader of a tag works with.
    """

    def by_id(tag_id: uuid.UUID) -> str | None:
        tag = session.get(Tag, tag_id)
        return tag.name if tag is not None and tag.owner_id == owner_id else None

    def candidates() -> Sequence[tuple[str, str]]:
        exact = session.exec(
            select(Tag.name).where(Tag.owner_id == owner_id, Tag.name == raw)
        ).first()
        if exact is not None:
            return [(exact, exact)]
        matches = session.exec(
            select(Tag.name).where(
                Tag.owner_id == owner_id, func.lower(col(Tag.name)) == raw.lower()
            )
        ).all()
        return [(name, name) for name in matches]

    return _resolve_by_name(
        raw,
        _Table(
            by_id=by_id,
            candidates=candidates,
            noun="tags that differ only by letter case",
            ambiguous_code="ambiguous_tag_name",
            instruction="Use the exact name.",
        ),
        not_found=lambda: raw,
    )


# Assignees


def resolve_assignee(caller: Caller, raw: str | None) -> uuid.UUID | None:
    """
    `assignee` the way every tool that takes one reads it (`create_task`,
    #255; `update_task`, #256): `self` is the connecting bot's own id,
    `owner` is the human owner's, anything else is read as a bot user's id
    outright. The real decision (one of the owner's, deleted, nonexistent)
    is still `app.api.routes.tasks._resolve_assignee`'s, a moment later, in
    the route a tool calls through to.
    """
    if raw is None:
        return None
    if raw == "self":
        assert caller.bot is not None, "an MCP caller is always a bot"
        return caller.bot.id
    if raw == "owner":
        return caller.owner_id
    try:
        return uuid.UUID(raw)
    except ValueError:
        refuse(
            "invalid_argument",
            f"“{raw}” is not “self”, “owner”, or a bot user id.",
        )


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


def since_datetime(raw: str) -> datetime:
    """
    `since` as a moment rather than a date (spec #248, #259): the start of
    the day `resolve_date` reads, exclusive — so a closed period ("last
    month") is named by its two calendar dates rather than by exact moments
    a caller would otherwise have to know.
    """
    return datetime.combine(resolve_date(raw), time.min, tzinfo=UTC)


def until_datetime(raw: str) -> datetime:
    """`until`'s own widening: the end of the day, inclusive — `since_datetime`'s other bound."""
    return datetime.combine(resolve_date(raw), time.max, tzinfo=UTC)


# Actors


def resolve_actor(
    session: Session, caller: Caller, raw: str
) -> tuple[uuid.UUID | None, bool, bool]:
    """
    `actor` as the three fields `app.activity_log.ActivityNarrowing` takes
    for it (spec #248, #259, #298): `actor_bot_user_id`, `by_bots`,
    `by_user`. `self` is
    the connecting bot's own id; `owner` and `any_bot` read as the log's own
    flags for "the human" and "any bot user"; anything else names a sibling
    bot user, by id or by name case-insensitively, the same ambiguous-name
    rule `resolve_project` follows, since a bot user's name is no more
    unique than a project's. Unlike a tag name (`resolve_tag_name`), a name
    matching no bot user is refused rather than narrowed to nothing: there
    is no reading of "show me what Nonexistent Bot did" where silently
    answering "nothing" is more useful than saying the name is wrong.
    """
    assert caller.bot is not None, "an MCP caller is always a bot"
    if raw == "self":
        return caller.bot.id, False, False
    if raw == "owner":
        return None, False, True
    if raw == "any_bot":
        return None, True, False
    return _resolve_bot_id(session, caller.owner_id, raw), False, False


def _resolve_bot_id(session: Session, owner_id: uuid.UUID, raw: str) -> uuid.UUID:
    """
    A bot user's id by a full id or by name, case-insensitively — deleted
    ones included, so an actor narrowing still finds what a deleted bot
    user did (FR-08.19). `resolve_actor` reads `self`, `owner` and
    `any_bot` ahead of this, so everything that reaches here is already
    known to name a sibling bot user one way or the other, resolved by
    `_resolve_by_name`'s shared algorithm the same as the task, project and
    tag resolvers.
    """

    def candidates() -> Sequence[tuple[uuid.UUID, str]]:
        rows = session.exec(
            select(BotUser.id).where(
                BotUser.owner_id == owner_id,
                func.lower(col(BotUser.name)) == raw.lower(),
            )
        ).all()
        return [(bot_id, str(bot_id)) for bot_id in rows]

    return _resolve_by_name(
        raw,
        _Table(
            by_id=lambda parsed: parsed,
            candidates=candidates,
            noun="bot users",
            ambiguous_code="ambiguous_bot_name",
        ),
        not_found=lambda: refuse("not_found", f"No bot user is named “{raw}”."),
    )


def actor_label(bot: BotUserRef | None) -> str:
    """
    Who acted, read back the way every tool that names one renders it:
    "owner" for the human — `bot` is `None` exactly when a recorded actor
    was the owner, never a bot user, whatever shape each caller's own data
    carries that in — or a bot user by the name it carries whatever its own
    scope (present even once deleted, FR-08.19), "(deleted)" appended if it
    no longer exists. Shared by `search_activity`, `list_completions` and
    `get_task`'s own comment rows (#301) rather than three copies of the
    same two lines.
    """
    if bot is None:
        return "owner"
    return f"{bot.name} (deleted)" if bot.deleted else bot.name


class HasActor(Protocol):
    """
    Anything that names who acted the way an activity entry does: a real
    column on `ActivityEntry` itself, or `list_completions`'s own `_Actor`
    dataclass, built from the same two fields off an entry it has already
    expanded away from. Exactly one of the two is ever set — never both,
    never neither — the same invariant `actor_label_of` below asserts.

    Declared as read-only properties rather than plain attributes: a plain
    attribute in a `Protocol` asks a structural match to be read-*and*-write
    compatible, which `ActivityEntry`'s own SQLModel column and `_Actor`'s
    frozen dataclass field both fail for reasons that have nothing to do
    with this convention — neither is ever written back through here.
    """

    @property
    def actor_id(self) -> uuid.UUID | None: ...
    @property
    def actor_bot_user_id(self) -> uuid.UUID | None: ...


def actor_label_of(actor: HasActor, bots: Mapping[uuid.UUID, BotUserRef]) -> str:
    """
    Who acted, read down to `actor_label`'s own convention from anything
    carrying `actor_id`/`actor_bot_user_id`: an `ActivityEntry` row
    (`search_activity`) or `list_completions`'s own `_Actor`. The two tools
    used to carry byte-identical four-line wrappers here, differing only in
    the annotated type of this argument (#321) — a review once read them as
    pure pass-throughs to `actor_label`, which they are not: reading an
    actor down to a bot or the owner, and asserting a bot a completion names
    is still there to be named (FR-08.19), is real work, done once rather
    than twice now that `HasActor` says in the type what both bodies already
    agreed on in the data.
    """
    if actor.actor_id is not None:
        return actor_label(None)
    assert actor.actor_bot_user_id is not None
    bot = bots.get(actor.actor_bot_user_id)
    assert bot is not None, "a bot user is kept, not removed, once it acted (FR-08.19)"
    return actor_label(bot)


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
    rows: list[dict[str, Any]],
    *,
    key: str = "tasks",
    count: int,
    offset: int = 0,
    narrow_with: str | None,
) -> dict[str, Any]:
    """
    The envelope a tool that returns several rows replies with (spec #247,
    generalised by #259 for its third shape): the compact rows under `key`
    (`"tasks"` for `search_tasks`, `"tags"` for `list_tags` — migrated here
    rather than kept as #254's own small copy — and `"entries"` for
    `search_activity`), the total the filters matched (not just this page),
    and, only when the page did not hold all of them, the filter that would
    narrow it — named by the caller, since only it knows which of its own
    arguments is still free to narrow with. `offset` defaults to 0 for a
    tool like `list_tags` that takes no page to skip.
    """
    result: dict[str, Any] = {key: rows, "count": count}
    if offset + len(rows) < count:
        result["truncated"] = True
        if narrow_with is not None:
            result["narrow_with"] = narrow_with
    return result


def narrow_hint(*filters: tuple[str, bool]) -> str | None:
    """
    `list_result`'s own `narrow_with`: the first of a tool's own filters,
    among `filters` in the priority order its own caller lists them, whose
    own `is_set` says it is still free to narrow with — named, not applied,
    so the caller stays the one deciding what it actually meant. `search_tasks`,
    `search_activity` and `list_completions` each pass their own filters in
    their own order (#301) — the one loop over them is shared; which
    filters exist, and which one to suggest first, is still each tool's own
    to decide. A pair standing for two filters that narrow the same way
    (`search_activity`'s `task_id` and `project`, say) is set if either one
    is; `search_tasks`' own `status` counts as set only once `open_only` has
    left something in it, so its own caller passes `bool(status)`, not
    `status is not None`.
    """
    for name, is_set in filters:
        if not is_set:
            return name
    return None
