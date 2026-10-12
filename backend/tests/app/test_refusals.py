"""
`app.refusals` (#275, #279): a refusal names itself, and is not an
`HTTPException` wearing a different hat.

This file pins the shape itself, independent of any one path that raises a
refusal — `tests/api/routes/test_task_write_refusals.py` (#276) is what pins
the wording a specific refusal gives a specific caller; this is what the
acceptance criteria calls "a test asserts that no refusal raised on these
paths lacks a code": every member of `RefusalCode` is exhaustive by
construction (`Refusal.__init__` makes `code` a required positional), so the
only way a refusal introduced by this slice could lack one is if this
module's own factory stopped setting it.
"""

import uuid

import pytest
from fastapi import HTTPException

from app.models import Task
from app.refusals import (
    OpenSubtask,
    Refusal,
    RefusalCode,
    TaskHasUncompletedSubtasks,
    task_has_uncompleted_subtasks,
)


def test_a_refusal_is_not_an_http_exception() -> None:
    """
    The whole point (#275's "otherwise HTTP leaks back into the operation"):
    a refusal is raised by `app.tasks`, which knows nothing of FastAPI, so it
    must never be mistaken for one by `isinstance`.
    """
    assert not issubclass(Refusal, HTTPException)


def test_a_refusal_requires_a_code() -> None:
    """`code` is the first positional argument, with no default — a refusal cannot be constructed without one."""
    with pytest.raises(TypeError):
        Refusal()  # type: ignore[call-arg]


def test_task_has_uncompleted_subtasks_carries_the_four_things_a_refusal_promises() -> (
    None
):
    open_one = Task(title="Child", owner_id=uuid.uuid4())
    refusal = task_has_uncompleted_subtasks([open_one])

    assert refusal.code is RefusalCode.TASK_HAS_UNCOMPLETED_SUBTASKS
    assert refusal.status == 409
    assert refusal.message == (
        "This task has open subtasks. Say whether they stay as they are or "
        "are done too."
    )
    assert refusal.payload == TaskHasUncompletedSubtasks(
        subtasks=[OpenSubtask(id=open_one.id, title="Child")]
    )


def test_a_refusal_with_no_open_subtasks_still_carries_an_empty_list() -> None:
    """Never `None` where the payload's own type promises a list — a caller reads `payload.subtasks` unconditionally."""
    refusal = task_has_uncompleted_subtasks([])
    assert refusal.payload == TaskHasUncompletedSubtasks(subtasks=[])
