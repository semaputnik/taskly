---
target: Project column (closing critique)
total_score: 28
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/components/Projects/ProjectPanel.tsx"
target_fingerprint: "sha256:4791d87739634e9334bfc141b25019f7841a35a157dc4f40e00fb88046073d04"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/components/Projects/ProjectPanel.tsx
timestamp: 2026-10-06T20-03-37Z
slug: src-components-projects-projectpanel-tsx
---
⚠️ DEGRADED: single-context (closing critique batch run sequentially, no isolated sub-agents)

Method: closing critique, single context. Read source (ProjectPanel.tsx, RecordPanel.tsx bar, ProjectLine.tsx), DESIGN.md (Project column, New-project draft, Record column), PRODUCT.md, CONTEXT.md, the slice-5 surface brief and the changelog-projects mock (its column), and viewed project-column-{desktop,phone}-{light,dark} and project-draft-{desktop,phone}-{light,dark}. Detector `impeccable detect --json` over components/Projects exited 0 with `[]` (the scanner reads .tsx: a probe with a side-tab border returned a finding, exit 2). No browser, no overlay: rendered checks are from screenshots only.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Every field saves as it is made; a toast on archive; the walk position "2 of 4" and the bar date say where you are |
| 2 | Match with real world | 3 | "Open the list ->", "Active / Archive", "No bot user has it in scope" are plain |
| 3 | User control and freedom | 3 | Archive reverses with Unarchive; Escape and Close; Delete is restorable from the activity log and says so |
| 4 | Consistency and standards | 3 | Same document shape as the task and bot columns: bar, name, property list, hairline sections |
| 5 | Error prevention | 2 | Archive is one click with no word on what it does to bots, and no confirm |
| 6 | Recognition rather than recall | 3 | Tasks, bots and state on one property list; the first five tasks and five log lines in place |
| 7 | Flexibility and efficiency | 3 | Capture line files straight into the project; Down/Up walk; "N more in the list ->" |
| 8 | Aesthetic and minimalist design | 3 | Flat and short; the resize grip on the Description field is the one stray piece of browser chrome |
| 9 | Error recovery | 3 | Empty name refused with the old name kept; a failed fetch is an alert with Try again |
| 10 | Help and documentation | 2 | The Inbox explains itself; nothing explains what archiving does to bots or to the open tasks |

**Total: 28/40.** Verdict: ships with notes.

## Design Specificity Verdict
LLM assessment: specific. The column is a document with the project's own questions answered in the property list (what is open, who works here, is it live) and a capture line that files into this project, so writing a task from here costs nothing. A generic version would be a tabbed settings form. The "Add a task to Website relaunch..." line with its `C` key cap is product-specific.
Deterministic scan: clean, 0 findings, exit 0. No overlay.

## Overall Impression
A good column that earns its place. The biggest opportunity is the one irreversible-feeling control, Archive, which changes what bots can reach and says nothing about it; the second is a phone bar that shows "P..." instead of the date alone.

## What's Working
- The capture line at the head of Open tasks: a project's column is the place to write into that project, and the placeholder says so.
- State row as one control both ways ("Active" + Archive, "Archived - read-only until it comes back" + Unarchive): archiving is a state, not a step toward deletion.
- The draft pins its foot to the bottom with "It opens here, ready for its first task." and one primary; nothing is written until Create.

## Priority Issues
- [P2] Archive does not say what it takes away. Why: archiving makes the project invisible to bot users at once (PRODUCT), and the State row, the toast ("moved to the archive") and the click carry no word of it; a bot mid-task simply starts failing. Fix: when `working` bot users exist, say "release-bot will lose access" beside Archive, or confirm with that sentence. Suggested command: /impeccable clarify. Product decision: yes (sentence versus confirmation).
- [P2] On a phone the bar reads "P... - created 10/06/2026" in all four phone captures. Why: the source hides the word "Project" and the dot below `sm` (max-sm:sr-only, max-sm:hidden) so the date has the room, yet the captures show a truncated "P..." and the dot; `max-sm:` is used nowhere else in the record panels, so either the variant is not taking effect or the bar's truncation clips it. Fix: use the plain `hidden sm:inline` / `sr-only sm:not-sr-only` pair the other panels' pattern would use and re-capture. Suggested command: /impeccable adapt. Product decision: no.
- [P3] The Tasks row wraps inside its own fact on a phone ("3 open - 1 overdue - 0" / "done") and prints "0 done", which the Projects page leaves out ("a zero is left out"). Fix: keep each fact whole and drop zero facts as the line does. Suggested command: /impeccable polish. Product decision: no.
- [P3] The Description field is a native textarea with the browser's resize grip visible in every capture (column and draft), in a system with no other resizable thing. Fix: no resize, grow with the text. Suggested command: /impeccable polish. Product decision: no.
- [P3] The draft's Create project is dimmed with an empty name and nothing says why; the name field takes a heavy boxed focus ring. Fix: keep the primary enabled and refuse an empty name in words under the field, as the tag draft does for a refused name. Suggested command: /impeccable harden. Product decision: no.

## Persona Red Flags
**Alex (Power User)**: Capture line has `C`; Down/Up walks the projects; no keyboard route to Archive or Delete.
**Jordan (First-Timer)**: "Backlog", "overdue", "Archive" are all unexplained here; the bar date reads 10/06/2026 (known).
**Casey (Mobile)**: "P..." in the bar; the "Open the list ->" action falls to the end of a wrapped row; the foot "Delete project" sits far below on a long column; 44px targets exist in source.
**Sam (Accessibility)**: Column is a landmark named for the record and the H2 repeats the name; Delete turns red only on hover (known), so its danger is carried by its icon and word only.

## Minor Observations
- The row tint on the open line is a left-to-right fade: lovely on desktop, but it fades before the count at the right, so the count link sits on the page ground.
- "9775 days late" is fixture data, not a defect.
- Delete and the inherited confirmation dialog are the shadcn kit (known).

## Questions to Consider
- If Archive is the consequential act, should it sit at the foot beside Delete rather than in the property list?
- Should a project's column show which bot users act on its tasks this week, not only which have it in scope?

Questions skipped: closing critique batch, findings are filed as issues by the coordinator
