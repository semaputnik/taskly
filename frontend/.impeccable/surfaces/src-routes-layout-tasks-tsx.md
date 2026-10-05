---
version: 1
slug: "src-routes-layout-tasks-tsx"
primary_target: "src/routes/_layout/tasks.tsx"
related_targets: ["src/components/Tasks/TaskFilters.tsx","src/components/Tasks/search.ts","src/components/Tasks/CompactTaskRow.tsx","src/components/Dashboard/CaptureLine.tsx"]
---

# Surface brief: the task list (redesign slice 3)

Scope: the Tasks route (`src/routes/_layout/tasks.tsx`), its filters, order and paging, the
task line's meta line, and the capture line's search and phone placement. Visitor mode:
**Operate**. The direction contract is inherited from the dashboard brief
(`src-routes-layout-index-tsx.md`, seed 018cd79f); this brief adds only the surface strategy for
the list.

## Audience, job, action

- The owner managing everything that is not in their hands today: Backlog, tasks on bot users,
  a project's whole list. They narrow with filters, scan, open a line, close a task.
- Primary actions: narrow the list; open a task; close a task; write a task into the narrowed
  project; find an open task by typing its title.
- Proof on screen: real counts in the lede (open, in Backlog, on bot users, overdue), real
  lines with assignee and project, the real total and page.
- Constraints: F-06 as amended for this slice (FR-06.4, 06.5, 06.13 to 06.15), ADR-0006 (open
  work only), the Stay-Put Rule, WCAG 2.2 AA both themes.

## Decisions taken in discovery (2026-10-05)

- **One view, lines.** The table view, the view switch, selection and the bulk-action bar are
  removed from the interface; the REST API keeps its batch endpoint for bot users.
- **Default order: newest filed first**, with subtasks indented under their root task with a
  branch mark; due date, priority and filed remain the choosable orders.
- **Filters are one text row**: "Any project", "Anyone", "Any status", "Any priority", "Any
  tag", "Any time", each a quiet text button opening a menu; a set filter is ink at 500 with an
  × to drop it; "Clear" at the row's end; the order menu at the right.
- **Assignee in the meta line**: "you", the bot user's name, or "release-bot → you" for a
  Review hand-over. Closes the slice-1 critique's open finding.
- **No "Add a task" in the navigation.** Capture lives in the page's capture line, the `c` key
  and, on a phone, the same line pinned to the bottom of the screen; the floating button goes.
- **The capture line searches**: from two characters, open tasks whose title contains the text,
  up to eight, newest first, match marked, status mark and project shown; Enter creates, arrows
  and Enter or a tap open a match. Matches open downward on desktop and upward on a phone.
- **Phone**: filters wrap, the rarer ones (tag, time) fold behind "More"; the capture line is
  the bottom bar above Safari's own; the list never scrolls sideways.

## First viewport (desktop)

Main column max 900px. The capture line at the top, "Add a task to <project>…" when narrowed.
"Tasks" at 22px/600, the counts sentence. The filter row over a strong hairline. Lines at 15px
with the meta line beneath, subtasks indented 30px with a 10px branch, the project marker at the
right end. The pager line: "N tasks", Previous and Next at the right.

## Unresolved

- Whether the capture line should also appear on Projects, Tags, Bots and Activity on a desktop,
  where `c` is now the only capture; decided after the slice if the owner misses it.
- How "More" folds filters on a phone: a sheet listing the remaining filters, or a second row.

References: `.impeccable/mocks/changelog-tasks.html` (desktop and phone layout) and
`.impeccable/mocks/changelog-tasks-iphone.html` (the phone, in Safari on an iPhone 16, idle and
typing), the approved mocks and the critique reference at the finish review.
