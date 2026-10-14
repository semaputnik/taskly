"""
A measurement harness for #323, kept for the next person profiling the suite.
Hooks `before_cursor_execute`/`after_cursor_execute` on the shared engine
(the same technique `tests/utils/counting.py` uses per call, #322) to total up
how much wall-clock time the whole run spends waiting on Postgres, and how
many statements it issues, without the distortion cProfile's own
instrumentation adds to every call.

Run from `backend/`, with the test database selected exactly as `test.sh`
requires (see `docs/test-suite-profile.md`):

    python scripts/profile_db_time.py tests/<subset> -q

Not via `pytest`: it drives `pytest.main` itself so the listener attaches
before any test imports the app and its session-scoped `db` fixture.

**Run it on a subset, not the whole suite.** The timestamp bookkeeping this
adds to every statement was enough, on this machine, to perturb the
webhook/paperless retry tests that gate real-time windows
(`tests/paperless/test_handover.py`, `tests/webhooks/test_delivery.py`) —
they failed under this harness and nowhere else. That is a property of this
instrumentation, not a bug in those tests.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import event  # noqa: E402

from app.core.db import engine  # noqa: E402

_total_time = 0.0
_total_count = 0
_start_times: dict[int, float] = {}


def _before(_conn, cursor, _statement, _parameters, _context, _executemany):
    _start_times[id(cursor)] = time.perf_counter()


def _after(_conn, cursor, _statement, _parameters, _context, _executemany):
    global _total_time, _total_count
    start = _start_times.pop(id(cursor), None)
    if start is not None:
        _total_time += time.perf_counter() - start
    _total_count += 1


event.listen(engine, "before_cursor_execute", _before)
event.listen(engine, "after_cursor_execute", _after)

import pytest  # noqa: E402

if __name__ == "__main__":
    wall_start = time.perf_counter()
    code = pytest.main(sys.argv[1:])
    wall_total = time.perf_counter() - wall_start
    print("\n=== DB time profile (#323) ===")  # noqa: T201
    print(f"wall clock (pytest.main):        {wall_total:.2f}s")  # noqa: T201
    print(f"total statements executed:        {_total_count}")  # noqa: T201
    print(f"total time inside cursor.execute: {_total_time:.2f}s")  # noqa: T201
    print(f"share of wall clock:              {100 * _total_time / wall_total:.1f}%")  # noqa: T201
    sys.exit(code)
