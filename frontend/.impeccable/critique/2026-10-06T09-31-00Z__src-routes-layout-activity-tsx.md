---
target: Activity, the log page (slice 4)
total_score: 28
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:frontend/src/routes/_layout/activity.tsx"
target_path: frontend/src/routes/_layout/activity.tsx
timestamp: 2026-10-06T09-31-00Z
slug: src-routes-layout-activity-tsx
---
Method: finish review (read-only reviewer over source, the slice-4 brief, the approved activity mock and the captures: desktop 1440x900 and phone 390x844, light and dark, the page, the kind menu and the phone order sheet), then the fixes below, a verdict pass, then this score on the build after them. Captures were taken on an isolated stack with entries by the user and by two bot users (one since deleted, struck in the log) and a deleted task with Restore.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | A counts sentence of real entries, a count per day, a pager that says the page and is announced |
| 2 | Match with real world | 3 | The log reads as sentences with the record linked; bot lines in ink, the reader's own in Ink 3 |
| 3 | User control and freedom | 2 | Restore asks first in a dialog for a one-click, reversible action; the brief says inline |
| 4 | Consistency and standards | 3 | The filter row and the order menu are the task list's own pieces; the day page's inline Restore asks nothing, this page's asks |
| 5 | Error prevention | 3 | Restore is confirmed; filter and pager targets grow to 44px under touch |
| 6 | Recognition rather than recall | 3 | A set filter stays on the row with its x; deleted names are struck, so a gone record is seen as gone |
| 7 | Flexibility and efficiency | 3 | Kind, actor, order and page live in the URL and combine; a bot user's column links to its own log |
| 8 | Aesthetic and minimalist design | 3 | Lines, day groups and hairlines only; the time column is one line after the fix |
| 9 | Error recovery | 3 | Empty and failed states are told apart, with Try again; Restore puts a deleted record back |
| 10 | Help and documentation | 2 | Nothing says what each kind of change covers |

**Total: 28/40.** Verdict: ships. Faithful to the approved mock, no P0 or P1 left; one open item needs a product decision.

## Verification
Same runs as the Bots critique: the touched specs, then the full suite once (260 tests, green, both themes in design-system) at --workers=1 on an isolated stack.

## Fixed after the finish review (before scoring)
- [P1] The time column (3.25rem) wrapped "06:34 AM" onto two lines on every row, desktop and phone, and pushed the sentence two lines below its actor on a phone: 4.25rem with no wrap, in the page's skeleton as well.
- [P2] The filter buttons, Clear and the order menu were 28px tall on a phone: 44px under a coarse pointer.

## Priority issues (open)
- [P3, needs a decision] Restore opens a confirmation for a lone task. Options: restore at once with a notice carrying Undo, or keep the dialog only where a cascade needs saying (a project or tag with children).
- [P3] Nothing glosses the six kinds of change in the kind menu.

## Settled, noted as cost
The counts sentence counts the whole log and so makes two limit=1 requests; the pager counts the current narrowing. A day's count is the lines of that day on this page. The actor menu lists the first 100 bot users, like the Bots page.
