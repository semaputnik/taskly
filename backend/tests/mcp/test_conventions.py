"""
`app.mcp.conventions`: direct tests of the pieces no tool test exercises as
an algorithm in its own right — `resolve_task_id`, `resolve_project_id`,
`resolve_tag_name` and the bot-name half of `resolve_actor` all share
`_resolve_by_name` (#301), `narrow_hint` is the one loop three tools' own
`_narrow_hint` used to repeat, and `actor_label` is the one rendering three
tools' own `_actor_label` used to repeat.

Built by hand the way `tests/access/test_task_access.py` and
`tests/app/test_tasks.py` build theirs: through `crud` directly, with a
`Caller` assembled rather than issued a token, since a tool test can only
ever reach these conventions indirectly, through whichever one of its own
arguments happens to be ambiguous or empty that day.
"""

import re
import uuid

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from sqlmodel import Session

from app import crud
from app.api.deps import Caller
from app.mcp.conventions import (
    actor_label,
    narrow_hint,
    resolve_actor,
    resolve_project_id,
    resolve_tag_name,
    resolve_task_id,
)
from app.models import (
    BotPermissions,
    BotScope,
    BotUserCreate,
    BotUserRef,
    ProjectCreate,
    TaskCreate,
    UserCreate,
)
from tests.utils.utils import random_email


def _owner(db: Session) -> Caller:
    user = crud.create_user(session=db, user_create=UserCreate(email=random_email()))
    return Caller(owner_id=user.id)


def _bot(db: Session, owner: Caller, project_ids: list[uuid.UUID]) -> Caller:
    bot = crud.create_bot_user(
        session=db,
        bot_user_create=BotUserCreate(
            name="Agent",
            scope=BotScope(project_ids=project_ids, permissions=BotPermissions()),
        ),
        owner_id=owner.owner_id,
    )
    return Caller(owner_id=owner.owner_id, bot=bot, project_ids=frozenset(project_ids))


def _task(
    db: Session, owner: Caller, project_id: uuid.UUID, title: str = "T"
) -> uuid.UUID:
    task = crud.create_task(
        session=db,
        task_create=TaskCreate(title=title),
        project_id=project_id,
        owner_id=owner.owner_id,
        reporter=crud.Reporter(user_id=owner.owner_id),
    )
    return task.id


# resolve_task_id


def test_resolve_task_id_accepts_a_full_id_unvalidated(db: Session) -> None:
    """A full id is taken as-is, with no query at all — existence is `app.api.access`'s to decide."""
    owner = _owner(db)
    raw = str(uuid.uuid4())
    assert resolve_task_id(db, owner, raw) == uuid.UUID(raw)


def test_resolve_task_id_accepts_the_short_prefix(db: Session) -> None:
    owner = _owner(db)
    inbox = crud.get_inbox_project(session=db, owner_id=owner.owner_id)
    task_id = _task(db, owner, inbox.id)
    assert resolve_task_id(db, owner, task_id.hex[:8]) == task_id


def test_resolve_task_id_no_match_is_refused_not_found(db: Session) -> None:
    owner = _owner(db)
    with pytest.raises(ToolError) as exc_info:
        resolve_task_id(db, owner, "nosuchprefix")
    assert "not_found" in str(exc_info.value)


def test_resolve_task_id_ambiguous_prefix_is_refused_with_candidates(
    db: Session,
) -> None:
    """
    The candidates are listed by the short id a compact line already
    shows, not the full id — a caller that only ever sees `short_id`
    (`render_task_rows`) can quote one straight back, and a full id would
    tell it nothing about which task is which anyway.
    """
    owner = _owner(db)
    inbox = crud.get_inbox_project(session=db, owner_id=owner.owner_id)
    first = _task(db, owner, inbox.id, title="First")
    second = _task(db, owner, inbox.id, title="Second")

    # The empty string is a prefix every task's id starts with — the same
    # deterministic trick `tests/mcp/test_search_tasks.py` uses, rather than
    # relying on two real ids sharing their first characters by chance.
    with pytest.raises(ToolError) as exc_info:
        resolve_task_id(db, owner, "")
    message = str(exc_info.value)
    assert "ambiguous_id" in message
    assert first.hex[:8] in message
    assert second.hex[:8] in message
    assert str(first) not in message
    assert str(second) not in message


def test_resolve_task_id_ambiguous_prefix_lists_each_candidates_title(
    db: Session,
) -> None:
    """
    An ambiguous prefix's refusal exists so the caller can pick the task it
    meant — a list of bare ids tells it nothing about which is which, so
    each candidate is named by its title too.
    """
    owner = _owner(db)
    inbox = crud.get_inbox_project(session=db, owner_id=owner.owner_id)
    _task(db, owner, inbox.id, title="Write the quarterly report")
    _task(db, owner, inbox.id, title="Fix the flaky spec")

    with pytest.raises(ToolError) as exc_info:
        resolve_task_id(db, owner, "")
    message = str(exc_info.value)
    assert "Write the quarterly report" in message
    assert "Fix the flaky spec" in message


