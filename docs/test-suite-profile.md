# Backend test suite profile (#323)

Measured 2026-10-14 on a developer laptop that had been running subagents all
day (load average 2.9–4.1 while the headline runs were taken — not an idle
machine, which is why every number below was taken at least twice). 1528
tests, collected by `pytest tests/ --collect-only -q`.

This is a measurement, not a change: nothing in `backend/tests/conftest.py`
or any fixture was touched to produce it. The harness scripts that produced
the numbers below live in `backend/scripts/profile_db_time.py` and
`backend/scripts/profile_microbench.py`, kept for the next person who
profiles this suite.

## Headline: where the suite's wall clock goes

| Run | Wall clock |
| --- | --- |
| No coverage, run 1 | 355.17s (`1528 passed … in 352.47s` + process start/teardown) |
| No coverage, run 2 | 356.67s |
| Under `coverage run` (what `scripts/test.sh` actually runs), run 1 | 388.70s |
| Under `coverage run`, run 2 | 405.57s |

No-coverage average: **355.9s**. Coverage average: **397.1s** — close to
#302's own baseline measurement of 6m28.46s taken on this same machine,
which is a useful cross-check that these numbers are in the right range.

**Coverage's own overhead: ~41s, ~11.6% of the no-coverage wall clock.**
That is not small — it is worth knowing that roughly one minute in nine of
every CI run is `coverage`'s own line-tracing, not test execution — but it
is a fixed multiplier on everything, not a lever on any one fixture.

### Fixed cost vs per-test cost

The fixed costs the issue asks to separate out turned out to be genuinely
small, and the suite's own `--durations` output shows why: pytest's
`setup`/`teardown` phases for ordinary tests round to `0.00s` (confirmed with
`--durations=0 -vv` on `tests/api/routes/test_tasks.py`; see below). Schema
creation and `alembic upgrade head` run once, outside the timed pytest
invocation, in the few seconds `scripts/test.sh` spends before `pytest`
starts. The engine is a single global object, built once at import. The
`client` fixture is module-scoped (`TestClient(app)` entering/exiting the
ASGI lifespan once per test file that uses it) and the session-scoped `db`
fixture is built once for the whole run and emptied once at the end — none
of that shows up as a measurable per-test setup cost.

