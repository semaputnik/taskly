---
target: Projects page (closing critique)
total_score: 28
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/_layout/projects.tsx"
target_fingerprint: "sha256:6ed934aac0791d727a8cb70e00e2d5d859123f0d59debc166fb97aa7c9dbe71d"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/_layout/projects.tsx
timestamp: 2026-10-06T20-03-37Z
slug: src-routes-layout-projects-tsx
---
⚠️ DEGRADED: single-context (closing critique batch run sequentially, no isolated sub-agents)

Method: closing critique, single context. Read source (projects.tsx, ProjectLine.tsx, backend read_projects), DESIGN.md (Projects page, Project column, New-project draft), PRODUCT.md, CONTEXT.md, the slice-5 surface brief and the changelog-projects mock, and viewed projects-{desktop,phone}-{light,dark} plus project-draft-{desktop,phone}-{light,dark} (the Archived section is in the projects captures). Detector `impeccable detect --json` over the route and components/Projects exited 0 with `[]`; the scanner was proven to read .tsx with a probe file (a side-tab border returned a finding, exit 2). No browser, no overlay: rendered checks are from screenshots only.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Counts sentence in words, skeleton of the line's shape, open line tinted; no in-page failure state (a failed fetch falls to the root error screen) |
| 2 | Match with real world | 3 | "N open ->", "release-bot works here", "2 tasks kept with it" say what the number is for |
| 3 | User control and freedom | 3 | Archive and Unarchive are one control both ways; the column closes with the page intact |
| 4 | Consistency and standards | 3 | Same line anatomy as Tags and Bots; bots.tsx still carries its own copy of the section heading |
| 5 | Error prevention | 3 | The Inbox cannot be archived or deleted and says why; Delete names the tasks it takes |
| 6 | Recognition rather than recall | 3 | Facts (overdue, Backlog, Review, which bot works there) sit on the line, so nothing needs opening |
| 7 | Flexibility and efficiency | 3 | Count link goes straight to the narrowed list; Down/Up walk the lines; "+ New project" is the only creator, no shortcut |
| 8 | Aesthetic and minimalist design | 3 | Hairlines and words only; a "Projects 3" group heading repeats the H1 directly above it |
| 9 | Error recovery | 2 | Draft keeps its text; but list order is undefined and a failed load has no local retry |
| 10 | Help and documentation | 2 | The Inbox line has no hint of what the Inbox is; how to archive is only learnt inside the column |

**Total: 28/40.** Verdict: ships with notes.

## Design Specificity Verdict
LLM assessment: specific. The count at the right is a link into the task list, the bots that work in a project are named on its line, and the Archived section is a quiet continuation rather than a second screen. A generic projects page would be cards or a table with progress bars; this one is a ruled log. The archived marker at 25% opacity and the ink-3 name say "kept, not live" without a badge.
Deterministic scan: clean, 0 findings, exit 0 (probe proved .tsx is scanned). No overlay was available. Nothing the detector could add that the review missed.

## Overall Impression
A calm, faithful page: it does one job (which project, how much is open, who works there) in a handful of words per line. The weakest point is not visual but structural: the order of the lines is not defined by the API, so the page can rearrange itself between loads.

## What's Working
- The line carries the facts a reader would otherwise open the project to find; "1 overdue" is the only colour on the page and it earns it.
- The Archived group says "Read-only until unarchived" once, in the heading, instead of on each line, and its count link ("2 tasks ->") is quieter than the live one.
- The draft is the real column, not a dialog: name focused, one primary at the foot, nothing written until Create.

## Priority Issues
- [P2] The order of the projects is undefined. Why: `read_projects` selects with offset and limit and no ORDER BY, and the captures show it: Inbox, Website relaunch, Home on desktop but Home, Inbox, Website relaunch in the light phone capture, with the column's "n of 4" walk position changing with it. A user who has learnt where Inbox sits will lose it. Fix: order the query (Inbox first, then created or name) for live and archived alike. Suggested command: /impeccable harden. Product decision: no.
- [P2] Archiving a project does not say what it does to the bots that work there. Why: PRODUCT says an archived project is invisible to bots at once, yet the line and the column show "release-bot works here" and Archive beside "Active" with no word on the consequence. Fix: when bot users have it in scope, say "release-bot will lose access" beside the control. Suggested command: /impeccable clarify. Product decision: yes (a sentence or a confirmation).
- [P3] The Inbox, the one project every user has, has no line of explanation (the mock gives "Where a task lands when it names no project."). Fix: a built-in description on the Inbox line. Suggested command: /impeccable clarify. Product decision: no.
- [P3] The mock marks an archived project with the day it was archived ("archived 12 Sept"); the build says only "N tasks kept with it", so two archived projects cannot be told apart by age. Fix: add the day if the API carries it. Suggested command: /impeccable clarify. Product decision: no.
- [P3] A "Projects 3" group heading sits under the "Projects" H1 and above a sentence that already says "3 projects". Fix: drop the live group's heading and keep Archived's. Suggested command: /impeccable distill. Product decision: yes.

## Persona Red Flags
**Alex (Power User)**: Down/Up walks the lines and the count link is one click; there is no key for "new project" (C is capture of a task) and Archive is reachable only through the column.
**Jordan (First-Timer)**: The Inbox line says "1 in Backlog" and nothing else; "Backlog" is unexplained; nothing on the page says how to archive.
**Casey (Mobile)**: "+ New project" sits top right, out of the thumb zone, with a 44px target in source; the phone line wraps the facts to two rows when a bot works there; Projects has no tab in the bar, so no tab is current on this page.

## Minor Observations
- The draft's name field takes a heavy boxed 2px focus ring in a world of flat fields; it is a valid indicator but the loudest thing on the page. The disabled "Create project" at 40% reads as broken until a name is typed and nothing says a name is needed.
- The Description field shows the browser's resize grip (draft and column, both sizes).
- The date in the bar reads 10/06/2026 (known).
- Native tab order is name, then count link per row: two stops per project, which is right.

## Questions to Consider
- Should the Inbox be pinned above a "Projects" group of its own, since it is not a project the user made?
- Would "N open" be better as a bar showing open against done, or is the absence of progress the point?

Questions skipped: closing critique batch, findings are filed as issues by the coordinator
