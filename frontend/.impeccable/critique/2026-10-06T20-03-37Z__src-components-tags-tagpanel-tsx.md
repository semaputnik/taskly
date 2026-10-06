---
target: Tag column (closing critique)
total_score: 29
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/components/Tags/TagPanel.tsx"
target_fingerprint: "sha256:e376a39c9a7ed0a889a47059f787cc6571d4db122badb2a8953757ea6c53ea9d"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/components/Tags/TagPanel.tsx
timestamp: 2026-10-06T20-03-37Z
slug: src-components-tags-tagpanel-tsx
---
⚠️ DEGRADED: single-context (closing critique batch run sequentially, no isolated sub-agents)

Method: closing critique, single context. Read source (TagPanel.tsx, LookAlike.tsx), DESIGN.md (Tag column), PRODUCT.md, CONTEXT.md, the slice-5 surface brief and the changelog-tags mock (its column), and viewed tag-column-{desktop,phone}-{light,dark}. There is no capture of the New-tag draft, so the draft is judged from DESIGN.md and source only. Detector over components/Tags exited 0 with `[]` (the scanner reads .tsx: a probe returned a finding, exit 2). No browser, no overlay.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Saves as it is made; "4 of 4" walk position; open tasks counted |
| 2 | Match with real world | 3 | "Fold another tag into this one" is a human sentence |
| 3 | User control and freedom | 3 | A rename never merges silently; Cancel in the dialog; no undo after a merge or delete (by product) |
| 4 | Consistency and standards | 3 | Same document shape as the other columns, shorter |
| 5 | Error prevention | 3 | Choosing in the Merge select is only step one; Delete says "Deleting takes it off 2 tasks. This can't be undone." before the dialog says it again |
| 6 | Recognition rather than recall | 3 | Open tasks with their projects in place |
| 7 | Flexibility and efficiency | 3 | Open the list, Down/Up walk, merge from either side |
| 8 | Aesthetic and minimalist design | 3 | Short; a large empty middle by design |
| 9 | Error recovery | 3 | A refused name is said under the field with the words kept |
| 10 | Help and documentation | 2 | Renaming's reach (every task carrying the tag) is not said where you rename |

**Total: 29/40.** Verdict: ships with notes.

## Design Specificity Verdict
LLM assessment: specific. "A tag is a thin record and its column is short" is stated in the source and honoured: three rows, five tasks, one foot. The deletion foot with its reach written in the line beside it is the product's principle (nothing is lost quietly) in layout form.
Deterministic scan: clean, 0 findings, exit 0. No overlay.

## Overall Impression
A short column that does not pretend to be bigger. The merge row and the foot carry all of the product's care; the rename is the one place that changes many records without saying so.

## What's Working
- The foot: the destructive text button with the consequence beside it, in the same line, before any dialog.
- The merge is a separate, confirmed act reachable from either direction, never a side effect of a rename.
- Open tasks carry the project name at the right, so a tag's column reads across projects, which is what a tag is.

## Priority Issues
- [P3] Renaming a tag renames it on every task (FR-01.24) and saves on blur with no word of how many. Why: it is the one multi-record write in the column that is not said where it happens. Fix: a 12.5px line under the name, "Renames it on 2 tasks", while the field has focus. Suggested command: /impeccable clarify. Product decision: no.
- [P3] The Merge row's control reads "choose a tag..." as a bare phrase with a chevron on a phone but none on desktop, so on desktop it looks like a link, not a select. Fix: the same chevron at both sizes. Suggested command: /impeccable polish. Product decision: no.
- [P3] The project name truncates on a phone ("Website r...") in the task lines, as in the Tasks list. Why: the project is half the reason to read this list. Fix: drop the project to the facts line on narrow widths. Suggested command: /impeccable adapt. Product decision: no.
- [P3] On a phone the foot sentence sits below the Delete tag button and the column's blank middle pushes both to the bottom; fine when the list is short, but with five tasks the foot disappears below the fold with no hint it exists. Fix: leave as is unless the foot is made sticky. Suggested command: /impeccable layout. Product decision: yes.
- [P3] Known and still true: Delete tag goes red only on hover; the bar date reads 10/06/2026; the merge dialog is the inherited shadcn kit.

## Persona Red Flags
**Alex (Power User)**: Down/Up and the Merge select; no key for Delete (right).
**Sam (Accessibility)**: Delete is carried by icon and word, not colour, at rest; the select is labelled by its row.
**Casey (Mobile)**: The merge select drops to a second row and the chevron appears there; the foot is not in the thumb zone unless the list is short.
**Riley (Stress Tester)**: A 50-character name, a name with trailing spaces, and a rename into a taken name (opens the merge) are each answered in words; the draft's 50-character limit is in source only.

## Minor Observations
- "Tasks: 2 open . Open the list ->" reads well; "2 in archived projects" appears only when it applies.
- The tag column's tinted source line in the list fades before the count, as on Projects.

## Questions to Consider
- Should the column show the tag's recent activity (who created it, who tagged what) as the project column does, or is thinness the point?
- Would a tag's rename be better as a confirmed act when it is carried by more than a handful of tasks?

Questions skipped: closing critique batch, findings are filed as issues by the coordinator
