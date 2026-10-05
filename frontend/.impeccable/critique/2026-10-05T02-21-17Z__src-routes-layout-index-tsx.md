---
target: app shell and day page (slice 1)
total_score: 27
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 1
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a181eab3bd1e90294/frontend/src/routes/_layout/index.tsx"
target_fingerprint: "sha256:ef596d27b7eee212fce2036be71d73d3748269ceb2d287f65499334ea941fe05"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a181eab3bd1e90294/frontend/src/routes/_layout/index.tsx
timestamp: 2026-10-05T02-21-17Z
slug: src-routes-layout-index-tsx
---
Method: dual-agent (A: design review sub-agent, read-only, over source and ten captures · B: mechanical detector, run once in the parent over the slice's markup files after DESIGN.md was regenerated). Repeat critique of redesign slice 1 at the end of #140.

## Detector (B)
0 findings against the new DESIGN.md (the 21 advisory "font size outside DESIGN.md" findings of the first run came from the stale teal-era DESIGN.md and are gone with it).

## Design Health Score (A)

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Real counts, weight-only active nav, same-shape skeletons; one Suspense boundary waits for the slowest request |
| 2 | Match with real world | 3 | Calm voice; "23 of the 47 changes so far" asks for arithmetic |
| 3 | User control and freedom | 3 | Undo receipts, inline Restore; undo of a ticked In progress task lands in To do (FR-01.5) |
| 4 | Consistency and standards | 3 | One row component; "In my hands" vs glossary "My work"; due fact restates its band |
| 5 | Error prevention | 3 | Recoverable one-tap actions; 26px mark beside the title link |
| 6 | Recognition rather than recall | 3 | Status by glyph alone in the bands |
| 7 | Flexibility and efficiency | 2 | `c` is the only accelerator; no row navigation (outside slice 1) |
| 8 | Aesthetic and minimalist design | 3 | Clean; repeated "Today" facts, owner's own lines padding the log |
| 9 | Error recovery | 2 | Scored on a build where an activity failure took the bands down; fixed after scoring (the bands now stand, only the sentence's bot half and the Changes log go) |
| 10 | Help and documentation | 2 | Empty states teach; no gloss of the glyph set |

**Total: 27/40** (first run in #140, before the finish-review fixes: 26/40).

## Priority issues
- [P1] Activity failure took out the bands and was misreported — FIXED after scoring (BotChanges has its own boundary; bands read tasks only).
- [P2] Band rows never say whose task it is (a late task on a bot user looks like the owner's) — needs a product decision; candidate for the task-list slice.
- [P2] The lede's bot clause and the 8-line log dilute "what did my bot users do": owner's own lines take most of the preview — needs a decision (bot-only preview, or folded own lines).
- [P2] The due fact repeats its band ("Today" under Due today) — candidate distill.
- [P3] "In my hands" vs CONTEXT.md "My work" — align the heading or record the UI label in CONTEXT.md.

## Settled, noted as cost
P1 red equals overdue red; My work repeats band rows (FR-06.7 + FR-06.11); two Add a task entries on desktop (nav entry specified in #135); zero-padded 12h time in en-US.
