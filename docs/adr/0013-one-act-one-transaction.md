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