def test_resolve_task_id_prefix_matches_only_a_bots_own_scope(db: Session) -> None:
    """A prefix is matched only among tasks the caller could reach at all (ADR-0012)."""
    owner = _owner(db)
    reachable = crud.create_project(
        session=db,
        project_create=ProjectCreate(name="Reachable"),
        owner_id=owner.owner_id,
    )
    outside = crud.create_project(
        session=db,
        project_create=ProjectCreate(name="Outside"),
        owner_id=owner.owner_id,
    )
    in_scope = _task(db, owner, reachable.id, title="In scope")
    _task(db, owner, outside.id, title="Outside scope")
    bot = _bot(db, owner, [reachable.id])

    assert resolve_task_id(db, bot, "") == in_scope


# resolve_project_id


def test_resolve_project_id_accepts_a_full_id_unvalidated(db: Session) -> None:
    owner = _owner(db)
    raw = str(uuid.uuid4())
    assert resolve_project_id(db, owner, raw) == uuid.UUID(raw)


def test_resolve_project_id_accepts_a_name_case_insensitively(db: Session) -> None:
    owner = _owner(db)
    project = crud.create_project(
        session=db, project_create=ProjectCreate(name="Launch"), owner_id=owner.owner_id
    )
    assert resolve_project_id(db, owner, "lAUNCh") == project.id


def test_resolve_project_id_no_match_is_refused_not_found(db: Session) -> None:
    owner = _owner(db)
    with pytest.raises(ToolError) as exc_info:
        resolve_project_id(db, owner, "No Such Project")
    assert "not_found" in str(exc_info.value)


def test_resolve_project_id_ambiguous_name_is_refused_with_candidates(
    db: Session,
) -> None:
    owner = _owner(db)
    first = crud.create_project(
        session=db, project_create=ProjectCreate(name="Launch"), owner_id=owner.owner_id
    )
    second = crud.create_project(
        session=db, project_create=ProjectCreate(name="Launch"), owner_id=owner.owner_id
    )

    with pytest.raises(ToolError) as exc_info:
        resolve_project_id(db, owner, "Launch")
    message = str(exc_info.value)
    assert "ambiguous_project_name" in message
    assert str(first.id) in message
    assert str(second.id) in message


# resolve_tag_name


def test_resolve_tag_name_accepts_a_full_id(db: Session) -> None:
    owner = _owner(db)
    tag = crud.create_tag(session=db, owner_id=owner.owner_id, name="CI")
    assert resolve_tag_name(db, owner.owner_id, str(tag.id)) == "CI"


def test_resolve_tag_name_accepts_a_name_case_insensitively(db: Session) -> None:
    owner = _owner(db)
    crud.create_tag(session=db, owner_id=owner.owner_id, name="CI")
    assert resolve_tag_name(db, owner.owner_id, "ci") == "CI"


def test_resolve_tag_name_unknown_name_passes_through_rather_than_refusing(
    db: Session,
) -> None:
    """
    A tag name is a filter, never a reference: one matching nothing stays a
    filter nothing satisfies, the same as the REST API's own `tag` filter —
    not refused the way an unresolved task, project or bot name is.
    """
    owner = _owner(db)
    assert resolve_tag_name(db, owner.owner_id, "no-such-tag") == "no-such-tag"


def test_resolve_tag_name_unknown_id_passes_through_rather_than_refusing(
    db: Session,
) -> None:
    owner = _owner(db)
    raw = str(uuid.uuid4())
    assert resolve_tag_name(db, owner.owner_id, raw) == raw


def test_resolve_tag_name_case_duplicates_are_refused_ambiguous(db: Session) -> None:
    owner = _owner(db)
    crud.create_tag(session=db, owner_id=owner.owner_id, name="Work")
    crud.create_tag(session=db, owner_id=owner.owner_id, name="work")

    with pytest.raises(ToolError) as exc_info:
        resolve_tag_name(db, owner.owner_id, "WORK")
    message = str(exc_info.value)
    assert "ambiguous_tag_name" in message
    assert "Work" in message
    assert "work" in message


def test_resolve_tag_name_exact_match_wins_over_a_case_duplicate(db: Session) -> None:
    """An exact match is never ambiguous, even with a case-variant also present."""
    owner = _owner(db)
    crud.create_tag(session=db, owner_id=owner.owner_id, name="Work")
    crud.create_tag(session=db, owner_id=owner.owner_id, name="work")

    assert resolve_tag_name(db, owner.owner_id, "Work") == "Work"


# resolve_actor (the bot-name resolver)


def test_resolve_actor_reads_self_owner_and_any_bot(db: Session) -> None:
    owner = _owner(db)
    bot = _bot(db, owner, [])
    assert bot.bot is not None
    assert resolve_actor(db, bot, "self") == (bot.bot.id, False, False)
    assert resolve_actor(db, bot, "owner") == (None, False, True)
    assert resolve_actor(db, bot, "any_bot") == (None, True, False)


