"""
`tree_walk`'s CTE stays cache-friendly: these checks run offline, against the
statement itself, never a database — exactly the guard the issue wanted
against reintroducing a per-call generated name (#305). A fresh name per
call once made every walk's compiled form unique, which defeated
SQLAlchemy's statement cache and evicted unrelated statements out of it;
an unnamed CTE lets SQLAlchemy number it per statement instead, so two
identical walks still produce the same cache key.
"""

import uuid

from sqlmodel import col, select

from app.models import Task
from app.repositories.predicates import tree_walk


def test_two_identical_tree_walks_share_a_cache_key() -> None:
    """
    A caller-supplied or freshly generated CTE name would make two
    structurally identical walks compile to different statements, which
    SQLAlchemy's cache treats as two separate entries forever. An unnamed
    CTE keeps the compiled form — and so the cache key — the same.
    """
    task_id = uuid.uuid4()
    condition = Task.parent_id == task_id

    first = select(Task.id).select_from(tree_walk(condition))
    second = select(Task.id).select_from(tree_walk(condition))

    assert first._generate_cache_key() == second._generate_cache_key()


def test_two_tree_walks_in_one_statement_compile_to_distinct_ctes() -> None:
    """
    `app/mcp/conventions.py`'s `resolve_task_id` combines two tree walks in
    one statement for a bot caller. Nothing about either walk names its own
    CTE, so SQLAlchemy has to number them itself — this is the case that
    broke when a caller had to pick two unique literal names, and the case
    that would break again if the two walks compiled to the same anonymous
    number.
    """
    owner_id = uuid.uuid4()
    other_owner_id = uuid.uuid4()

    first_walk = tree_walk(Task.owner_id == owner_id)
    second_walk = tree_walk(Task.owner_id == other_owner_id)
    statement = select(Task.id).where(
        col(Task.id).in_(select(first_walk.c.id)),
        col(Task.id).in_(select(second_walk.c.id)),
    )

    compiled = str(statement)

    assert "WITH RECURSIVE anon_1" in compiled
    assert "anon_2" in compiled
    assert compiled.count("WITH RECURSIVE") == 1
