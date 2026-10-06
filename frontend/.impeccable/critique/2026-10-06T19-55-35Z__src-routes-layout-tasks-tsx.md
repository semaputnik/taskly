---
target: Tasks list (closing critique)
total_score: 29
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/_layout/tasks.tsx"
target_fingerprint: "sha256:28cad310d6147d2df452c25112b3e0079063ff0a2e35669d84dab31b74fa2020"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/_layout/tasks.tsx
timestamp: 2026-10-06T19-55-35Z
slug: src-routes-layout-tasks-tsx
---
⚠️ DEGRADED: single-context (sub-agent cannot be waited on in this run)

Method: closing critique, single context. Read source (tasks.tsx), DESIGN.md, PRODUCT.md, the tasks and tasks-iphone mocks, and viewed tasks-{desktop,phone}-{light,dark} plus task-column (the list beside the open column). Detector scan ran (clean). No browser, no overlay.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Count sentence, "5 tasks", page x of y; skeleton rows sized to the count |
| 2 | Match with real world | 3 | "Any project / Anyone / Any status" read as words; "Newest first" |
| 3 | User control and freedom | 3 | Filters in the URL, "clear them all" in the empty state; no active-filter summary on the list |
| 4 | Consistency and standards | 3 | Same line anatomy as Today, Projects, Bots |
| 5 | Error prevention | 3 | Page clamps when the list shrinks; no bulk edits by design |
| 6 | Recognition rather than recall | 3 | Filters are visible words; priority and status are marks with no key |
| 7 | Flexibility and efficiency | 3 | C, Down/Up walk into the column, server-side order and paging |
| 8 | Aesthetic and minimalist design | 3 | Six filters plus order is the densest control row in the product |
| 9 | Error recovery | 3 | Distinct failed, filtered-empty, all-done and first-run states with different sentences |
| 10 | Help and documentation | 2 | Empty states guide; ring colours and ordering rules are unexplained |

**Total: 29/40.** Verdict: ships with notes.

## Design Specificity Verdict
LLM assessment: specific. A bare ruled list with the count as one sentence ("5 open. 4 in Backlog, 1 overdue.") and the project as a quiet right-aligned word is a triage surface, not a table or kanban. The no-selection stance is stated in code and in the product.
Deterministic scan: `impeccable detect --json` exited 0 with `[]` on this file. The scanner was proven to read .tsx (a probe file with a side-tab border returned findings, exit 2). No browser overlay was available, so rendered checks were judged from screenshots only.

## Overall Impression
A well-argued list that does one thing. The weakest point is the control row: six dropdown triggers that all look alike.

## What's Working
- Empty states: four different sentences for four causes, each with the next action.
- The right-aligned project word keeps the left edge for title and facts; scanning is fast in both themes.
- With the column open the filters reflow to two rows and the selected line keeps a visible tint.

## Priority Issues
- [P2] Filters give no sign of being active. Why: after choosing a project the trigger changes its word, but nothing on the list says it is narrowed, and on the phone three filters sit under "More". Fix: when any filter is set, add a "Clear filters" text action beside the count. Suggested command: /impeccable clarify. Product decision: no.
- [P2] The phone control row is unbalanced: three filters and "More", then "Newest first" alone on a second row at the right. Why: order floats apart from the filters it belongs with and costs a row of height above the list. Fix: put order on the filter row or under More. Suggested command: /impeccable layout. Product decision: no.
- [P3] Status and priority rings are told apart by colour and dash (grey, amber, red, filled dot) and nothing in the list names them. Why: a first-timer cannot learn them and colour-only meaning fails Sam. Fix: give each an accessible name and consider showing P1 in the line. Suggested command: /impeccable harden. Product decision: yes (whether priority belongs in the list).
- [P3] The phone line truncates the project when a row has a date, two tags and a project ("Website r...") and wraps the second tag. Fix: let the project drop to the facts line on narrow widths. Suggested command: /impeccable adapt. Product decision: no.

## Persona Red Flags
**Alex (Power User)**: Good (C, Down/Up, URL state). No way to set status or priority from the list without opening the column, by design.
**Jordan (First-Timer)**: Six "Any ..." dropdowns before the list; ring colours unexplained; dashed versus solid circle unknown.
**Casey (Mobile)**: "More" hides priority, tag and time filters; order sits at the top, away from the thumb; 44px targets under a coarse pointer are in source.

## Minor Observations
- Disabled Previous/Next at 40% opacity are near invisible with one page; hide them when count is within one page.
- "9775 days late" repeats from Today.
- The 22px heading is small beside Today's numeral, which is intended.

## Questions to Consider
- Could the filters be one sentence ("Open tasks in Website relaunch, anyone, any time") instead of six triggers?
- Now that the URL holds state, should a filter set be savable?

Questions skipped: closing critique batch, findings are filed as issues by the coordinator
