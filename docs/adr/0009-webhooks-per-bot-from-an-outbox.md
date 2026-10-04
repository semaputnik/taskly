# Webhooks belong to bot users and are delivered from an outbox

Until now a bot user found out about work by asking: polling the task list on
a schedule of its own. An AI agent that polls either wastes runs on an empty
list or sits for minutes on a task that was handed to it. Taskly now calls a
bot user back: each bot user may carry two webhooks, one for a task becoming
ready for it and one for a comment on a task it is involved in.

**Per bot user, not per user.** A webhook could have hung off the user, with a
filter saying which bot's events it wants. But the receiver of a webhook *is*
an integration, which is exactly what a bot user models, and everything a bot
user has — its scope, its token, its name on what it did — is already set in
one place by the owner. A webhook is one more thing a bot user has. It also
keeps the question "what may this URL learn about" answered by the bot's scope
rather than by a second filter. Like the rest of a bot user's configuration
(FR-07.3), only the owner sets it, in the interface; a bot cannot point its
own webhook somewhere else.

**Two fixed events, not a subscription.** A general "subscribe to any change"
would need an event vocabulary, a filter language and a way for a bot to say
which kinds it wants, for a product whose bots so far need exactly two
things: to be told when a task is theirs to do, and to be told when someone
has said something on a task they are part of. "Ready" is deliberately a
state entered — in To do *and* assigned to the bot — rather than two separate
events, because a bot assigned a Backlog task has nothing to do yet and a bot
whose To do task is reassigned away was never asked. The bot's own changes do
not fire its webhooks: an agent that moves its task and is then told about it
loops.

**A thin ping, not the record.** A delivery carries the event type, the ids
involved and the task's title, nothing more. The bot fetches what it needs
with its token, so what it can learn is bounded by its scope, not by what a
payload happened to include, and a URL that is wrong or stale leaks a title
rather than a thread. It also makes ordering unimportant: a bot that receives
two pings reads the current task once.

**An outbox inside the API, not fire-and-forget and not a worker.** Sending
from the request and forgetting would lose every event the receiver was down
for, and a lost event is a task nobody picks up. A separate worker process is
a second thing to run, configure and keep alive on every installation. The
middle: events are written to a table in the same transaction as the change
that caused them, and the API processes themselves drain it in the
background, retrying on a fixed schedule and marking a delivery failed after
about two hours. This is the first background work in the backend; the outbox
is also what lets the owner see the last delivery of each webhook, and what
keeps a signed request possible after a restart.

**Private addresses are refused unless the operator says otherwise.** A
webhook makes the server send requests to an address a user typed, and
registration is open, so without a rule any visitor could probe the server's
own network. Loopback and private ranges are refused by default and allowed
by one installation setting, because the common self-hosted case — an agent
on the same machine or LAN — is the one the default forbids, and the operator
is the one who knows which case theirs is.
