# One act, one transaction, owned by the operation

`app.api.deps.get_db` opens a session and closes it — no commit, no
rollback. The transaction boundary has always been wherever a repository
happened to call `session.commit()`: 23 of them, scattered across what is
now `app.repositories` (#283), none aware of any other. The composite act
`app.tasks.complete` drives when a bot closes a recurring task and leaves a
note — close it, spawn its next occurrence, write the comment — reached the
database as two of those commits: `crud.update_task`'s, then
`crud.create_comment`'s, on the one `Session` an MCP call or a request opens.
Nothing stopped a caller from seeing the task closed with its note still
missing if the second commit never happened, and nothing rolled the first
back if it didn't.

## Decision

**A unit of work is an explicit object, `app.unit_of_work.UnitOfWork`, and
the operation owns it.** Each of `app.tasks`'s four operations (`create`,
`update`, `complete`, `delete`) and `app.comments.comment` opens one around
its own body: `with UnitOfWork(session): ...`. Reaching the end commits
everything staged; an exception — a `Refusal` raised by an access check, or
anything else — rolls all of it back. `update` delegates whole to `complete`
when the request moves a task to done (#282); that delegation is never
nested inside a second `UnitOfWork` of `update`'s own, since `update` returns
before opening one in that branch — the operation that actually performs the
act is always the one that owns its transaction.

**The repositories these operations call stop committing on the paths they
drive, through the same `commit=False` opt-out `app.repositories.projects.
create_user` already had.** `app.repositories.tasks.create_task` and
`.update_task`, `app.repositories.comments.create_comment`, and
`app.deletions.delete_task` (the single-task path `app.tasks.delete` calls,
not the batch or project ones) each gain a `commit: bool = True` parameter;
the operation that drives each path is the only caller that passes
`commit=False`, so every other caller — direct `crud` calls in tests among
them — keeps the commit-by-default behaviour unchanged. A plain unconditional
removal was tried first and broken: `tests/api/routes/
test_composite_act_entries.py::
test_two_commits_touching_one_entity_are_two_entries_not_one` (#278) and
several others call `crud.create_task` directly, by hand, relying on it
landing before whatever they do next — removing its commit outright silently
folded that creation into whatever transaction followed, which is exactly
the collapse risk below, by accident rather than on purpose. The opt-out
parameter is how the existing precedent already avoids that for
`create_user`; this ticket is what generalises it to the other four.

**Verified: the activity log is unaffected.** `app.activity._collect` and
`._write` already diffy an entity's state before a change against its state
right before commit, once per transaction, and already run inside whichever
commit happens to be last — collapsing two commits into one changes how many
transactions there are, not what either hook does inside one. #278's
characterization test
(`tests/api/routes/test_composite_act_entries.py::
test_closing_a_recurring_task_with_a_note_is_three_entries_and_one_delivery`)
pins the proof: closing a recurring task and leaving a note still writes the
same three entries — `task_completed`, `task_created`, `comment_added` — in
the same order, with the same details, attributed to the same actor, and
stages the same one outbox row. It passes unchanged by this ticket.

## The collapse risk

`_write` diffs an entity's state once per transaction. Two *separate*
transactions that each touch the *same* entity write two entries, one per
commit, each with its own partial `changes`; folded into one transaction,
the identical two edits would be diffed exactly once, start to finish, and
write a single entry describing the net change instead of two recording that
it was two decisions. No operation this ticket moved touches one entity
twice within its own act — the composite act above touches three different
entities (the task it closes, the task it spawns, the comment it writes),
never the same one twice — so none of the five transactions this ticket
introduces loses an entry today. `tests/api/routes/test_composite_act_entries.py::
test_two_commits_touching_one_entity_are_two_entries_not_one` (#278) pins
the *other* side of this: two genuinely separate transactions touching one
task still write two entries, proving the diff-once-per-transaction
mechanism itself is untouched. `backend/tests/test_unit_of_work.py::
test_one_unit_of_work_touching_one_entity_twice_is_one_entry_not_two`
demonstrates the collapse directly, built against `UnitOfWork` itself rather
than through a real operation (none needs to, yet): two writes to the same
task inside one `with UnitOfWork(session):` block produce the single merged
entry one transaction is now able to write. The sharp edge for whoever adds
the next operation: if an act's own two sub-steps ever need to read as two
decisions rather than one net change, they need two transactions (two
operation calls), not one operation touching the same row twice.

## The three exceptions

Each keeps its own commit, named where it sits:

- **`app.repositories.comments.create_attachment`.** The attachment's row
  must be durable before its bytes reach storage (`app.api.routes.
  attachments.upload_attachment`): a crash between the two must leave
  metadata with nothing to download, never bytes nothing points at.
  `tests/api/routes/test_attachments.py::
  test_downloading_an_attachment_whose_bytes_are_missing_is_a_404` is what
  already proves it — a row surviving bytes that never arrived — and keeps
  proving it unchanged, since this path is not an operation this ticket
  moved.
- **`app.paperless.fetch_original`.** Commits to release the database
  connection before a slow HTTP call to Paperless; a single outer
  transaction would hold that connection for the whole request instead.
- **`app.passkeys.finish_registration`.** Already owned its boundary through
  `app.repositories.projects.create_user`'s `commit=False` opt-out, the
  precedent this ticket generalises into `UnitOfWork` — now expressed as
  `with UnitOfWork(session): user = crud.create_user(..., commit=False); ...`
  rather than an ad hoc `session.commit()`, with no change to when the
  account and its first passkey land.

## Consequences

What a client or an operator can observe changes in two small ways, both
named in #284's own acceptance criteria: the comment's activity-log entry
timestamp now joins the task's and the next occurrence's at the one instant
the transaction commits, rather than landing a moment later under its own
commit; and `app.webhook_events._wake` fires once per act instead of once
per commit, so an act that stages more than one outbox row wakes the
delivery loop a single time rather than once for each commit that used to
stage one. Neither changes what is eventually delivered or logged, both
pinned by `tests/api/routes/test_composite_act_entries.py` and by
`backend/tests/test_unit_of_work.py`'s own wake-count test.

A failure anywhere inside an act now leaves nothing behind. `tests/mcp/
test_complete_task.py::
test_a_comment_without_the_grant_is_refused_by_name_before_anything_closes`
already closes a task with a comment the caller may not leave and asserts
the task is still open, and needed no change: true already from the access
check ordering `app.tasks.complete` has always had (the comment's grant is
checked before anything closes), and true now for a reason beyond ordering
too — an act that got further before failing would roll back exactly as
completely.

## Amendment (2026-10-14): the boundary stays the operations', and no write path pays for it today

"A unit of work is an explicit object, and the operation owns it" is
unchanged — this settles the open end this ADR left. Of `app.repositories`'s
23 commit sites, #284 gave 4 the `commit=False` opt-out its five operations
need (one, `create_user`, already had it as the precedent #284 generalised);
the other 19, plus every commit outside `app.repositories` that is not one
of the three exceptions below, still commit unconditionally, each its own
repository-owned transaction. Two ways forward were on the table: widen the
boundary to the request edge (`app.api.deps.get_db` commits once on success,
rolls back on failure, and no repository commits at all), or keep growing
operations one at a time, the same shape #284 used. **The boundary stays
the operations'.**

Two reasons, neither about today's code being broken.

**The activity log is the one that matters.** `app.activity._collect`
snapshots an entity before a change; `app.activity._write` diffs it once
per transaction. Two changes to *one* entity in *one* transaction produce
one entry; the same two changes across two commits produce two —
`tests/test_unit_of_work.py::
test_one_unit_of_work_touching_one_entity_twice_is_one_entry_not_two` and
`tests/api/routes/test_composite_act_entries.py::
test_two_commits_touching_one_entity_are_two_entries_not_one` pin both
sides of it, built by hand since nothing in the product does either today.
Widening the boundary to the request edge would silently fold every
write path that happens to commit twice against one entity into this
collapse — and before this ticket, nobody had gone looking for which paths
those were. A change that silently shortens the log is not one to make on
the way to a tidier architecture, least of all in a product whose log is
the only record of when a task was completed (ADR-0011).

**There is no boundary at the request edge to widen into.** `get_db` opens
a session and closes it — no commit, no rollback. The repositories' own
commits *are* the only boundary that exists today; moving to the request
edge would not widen an existing one, it would create one from nothing,
and with it a rollback-semantics question of its own: what a partially
successful request leaves behind when the write that fails is the third
of four, say, and the first two already answered a query that read them
back. #284 answered that question for the five operations it moved,
deliberately, one at a time. Answering it for every remaining commit site
at once, in the same stroke that introduces the boundary, was the risk
this amendment declines to take.

### The survey

The question the issue asked first: which write paths touch one entity
twice within what a caller experiences as one act, and what would moving
the boundary have cost each of them. Every route, MCP tool and repository
outside #284's five operations was read against this (`app.api.routes.*`,
`app.mcp.tools.*`, `app.repositories.*`, `app.deletions`, `app.paperless`,
`app.passkeys`) — **every one of them commits at most once against any
entity the activity log watches (`Task`, `Project`, `Comment`, `Tag`,
`Attachment`) within one request or one MCP call.** The cost of widening
the boundary, counted today, is zero everywhere:

- **The batch endpoints** — the first suspects named, since
  `app.repositories.tasks.bulk_update_tasks` stages subtask completions
  (`complete_subtasks`) and then updates the selected tasks in the same
  pass. Suspected correctly that this is where two writes to one entity
  would show up first; wrongly that it would cost anything — the whole
  batch is already one `session.commit()`, so there is only ever one
  transaction for the boundary to have been widened from. A selection that
  names both a parent and one of its own subtasks touches that subtask
  twice (once swept, once in its own turn through the loop) and still
  lands as the one entry a single transaction always was going to write;
  a subtask swept along but never selected is excluded from the entry
  and its count on purpose (`tests/api/routes/test_bulk_tasks.py::
  test_a_batch_counts_the_tasks_that_were_selected`,
  `::test_a_batch_completion_logs_no_entry_per_swept_subtask`) — a logging
  policy choice, unrelated to where the transaction boundary sits, and
  unchanged by this amendment. `bulk_delete_tasks` (`app.deletions.
  delete_tasks`) is the same shape: one commit for the whole selection.
- **Tags, projects, comments beyond `comment`, bot users and their
  tokens and webhooks** — every route is one call to one repository
  function, one commit. Nothing left to collapse.
- **`app.api.routes.attachments.upload_attachment`** — the one path left
  that genuinely commits twice outside the five operations, on purpose:
  `crud.create_attachment`'s row lands first (the attachment exception,
  below), then `app.paperless.queue_handover` commits a `PaperlessHandover`
  row in a second transaction on the same session. The two commits never
  touch the *same* entity — the attachment, once; a kind `_collect` does
  not watch at all, in the second — so today's two entries and a
  request-edge boundary's one are the same single entry either way
  (`tests/api/routes/test_composite_act_entries.py::
  test_uploading_a_pdf_with_paperless_connected_is_one_entry_not_two`,
  added by this ticket).
- **Users and passkeys** — `app.repositories.users.create_user`,
  `app.passkeys.*` and the dozen-odd commits inside them touch `User`,
  `Passkey` and `PaperlessConnection`, none of which `_collect` watches.
  The Inbox project `create_user` creates in the same transaction is a
  `Project`, but is excluded from the log by name (`not obj.is_inbox`), so
  even this one touch of a watched entity writes nothing to collapse.

Nothing above argues the request edge is cheap in general — only that it
is free *today*, against the paths this product currently has. The first
write path that legitimately needs two separate commits against one
entity within one act is the evidence that would reopen this: a real
instance of the collapse risk, not the hand-built tests above, naming an
actual entry the product would lose. Until one shows up, the operations
keep growing the way #284 started them.

### `commit=False`, named as the seam

Every repository function a write path drives takes `commit: bool = True`
and keeps the behaviour every direct caller — a script, a test calling
`crud.create_task` by hand — already relies on: it lands its own write the
moment it returns, same as before this ADR existed. `commit=False` is what
a function offers instead to the one kind of caller that has somewhere
better for the commit to happen: an operation that opened a `UnitOfWork`
around a body of its own, and needs this write to land as part of that
body rather than as a transaction of its own. The operation is always the
only caller that passes it — never a route, never a test, never another
repository function — because the operation is the only thing in this
codebase that owns a transaction wider than one write.

A write path moving from a bare repository call into an operation of its
own, the way #284 moved the first five, goes through the same two
changes in the same commit: the repository function it drives grows
`commit: bool = True` (if it does not already have one shaped like it),
and the operation is the one caller that passes `commit=False`, inside its
own `with UnitOfWork(session): ...`. Nothing else about the function
changes — `commit=False` does not mean "never commit", it means "someone
else just did, or is about to"; the function still flushes what it staged,
so a caller reading the row back (`session.refresh`) finds it exactly as
committed.

### The three exceptions, unchanged

Each was already a deliberate exception to "one act, one transaction"
before this amendment, and stays one after it, whichever boundary this
ticket had chosen:

- **`app.repositories.comments.create_attachment`.** The attachment's row
  must be durable before its bytes reach storage
  (`app.api.routes.attachments.upload_attachment`): a crash between the
  two must leave metadata with nothing to download, never bytes nothing
  points at. A request-edge boundary would not have removed this commit —
  it would have had to carve out the same exception, since the row and
  the bytes are never going to share one transaction while storage is not
  the database.
- **`app.paperless.fetch_original`.** Commits to release the database
  connection before a slow HTTP call to Paperless; a request-edge
  transaction spanning the whole request would have held that connection
  for the call's whole duration instead, which is the problem this commit
  exists to avoid, not an accident this ADR's original scope left
  standing.
- **`app.passkeys.finish_registration`.** Owns its boundary through
  `app.repositories.projects.create_user`'s `commit=False` opt-out, same
  as before.

None of the three needed a decision from this amendment: each is a
boundary a wider transaction cannot absorb without reintroducing the
problem it exists to solve, independent of where "the rest" of the
boundary sits.
