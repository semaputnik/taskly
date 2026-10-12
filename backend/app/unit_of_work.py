"""
The transaction boundary an operation owns (ADR-0013): one act is one
transaction, decided here rather than left to whichever repository happens
to call `session.commit()` last.

Before this, `app.api.deps.get_db` opened a session and closed it — no
commit, no rollback — so the repositories' own 23 commits *were* the
boundary, and the composite acts `app.tasks.complete` and `app.comments.
comment` drive landed as two or more of them. `app.tasks` and `app.comments`
are the one place that knows where an act begins and ends, so each of their
five operations (`create`, `update`, `complete`, `delete`, `comment`) opens
one `UnitOfWork` around its own body: everything it stages lands together, or
none of it does.

An explicit object rather than a bare `try`/`finally` inline in each
operation, so the rule ("commit what succeeds, roll back what fails") is
written once and the five operations only ever say `with UnitOfWork(session):`.

The repositories these operations call (`app.repositories.tasks.create_task`
and `.update_task`, `app.repositories.comments.create_comment`, `app.
deletions.delete_task`) each take the same `commit: bool = True` opt-out
`create_user` already had: the operation passes `commit=False` on the one
path it drives, every other caller keeps the commit-by-default behaviour
this module does not touch.

Three places keep a commit of their own, each a documented exception to "one
act, one transaction" rather than a repository that was simply missed:
`app.repositories.comments.create_attachment` (a crash between the row and
its bytes must leave metadata with nothing to download, never bytes nothing
points at), `app.paperless.fetch_original` (releasing the database
connection before a slow HTTP call), and `app.passkeys.finish_registration`,
which already owned its boundary through `app.repositories.projects.
create_user`'s `commit=False` — the precedent this module generalises.
"""

from types import TracebackType

from sqlmodel import Session


class UnitOfWork:
    """
    One act, one transaction: commits everything staged on `session` if the
    wrapped block runs to the end, rolls all of it back if anything in it
    raises.

    `session` is never this object's own — it is the operation's, opened by
    `app.api.deps.get_db` for a request or `app.mcp.conventions.open_caller`
    for an MCP call — so a `UnitOfWork` never opens or closes one, only
    decides how the block using it ends.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> UnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self.session.commit()
        else:
            # A refusal raised before anything was staged rolls back an
            # empty transaction; a failure after a write rolls back
            # whatever the act had staged so far — either way, nothing this
            # act touched is left half-done (#284's own acceptance test).
            self.session.rollback()
