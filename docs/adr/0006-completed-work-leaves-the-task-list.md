# Completed work leaves the task list

The task list was two things at once. It held the work that was left, and it
held the record of work that was finished, told apart only by a status filter
the reader had to remember to set. In an installation that keeps entries
indefinitely (FR-10.5) and never hard-deletes a task (FR-01.8), the second
grows without limit while the first is what the product is for. Triage —
"capture and triage are the core loop" — got steadily worse at exactly the
rate the owner used the product successfully.

The task list now shows open work only. Its status filter offers **Any open
status**, To do, In progress and Waiting, and Done is not among the choices.
Finished work is read in the activity log, which gained a filter by kind of
change for the purpose (FR-10.8).

**The log rather than a second list.** The obvious alternative was a
"Completed" screen. That is the list we just removed, standing somewhere else,
and it would need its own filters, its own paging and its own answer to "how
far back". The log already records every completion with its date and its
actor (FR-10.2, FR-10.3), already links to each task, and is already the
place the owner goes to ask what happened. Making it answer one more question
cost one filter; a second list would have cost a surface.

**The baseline is not a filter.** Open work is what the list *is*, not a
narrowing applied to it. So no chip offers to remove it, clearing the filters
returns to it rather than to every status, and the URL says nothing when it
is in force. The old "Open" choice and the old "no filter" choice were always
the same list; they are now the same control. A URL asking for Done drops
that filter the way the list drops any unusable value, which also means
bookmarks written before this change still open.

**The row was its own receipt, and now it is gone.** Ticking the checkbox used
to leave the task on screen with a line through it. That was the confirmation,
which is why every write in a panel is deliberately silent. Removing the row
removes the confirmation with it, and "nothing is lost quietly" is a product
principle, so completing a task *from a list* now raises a notice naming it
with an Undo. This is the only place a status write is announced, and the
reason is precise: it is the only place where the value stops being visible.
The panel's own status control stays silent, because there the value is still
on screen.

**Where Done still shows.** Three surfaces keep it, and each for its own
reason. The archive is a read-only record of finished work, so hiding Done
there would empty it. The subtask list inside a task's panel keeps its done
children, so the "2/5" progress count stays honest against the rows beneath
it. A bot user's panel already listed only open tasks, so nothing changed
there; what was incidental is now the rule.

**What this costs.** Finding a specific finished task is slower than filtering
a list for it: the log is chronological, and the kind filter narrows it but
does not search it. Taskly has no text search at all (PRODUCT.md lists it out
of scope), so the list was never good at that either — it was a scan, and the
log is a scan. If text search is ever added, it should reach completed work,
and that is the point at which this decision is worth reopening.
