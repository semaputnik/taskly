---
target: Kept tasks page (closing critique)
total_score: 27
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/_layout/projects_.$projectId.tasks.tsx"
target_fingerprint: "sha256:fa02cf781822962405312108a477dbcfa8f639403a6272ba780b573022697aa1"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/_layout/projects_.$projectId.tasks.tsx
timestamp: 2026-10-06T20-03-37Z
slug: src-routes-layout-projects-projectid-tasks-tsx
---
⚠️ DEGRADED: single-context (closing critique batch run sequentially, no isolated sub-agents)

Method: closing critique, single context. Read source (projects_.$projectId.tasks.tsx, the readOnly branch of CompactTaskRow.tsx), DESIGN.md (Archived section, Kept-tasks page), PRODUCT.md, CONTEXT.md and the slice-5 surface brief; there is no dedicated mock for this page (the projects mock shows only the "4 tasks ->" link). Viewed kept-tasks-{desktop,phone}-{light,dark}. Detector over the route file exited 0 with `[]` (the scanner reads .tsx: a probe returned a finding, exit 2). No browser, no overlay: rendered checks are from screenshots only.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Skeleton rows, then the count sentence; a live project redirects to the list |
| 2 | Match with real world | 3 | "2 tasks kept. Archived, so read-only until it is unarchived." says the state in one sentence |
| 3 | User control and freedom | 3 | "<- Projects" and "Open the project" both leave; nothing here can be changed by accident |
| 4 | Consistency and standards | 3 | Same compact task rows and heading scale as the other pages, read-only |
| 5 | Error prevention | 3 | Read-only by construction; archived work cannot leak into daily views |
| 6 | Recognition rather than recall | 2 | Rows show title and status mark only in the captures; a kept task cannot be opened to read what it said |
| 7 | Flexibility and efficiency | 2 | No keyboard walk, no filter, and a hard stop at 100 with no way past it |
| 8 | Aesthetic and minimalist design | 3 | Nothing extra; very sparse with two rows |
| 9 | Error recovery | 3 | A missing project is an alert with the way to the activity log; a failed task fetch leaves skeleton rows |
| 10 | Help and documentation | 2 | The sentence explains read-only; it does not say how to unarchive |

**Total: 27/40.** Verdict: ships with notes.

## Design Specificity Verdict
LLM assessment: specific in intent (a page of its own so archived work never mixes into daily views, FR-05.14) and quiet in execution; the sentence with an underlined "Open the project" is the product's own voice. It is thin: it shows a list of titles and nothing else, so it reads as a stub of the Tasks page rather than as an archive.
Deterministic scan: clean, 0 findings, exit 0. No overlay.

## Overall Impression
Correct and calm, but the least finished of the slice-5 pages: the one reason to come here is to read what an archived project kept, and it offers titles only, capped at 100.

## What's Working
- The state sentence does the work of a banner without being one.
- Done tasks are struck through and green-marked, open ones dashed: the archive keeps everything and shows what stood where.
- A live project's address redirects to the narrowed task list, so a stale link never shows an empty archive.

## Priority Issues
- [P2] The page stops at 100 tasks and says so without a way on. Why: "Showing the first 100 of N." is the end of the road for a project that kept 300; the rest are unreachable on any screen. Fix: a pager as the Tasks page has, or load more. Suggested command: /impeccable harden. Product decision: no.
- [P2] A kept row opens nothing. Why: the readOnly row renders the title as a plain span, so a kept task's description, comments and files cannot be read without unarchiving the whole project, which then changes what bots can reach. Fix: open the read-only record column for a kept task, or at least show the facts line (due, tags) live rows have. Suggested command: /impeccable shape. Product decision: yes (whether an archived task may be read in the column; FR-05.12 freezes edits, not reading).
- [P3] Unarchiving takes two steps and the word is missing: "Open the project" lands on Projects with the column open, where Archive/Unarchive sits in the State row. Fix: "Open the project to unarchive it", or the control here. Suggested command: /impeccable clarify. Product decision: no.
- [P3] Open and done kept tasks are intermixed and the sentence counts them as one number. Fix: "1 open, 1 done" in the sentence. Suggested command: /impeccable clarify. Product decision: no.
- [P3] "<- Projects" is a 13px ink-3 link with no coarse-pointer padding (the page-header links on Projects, Tags and Bots all have it). Fix: add the same pointer-coarse padding. Suggested command: /impeccable adapt. Product decision: no.

## Persona Red Flags
**Alex (Power User)**: No keyboard route into a kept task; no search in a list that may be 100+ long.
**Riley (Stress Tester)**: A project with 150 kept tasks shows 100 and a sentence; subtasks of a task beyond the cut vanish from the tree.
**Casey (Mobile)**: Back link is the only way out besides the tab bar, and it is about 20px high; the page has no tab current (Projects has no tab).

## Minor Observations
- The heading carries no mark that the project is archived (the 25% marker used on the Projects page); the sentence has to.
- Empty state "Nothing is kept with this project." is plain and correct, but the Archived line on Projects hides the link for such a project, so it is only reachable by URL.
- The page ends after two rows; the full-height blank is fine for a read-only view.

## Questions to Consider
- Is an archive a place to read or only a place things wait? If read, the rows should open.
- Should "Unarchive" live here, since this page is where a user decides whether to?

Questions skipped: closing critique batch, findings are filed as issues by the coordinator
