"""
`Caller`: whoever is making a request to an endpoint, or calling an
operation, that humans and bot users may both reach.

Moved below `app.api` (#275, #282): `app.tasks` and `app.comments` are
operations, and an operation is not allowed to depend on the layer above it
— yet both used to import `Caller` from `app.api.deps`, the inversion this
module exists to end. `app.api.deps` re-exports `Caller` unchanged, so none
of its other importers moves; resolving one from an actual request —
`_bot_caller`, `get_caller`, `get_mcp_caller` — is still that module's own
job, reading the bearer token, the database and FastAPI's dependency
injection along the way. Only the shape of what a request resolves to, and
attributing a transaction to it once resolved, live here instead.

(`app.api.access`, at 570 lines and imported by every route as well as by
the operations, was the same inversion at a larger scale; this ticket moved
`Caller` and `set_caller_actor` alone, and left it where it was. `app.access`
is #303's move of it, the same shape repeated.)
"""

import uuid
from dataclasses import dataclass

from sqlmodel import Session

from app import activity
from app.models import BotUser, User


@dataclass(frozen=True)
class Caller:
    """
    Whoever is making a request to an endpoint that humans and bot users may
    both call.

    `owner_id` is whose data the request reaches: the user's own, or the
    owning user's for a bot, which never reaches anyone else's. For a bot,
    `bot` and the projects of its scope come along, so Task access
    (`app.access`) can narrow what it reaches. `user` is the human caller
    themselves, already resolved by `app.api.deps.get_current_user`; it is
    `None` for a bot, which is never a `User` row (FR-08.2's "not a kind of
    user account").
    """

    owner_id: uuid.UUID
    bot: BotUser | None = None
    project_ids: frozenset[uuid.UUID] = frozenset()
    user: User | None = None


def set_caller_actor(session: Session, caller: Caller) -> None:
    """
    Attribute whatever this transaction commits to the caller itself
    (FR-10.2): a bot user's act is never recorded as its owner's.

    Shared operation machinery (#282): `app.tasks` and `app.comments` each
    call this themselves, rather than relying on it having already happened
    on the way in — every path today happens to run through the one
    `app.api.deps` dependency that already does this, but a second caller
    already exists (#275), so no operation takes that on faith. One copy,
    beside `Caller` itself, rather than the `_set_actor` each operation
    module used to repeat on its own.
    """
    if caller.bot is not None:
        activity.set_bot_actor(session, caller.bot.id)
    else:
        activity.set_actor(session, caller.owner_id)