def test_resolve_actor_accepts_a_full_bot_id_unvalidated(db: Session) -> None:
    owner = _owner(db)
    bot = _bot(db, owner, [])
    raw = str(uuid.uuid4())
    assert resolve_actor(db, bot, raw) == (uuid.UUID(raw), False, False)


def test_resolve_actor_accepts_a_sibling_bot_name_case_insensitively(
    db: Session,
) -> None:
    owner = _owner(db)
    caller = _bot(db, owner, [])
    sibling = crud.create_bot_user(
        session=db,
        bot_user_create=BotUserCreate(
            name="Triager",
            scope=BotScope(project_ids=[], permissions=BotPermissions()),
        ),
        owner_id=owner.owner_id,
    )
    assert resolve_actor(db, caller, "triAGER") == (sibling.id, False, False)


def test_resolve_actor_no_match_is_refused_not_found(db: Session) -> None:
    owner = _owner(db)
    caller = _bot(db, owner, [])
    with pytest.raises(ToolError) as exc_info:
        resolve_actor(db, caller, "No Such Bot")
    assert "not_found" in str(exc_info.value)


def test_resolve_actor_ambiguous_bot_name_is_refused_with_candidates(
    db: Session,
) -> None:
    owner = _owner(db)
    caller = _bot(db, owner, [])

    def _named(name: str) -> uuid.UUID:
        bot = crud.create_bot_user(
            session=db,
            bot_user_create=BotUserCreate(
                name=name,
                scope=BotScope(project_ids=[], permissions=BotPermissions()),
            ),
            owner_id=owner.owner_id,
        )
        return bot.id

    first = _named("Dup")
    second = _named("Dup")

    with pytest.raises(ToolError) as exc_info:
        resolve_actor(db, caller, "Dup")
    message = str(exc_info.value)
    assert "ambiguous_bot_name" in message
    assert str(first) in message
    assert str(second) in message


# The shared ambiguity shape


def test_ambiguous_prefix_name_and_bot_name_refuse_in_the_same_shape(
    db: Session,
) -> None:
    """
    The one acceptance criterion this module exists for: an ambiguous task
    prefix, an ambiguous project name and an ambiguous bot name all come
    back in the same shape — `_resolve_by_name`'s own template — asserted
    once here rather than separately in each tool's own test file.
    """
    owner = _owner(db)
    inbox = crud.get_inbox_project(session=db, owner_id=owner.owner_id)
    _task(db, owner, inbox.id)
    _task(db, owner, inbox.id)
    crud.create_project(
        session=db, project_create=ProjectCreate(name="Dup"), owner_id=owner.owner_id
    )
    crud.create_project(
        session=db, project_create=ProjectCreate(name="Dup"), owner_id=owner.owner_id
    )
    bot_owner = _bot(db, owner, [])
    for _ in range(2):
        crud.create_bot_user(
            session=db,
            bot_user_create=BotUserCreate(
                name="Dup",
                scope=BotScope(project_ids=[], permissions=BotPermissions()),
            ),
            owner_id=owner.owner_id,
        )

    shape = re.compile(r"^“.*” names \d+ .+: .+\. Use one of their ids\.$")

    for call in (
        lambda: resolve_task_id(db, owner, ""),
        lambda: resolve_project_id(db, owner, "Dup"),
        lambda: resolve_actor(db, bot_owner, "Dup"),
    ):
        with pytest.raises(ToolError) as exc_info:
            call()
        code, _, message = str(exc_info.value).partition(": ")
        assert code.startswith("ambiguous_")
        assert shape.match(message), message


# narrow_hint


def test_narrow_hint_returns_the_first_unset_filter_in_order() -> None:
    assert narrow_hint(("a", True), ("b", False), ("c", False)) == "b"


def test_narrow_hint_returns_none_once_everything_is_set() -> None:
    assert narrow_hint(("a", True), ("b", True)) is None


def test_narrow_hint_order_is_the_callers_own() -> None:
    """Each caller passes its own priority order — the same two filters, reordered, hint differently."""
    assert narrow_hint(("a", False), ("b", False)) == "a"
    assert narrow_hint(("b", False), ("a", False)) == "b"


# actor_label


def test_actor_label_of_none_is_owner() -> None:
    assert actor_label(None) == "owner"


def test_actor_label_of_a_live_bot_is_its_name() -> None:
    bot = BotUserRef(id=uuid.uuid4(), name="Agent", deleted=False)
    assert actor_label(bot) == "Agent"


def test_actor_label_of_a_deleted_bot_appends_deleted() -> None:
    bot = BotUserRef(id=uuid.uuid4(), name="Agent", deleted=True)
    assert actor_label(bot) == "Agent (deleted)"
