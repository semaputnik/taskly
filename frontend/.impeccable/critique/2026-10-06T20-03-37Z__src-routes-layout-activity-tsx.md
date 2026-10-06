---
target: Activity (closing critique)
total_score: 28
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/_layout/activity.tsx"
target_fingerprint: "sha256:0a6c29359333dd6ac2f65060c5b692a4b161a2f5774769bb34e0a044e2a2cc58"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/_layout/activity.tsx
timestamp: 2026-10-06T20-03-37Z
slug: src-routes-layout-activity-tsx
---
⚠️ DEGRADED: single-context (closing critique batch run sequentially, no isolated sub-agents)

Method: closing critique, single context. Read source (activity.tsx, ActivityLog.tsx grid, ActivityDescription.tsx links, ActivityFilters.tsx), DESIGN.md (Activity page, Activity chronology), PRODUCT.md, CONTEXT.md, the slice-4 activity snapshot (2026-10-06T09-31-00Z, 28/40) and the changelog-activity mock, and viewed activity-{desktop,phone}-{light,dark}. The fixture log has 14 entries, all by "You", none deleted, so bot-actor lines (ink), Restore and the deleted-bot label are judged from DESIGN.md and source, not from captures. Detector over activity.tsx and components/Activity exited 0 with `[]` (the scanner reads .tsx: a probe returned a finding, exit 2). No browser, no overlay.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Counts sentence, day group counts, the pager says "14 entries"; polite live region |
| 2 | Match with real world | 3 | "created Call the bank in Inbox", "Anything that happened", "By anyone" are the log's own words |
| 3 | User control and freedom | 3 | Filters visible and clearable, order reversible; Restore is the way back from a delete |
| 4 | Consistency and standards | 3 | Same filter row and control language as the Tasks page; the heading sits at a different height from the other list pages |
| 5 | Error prevention | 3 | Read-only; Restore behind a confirmation |
| 6 | Recognition rather than recall | 3 | Object names are links to the live record; deleted ones are plain |
| 7 | Flexibility and efficiency | 2 | Kind, actor, project and order, but no date jump and no "since I last looked" |
| 8 | Aesthetic and minimalist design | 3 | Calm; the count "14" appears three times and the actor column leaves a wide gap |
| 9 | Error recovery | 3 | A failed load is not an empty log; Try again |
| 10 | Help and documentation | 2 | Six kinds of change in the kind menu are not glossed (carried from slice 4) |

**Total: 28/40.** Verdict: ships with notes.

## Design Specificity Verdict
LLM assessment: specific. A log set as day groups of one-line sentences with a mono time column, and a bot's lines in ink where the owner's are quiet, is the Changelog world applied to the product's accountability promise (every change has a named author). A generic version would be a table with an avatar and a timestamp column.
Deterministic scan: clean, 0 findings, exit 0. No overlay.

## Overall Impression
Precise and legible, and as the closing proof of the Changelog idea it is the best page. Its weakness is the product's own first use case: coming back after a while and asking what the bots did. The page has no way to start from "since".

## What's Working
- The sentence is the log's own account: "Every change in your account, newest first. 14 entries, none of them by your bot users."
- The time column in tabular mono, never wrapping, with the full date on hover.
- On a phone the grid collapses to time and actor above the sentence, which keeps the sentence at full width.

## Priority Issues
- [P2] The page cannot answer "what happened while I was away". Why: PRODUCT lists checking what a bot user changed as a core moment; the log is paged at 50 and filtered by kind, actor and project only, so a user who left for a week pages from the top and has to recognise where they stopped. Fix: a "Since" date in the filter row, or an unobtrusive "You were last here" divider. Suggested command: /impeccable shape. Product decision: yes.
- [P2] The heading sits about 10px higher than on Projects, Tags and Bots (y 39 against 49 in the desktop captures), so the title jumps when moving between those nav items. Why: those pages hold a text action at the heading's right and Activity has none, and the row height is set by the action. Fix: give the heading row the same minimum height. Suggested command: /impeccable layout. Product decision: no.
- [P3] The count "14" is stated three times in one view: the sentence, the day heading, the pager line. Fix: drop the pager line while there is one page. Suggested command: /impeccable distill. Product decision: no.
- [P3] The actor column is a fixed 136px, leaving about 150px of empty space between "You" and the sentence on desktop (x 410 to 558); a reader's eye hops a gap on every line. Fix: size the column to the longest actor name on the page. Suggested command: /impeccable layout. Product decision: no.
- [P3] Carried from slice 4: Restore on a lone task opens a confirmation (needs a decision), and the kind menu's six words are not glossed.

## Persona Red Flags
**Alex (Power User)**: Filters in the URL; no key to move between days; no date jump.
**Jordan (First-Timer)**: "Anything that happened" and "By anyone" explain themselves; the six kinds do not.
**Sam (Accessibility)**: Object names are links distinguished by weight and colour from the quieter sentence, with an underline on hover only; the time carries its full date on hover only, which a keyboard user cannot reach.
**Casey (Mobile)**: Four filters wrap to two rows and take about 100px before the first entry; "Newest first" at the row's right is out of reach.

## Minor Observations
- The page runs to 1390px on a phone for 14 entries; paging at 50 is long on a thumb.
- The tab bar composited mid-page is a capture artifact.
- Time reads 09:39 PM in 12-hour form while the bar dates read 10/06/2026 (known).

## Questions to Consider
- Should the log mark where bot activity began after the owner's last visit, instead of asking the owner to filter for it?
- Should consecutive lines by the same actor on the same record fold into one ("moved three times")?

Questions skipped: closing critique batch, findings are filed as issues by the coordinator
