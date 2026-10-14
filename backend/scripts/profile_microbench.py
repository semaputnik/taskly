"""
A micro-benchmark for #323, kept for the next person profiling the suite.
Isolates three candidate per-test costs named explicitly in the issue, each
measured on its own rather than inferred from a profile:

1. A bare HTTP round trip through `TestClient` (in-process ASGI, no socket),
   hitting a trivial authenticated route that does one indexed lookup.
2. A bare database transaction (`session.commit()` after one trivial write),
   with no HTTP or app code involved at all.
3. A passkey sign-in ceremony (`tests.utils.user.new_user_headers`), the
   expensive-by-design crypto the issue asks about, for comparison against
   the cheap-by-design bot token path (`app.core.security.hash_bot_token`,
   plain sha256).

Run from `backend/`, with the test database selected exactly as `test.sh`
requires (see `docs/test-suite-profile.md`):

    python scripts/profile_microbench.py
"""

import os
import sys
import time
import uuid
from collections.abc import Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.core.security import hash_bot_token  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402

N = 200


def bench(label: str, fn: Callable[[], None], n: int = N) -> None:
    # One warm-up call, excluded from the timing, so import/caching effects
    # on the first call don't skew the per-call average.
    fn()
    start = time.perf_counter()
    for _ in range(n):
        fn()
    total = time.perf_counter() - start
    print(  # noqa: T201
        f"{label:55s} {total:7.3f}s total  {1000 * total / n:7.3f}ms/call  (n={n})"
    )


def main() -> None:
    with TestClient(app) as client:
        from tests.utils.accounts import create_user_headers
        from tests.utils.user import new_user_headers

        with Session(engine) as db:
            headers = create_user_headers(client, db)

        def http_roundtrip() -> None:
            r = client.get(f"{settings.API_V1_STR}/caller", headers=headers)
            assert r.status_code == 200

        bench("HTTP round trip through TestClient (GET /caller)", http_roundtrip)

        def db_transaction() -> None:
            # no-op lookup, same shape as a real read
            with Session(engine) as db:
                db.get(User, uuid.UUID(int=0))
                db.commit()

        bench("Bare DB transaction (session.commit(), no app code)", db_transaction)

        def bot_token_hash() -> None:
            hash_bot_token("taskly_bot_" + "x" * 43)

        bench("Bot token hash (sha256, cheap by design)", bot_token_hash, n=2000)

        def passkey_ceremony() -> None:
            with Session(engine) as db:
                new_user_headers(client, db)

        bench(
            "Full passkey sign-in ceremony (create user + passkey + sign-in)",
            passkey_ceremony,
            n=50,
        )


if __name__ == "__main__":
    main()
