---
target: the task list (slice 3)
total_score: 29
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:frontend/src/routes/_layout/tasks.tsx"
target_path: frontend/src/routes/_layout/tasks.tsx
timestamp: 2026-10-06T00-18-57Z
slug: src-routes-layout-tasks-tsx
---
Method: finish review (read-only reviewer over source, the surface brief, the approved desktop and iPhone mocks and nine captures: desktop 1440x900 light and dark, phone 390x844 light and dark, filters open, More sheet, capture matches on both, the dashboard hand-over) on the built branch, then the fixes below, then this score on the build after them. Captures were taken on an isolated stack with roots, subtasks, a bot user task, a Review hand-over, an overdue task, tagged tasks and two projects.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Real counts in the lede, shaped skeletons, an announced pager; a failed fetch now says so |
| 2 | Match with real world | 3 | Calm voice; "1 on a bot user" reads right; the empty state no longer points at a line that is at the bottom on a phone |
| 3 | User control and freedom | 3 | An x on every set filter, Clear, Escape closes matches, undo on notices; no back-out from a wrongly narrowed capture target |
| 4 | Consistency and standards | 3 | One row component, one breakpoint in JS and CSS; the meta line does not mark a deleted bot user while the dashboard's hand-over line does |
| 5 | Error prevention | 3 | Pager targets grow to 44px under touch; the 26px close mark beside a title remains the weak spot |
| 6 | Recognition rather than recall | 3 | A set filter always stays on the row; status is carried by glyph shape alone (no word for Backlog or Waiting) |
| 7 | Flexibility and efficiency | 3 | `c`, arrows through matches, Down and Up walk the list, state in the URL |
| 8 | Aesthetic and minimalist design | 3 | Quiet and faithful to the mocks; every row is two lines and subtasks repeat the project |
| 9 | Error recovery | 3 | A failed list fetch says so with Try again instead of reading as an empty account; empty states teach |
| 10 | Help and documentation | 2 | Empty states teach; nothing glosses the status glyphs (carried from slice 1) |

**Total: 29/40** (slice 2: 30/40 on a different surface; slice 1: 27/40). Verdict: ships. Faithful to the approved mocks, no P0 or P1 left.

## Fixed after the finish review (before scoring)
- [P1] A failed task fetch rendered as "No tasks yet": the page now shows an alert, "The tasks could not be loaded", with Try again; covered by a spec.
- [P2] The capture-match footer clipped the destination project on a phone: it wraps, and only the typed title is clamped.
- [P2] A hand-over's "→ you" was the part clipped on a phone: the bot user's name truncates, the arrow does not.
- [P2] The empty state said "the line above": it now names the Add a task line.
- [P2] Pager buttons were about 16px tall on touch: they grow under a coarse pointer.
- [P3] The phone capture field had no focus cue: the bar's top hairline turns ink on focus.
- [P3] "1 on bot users" in the lede.
- [P3] A comment claimed a line can be one line tall.
- [P3] DESIGN.md still described the floating Add button and the navigation entry: rewritten from the shipped code.

## Priority issues (open)
- [P2] The capture line exists only on Today and Tasks. On Projects, Tags, Bots, Activity and Archive a phone has no way to add a task (the `c` key needs a keyboard). Needs a product decision: mount the line in the layout, or link to Tasks.
- [P2] The approved mock prints status words ("Backlog", "blocked") in the meta line; the build has the glyph and its accessible name only. Needs a decision: ship as is, or add a word for Backlog and Waiting.
- [P3] "Newest first" (nested) and "Filed, newest first" (flat) differ only by nesting and nothing says so.
- [P3] A set assignee filter reads "Assigned to me" for yourself and a bare name for a bot user.
- [P3] The meta line does not mark a deleted bot user "(deleted)" as the dashboard's hand-over line does; FR-08.19 asks only that it be named.
- [P3] The `C` key cap sits inside the capture line, but `c` opens the full draft, not the line.
- [P3] Subtask lines repeat their root's project.

## Settled, noted as cost
No server-side tree order: a subtask whose root is on another page or filtered out is drawn as a root. Down and Up walk the record list (#169). A phone has no entry to the full draft. Both the "bot user → you" meta line and the "finished this ... handed it to you" line stay in In my hands: the dashboard brief draws the second with its Close it action and FR-06.13 requires the first wherever a task line is shown.