What this means concretely: **almost the entire suite's wall clock is the
"call" phase of every test** — not pytest fixture machinery, but the test's
own body, which in this codebase builds its own scaffolding (a user, a
project, a bot user) through the same HTTP API it goes on to exercise
(`tests/utils/accounts.py`'s own docstring: "Everything here goes through the
API"). That is why a profile has to look inside the call phase rather than
at pytest's setup/teardown split to find the real cost.

## One representative test, phase by phase

`tests/api/routes/test_tasks.py::test_create_task_without_project_lands_in_inbox`:
creates its own user via a passkey ceremony, looks up the inbox project, then
posts one task. Timed directly (not under cProfile, to avoid its overhead),
with `tests/utils/counting.py`'s `before_cursor_execute` listener counting
statements per phase:

| Phase | Time | DB statements |
| --- | ---: | ---: |
| `new_user_headers` (passkey sign-in ceremony: create user, register a passkey, sign in — 2 HTTP round trips) | 73.93ms (61%) | 13 |
| `inbox_project_id` (1 HTTP round trip) | 21.99ms (18%) | 4 |
| `POST /tasks/` — the test's own assertion | 24.53ms (20%) | 13 |
| **Total** | **120.45ms** | **30** |

This matches the `--durations` figure for this same test in the full run
(0.10–0.12s). Pytest's own setup/teardown phases for it: `0.00s` each — all
120ms is inside the test body, and most of it (61%) is the scaffolding the
test builds for itself, not the line under test.

## The dominant per-test cost, named, with numbers

The issue asks specifically: how much is HTTP round trips through
`TestClient`, how much is transactions, how much is hashing? Two independent
measurements agree: **it is database round trips, not hashing, and not
`TestClient`'s own HTTP machinery.**

### Measurement 1: cProfile, self time, by subsystem

`python -m cProfile` over 59 tests from `test_tasks.py`, `test_projects.py`,
`test_comments.py`, `test_bulk_tasks.py` (a representative slice of
`tests/api/routes/`, ~12% of its 691 tests), bucketed by self time
(`tottime`, which does not double-count across nested calls, unlike
cumulative time):

| Bucket | Self time | Share |
| --- | ---: | ---: |
| `psycopg` (DB wire protocol, socket wait) | 4.856s | 37.4% |
| `sqlalchemy` (ORM/Core: compiling, caching, loading) | 1.882s | 14.5% |
| **Database total** | **6.738s** | **51.9%** |
| `pydantic` (validation/serialization) | 0.512s | 3.9% |
| HTTP transport (`starlette.testclient`, `httpx`, `anyio` bridge) | 0.495s | 3.8% |
| `fastapi` (routing, dependency injection) | 0.399s | 3.1% |
| `webauthn` + `cryptography` + `fido2` + `jwt` + `hashlib`/`hmac` (**all password/token/passkey crypto**) | 0.033s | **0.3%** |
| pytest harness itself | 0.120s | 0.9% |
| our own app/test code | 0.116s | 0.9% |
| everything else (stdlib mechanics — `isinstance`, `dict.get`, `getattr` — spread across every layer above) | 4.579s | 35.2% |

Database work (psycopg + SQLAlchemy) is **over 150x** the crypto/hashing
share, and bigger than the explicit HTTP-transport, FastAPI and Pydantic
layers combined.

### Measurement 2: direct instrumentation, whole suite

`backend/scripts/profile_db_time.py` hooks
`before_cursor_execute`/`after_cursor_execute` on the real engine (the same
technique `counting.py` uses per-test, generalised to the whole run) and
totals actual time spent inside `cursor.execute`, with no cProfile overhead
distorting the numbers:

```
total statements executed:        84070
total time inside cursor.execute: 116.59s
wall clock:                       391.68s
share of wall clock:              29.8%
```

That is 1528 tests × ~55 statements/test on average, at **~1.39ms per
statement** round trip, totalling **~30% of the suite's wall clock** spent
waiting on Postgres — consistent with cProfile's 37–52% self-time estimate
on an independent sample (cProfile's own instrumentation inflates CPU-bound
work relative to I/O wait, so the two numbers are expected to differ, not
match exactly; they agree on the thing that matters, which is that DB time
is a large, consistent double-digit share and crypto is not).

**Caveat on this run:** 28 of 1528 tests failed under this harness — all in
`tests/paperless/test_handover.py` and `tests/webhooks/test_delivery.py`,
which gate real-time retry windows. Run standalone (no instrumentation),
those same 71 tests pass cleanly in 18s. The per-statement timestamp
bookkeeping this harness adds was, on this loaded machine, enough to perturb
those timing-sensitive tests. That is a property of the instrumentation, not
a bug in the tests, and it is why `profile_db_time.py`'s own docstring says
to run it on a subset rather than the whole suite. It does not affect the
statement count or total DB time reported above, since every test still ran
to completion.

### Measurement 3: micro-benchmark, each candidate cost in isolation

`backend/scripts/profile_microbench.py`, run twice (plus a third confirming
run):

| Operation | Run 1 | Run 2 | Run 3 |
| --- | ---: | ---: | ---: |
| HTTP round trip through `TestClient` (`GET /caller`, one indexed DB lookup) | 7.362ms | 8.266ms | 6.698ms |
| Bare DB transaction (`session.commit()`, no HTTP, no app code at all) | 3.972ms | 2.325ms | 4.060ms |
| Bot token hash (`sha256`, deliberately **cheap**) | 0.002ms | 0.002ms | 0.002ms |
| Full passkey sign-in ceremony (create user + register passkey + sign in — the deliberately **expensive** crypto) | 56.099ms | 39.980ms | 60.736ms |

Three things fall out of this:

1. **A single DB transaction alone (~2.3–4.1ms) is already more than half of
   a full HTTP round trip (~6.7–8.3ms).** The HTTP round trip through
   `TestClient` is in-process ASGI (no real socket), so most of its cost is
   either the DB work the route does, or FastAPI/Pydantic routing overhead —
   not network or serialization in the way a real HTTP client would pay.
2. **Hashing is exactly as expensive as the issue predicts it should be, by
   design** — a passkey ceremony is ~15–25x a plain DB transaction — but it
   is paid rarely, not per test: only the ~300–400 call sites across the
   suite that build their own user via `tests.utils.user.new_user_headers`
   or `tests.utils.accounts.create_user_headers` pay it (`grep -rc
   "create_user_headers(client" tests` → 387 call sites), not all 1528
   tests. At ~50ms average, that is roughly 15–20s total — about 4–5% of the
   suite's wall clock, not the dominant cost.
3. **Bot token hashing is not where any suite time goes.** It is `sha256`
   over a 256-bit random token (`app/core/security.py`'s own comment: "a fast
   digest is as safe to store as a slow password hash would be"), at
   0.002ms/call — three orders of magnitude cheaper than the passkey
   ceremony, and unmeasurable against anything else in the suite.

## Conclusion: name the lever, and why it is not being proposed

The dominant per-test cost is **real database round trips against a real
local Postgres**, not the MCP protocol handshake (#302 already showed that:
six seconds, 1.6%), not `TestClient`'s HTTP mechanics (~4–8ms, mostly DB
underneath), and not password/token/passkey hashing (well under 1% of CPU
time, and expensive only where it is deliberately supposed to be).

The standard answer to "too many small DB round trips in a test suite" is to
share one transaction (or one connection) across more tests — typically a
`SAVEPOINT`-per-test pattern wrapped in a rollback, so setup data never
really commits and tests stop paying for independent connections and
commits. That is the obvious lever, and it is exactly what this issue and
#288 say not to reach for yet:

- **#288 is open**, not closed as this issue's own first comment
  mistakenly said before being corrected. In code today,
  `backend/tests/conftest.py`'s `db` fixture is still `scope="session"`, and
  `app/activity.py`'s `_discard` (line ~456) pops `_PENDING_KEY`,
  `_BATCH_KEY` and `_TAG_MERGE_KEY` but never `_ACTOR_KEY` — confirmed by
  reading the function directly. An actor set by one test through the shared
  session is still set for the next one.
- Any pattern that shares a transaction or connection across more tests
  widens exactly this leak surface, not narrows it. A `SAVEPOINT`-rollback
  fixture would make the *existing* actor-leak bug *more* likely to bite
  (more tests sharing more state, not fewer), and it would conflict with
  code that already depends on real commits being visible across sessions —
  `tests/paperless/test_handover.py` and `tests/webhooks/test_delivery.py`
  (the same two files the instrumentation above perturbed) run a real
  background worker thread with its own connection, which must see what the
  main test thread committed. A rollback-based test transaction breaks that
  by design.

**The measured result is a qualified no: do not touch fixtures now.** The
suite's cost is legitimate work — real queries against a real database,
exercised through the real HTTP surface — and the one concrete lever that
would meaningfully cut it requires sharing more test-session state, which
is unsafe until #288 is fixed. The follow-up proposal (filed as a new issue)
says exactly this, and names the two files above as what a future
`SAVEPOINT`-rollback pattern would have to specifically exempt or redesign.

## Reusable harness

- `backend/scripts/profile_db_time.py` — totals real DB wait time and
  statement count for a pytest run, via the same cursor-execute hook
  `tests/utils/counting.py` uses per-test. Run on a subset
  (`python scripts/profile_db_time.py tests/<subset> -q`), not the whole
  suite — see its docstring for why.
- `backend/scripts/profile_microbench.py` — isolates the three candidate
  per-test costs this issue named (HTTP round trip, DB transaction, crypto)
  as standalone, repeatable numbers, independent of any one test's shape.
