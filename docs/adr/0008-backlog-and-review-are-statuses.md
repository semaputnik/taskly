# Backlog and Review are statuses, not flags

Four statuses (ADR-0004) left two situations with no name. A task the owner
had written down but not decided to do sat in To do beside the ones they had,
so To do stopped meaning anything. And a bot user that had finished a task had
no way to say so short of closing it, which the owner then could not check
before it was gone. The set is now six: **Backlog**, To do, In progress,
Waiting, **Review**, Done. Both new values are open, and every rule in the
product goes on asking only whether a task is open or Done.

**Statuses, not a flag and a tag.** Backlog could have been a `planned`
boolean beside the status, and Review a tag a bot applies. Both were rejected
for the reason ADR-0004 gives against user-defined statuses: a second axis
means a second question in every rule and every filter, and two values that
can contradict each other (`planned: false, status: in_progress`). A task is
in exactly one place, and the status is that place. The cost is what ADR-0004
already accepted — the vocabulary is fixed and a bot has to know it — and six
values is still a vocabulary.

**Review is the owner's move, Waiting is someone else's.** The two look alike
from outside — work has stopped — and are told apart by whose move is next.
Waiting is the owner's parking state for work that depends on others. Review
is the doer's hand-over, which in practice means a bot user's: it finished,
and the owner decides whether it is done. That is why Review sits on the main
road, between In progress and Done, and Waiting beside it.

**Review does not touch the assignee.** The hand-over the bot makes is two
acts, a status and an assignee, and nothing joins them: a bot that finished
half and wants Review while staying assigned is not refused, and a task does
not land on the owner because of a status. The dashboard's *My work* shows
what is explicitly on the owner, so a bot that wants the owner to see its
work reassigns it, and the API documentation says so as a convention.

**Backlog is the default, and recurring work skips it.** Every captured task
starts in Backlog, so To do is a decision rather than a default; capture
stays a single act and the decision is made on the Tasks page. The next
occurrence of a recurring task starts in To do, because the decision was
made when the series was set up and a daily task that had to be re-planned
daily would be no recurrence at all. Undoing a completion still returns a
task to To do, not to where it was: work that came back is work decided on.
