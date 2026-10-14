"""
`_counting`, shared (#322): a context manager that records every statement a
`Session` issues while it is open, via `before_cursor_execute` — the same
small helper `tests/read_models/test_task_publics.py` wrote first, now
reused rather than copied a third and fourth time by `tests/mcp/
test_search_activity.py` and `tests/mcp/test_list_completions.py`, each of
which proves a call issues no statement whose result it discards (#322's own
acceptance criterion: counted, not asserted by eye).
"""

from typing import Any

from sqlalchemy import event
from sqlmodel import Session


class counting:
    """
    `with counting(db) as statements:` records every statement `db`'s engine
    executes for the duration of the block, as `str(args[2])` — the compiled
    SQL `before_cursor_execute` hands the listener — so a test can assert on
    `len(statements)` or on what the statements actually say.
    """

    def __init__(self, db: Session) -> None:
        self.engine = db.get_bind()
        self.statements: list[str] = []

    def _record(self, *args: Any) -> None:
        self.statements.append(str(args[2]))

    def __enter__(self) -> list[str]:
        event.listen(self.engine, "before_cursor_execute", self._record)
        return self.statements

    def __exit__(self, *_: object) -> None:
        event.remove(self.engine, "before_cursor_execute", self._record)
