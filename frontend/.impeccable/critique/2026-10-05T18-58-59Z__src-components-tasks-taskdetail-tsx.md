---
target: task panel and record column (slice 2)
total_score: 30
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-ace929aa05201fc44/frontend/src/components/Tasks/TaskDetail.tsx"
target_fingerprint: "sha256:baf47324f0654817086c334204c7e0941cd2917a6ad38b8d25f691c9afae9820"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-ace929aa05201fc44/frontend/src/components/Tasks/TaskDetail.tsx
timestamp: 2026-10-05T18-58-59Z
slug: frontend-src-components-tasks-taskdetail-tsx
---
Method: dual assessment. A: the finish reviewer (read-only, over source, the surface brief, the approved mock and sixteen captures: desktop 1440x900 and phone 390x844, both themes, column top and bottom, draft, notice) plus the parent's own reading of the captures after the fixes. B: mechanical detector (`impeccable detect --json`) over the Tasks, Records, CaptureLine and Toaster sources: 0 findings. Repeat critique of redesign slice 2 at the end of #160, scored on the build after the finish-review fixes.

## Detector (B)
0 findings.

## Design Health Score (A)

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Status mark and Priority row say state in colour; subtask progress `1/3`; notices name what was made; Activity shows "Loading..." in words |
| 2 | Match with real world | 3 | "opened by you", "kept in Taskly", "bot user" tag on bot comments; dates are numeric (10/05/2026) where the mock has "24 Sept", ambiguous next to the day page's "Today" |
| 3 | User control and freedom | 3 | Undo on capture, on a deleted comment; Escape and Back close the column; Undo of a captured task that has since gained subtasks now says so instead of doing nothing |
| 4 | Consistency and standards | 3 | One section component, one gutter, one row look across task, project, tag and bot panels; the three non-task panels keep their old header and the old muted-foreground token |
| 5 | Error prevention | 3 | Draft asks before it is discarded; refused saves keep the typed words; the single destructive control is at the foot, away from the close control |
| 6 | Recognition rather than recall | 3 | Every property has a visible label; chevrons appear on hover and always on touch; the walk count "1 of 2" says where the reader is in the list |
| 7 | Flexibility and efficiency | 3 | Capture line, `c`, up/down walking, Ctrl/Cmd Enter posts a comment; the walking arrows also steal the column's own scrolling (#169) |
| 8 | Aesthetic and minimalist design | 4 | Hairlines at two strengths, one 36px edge, colour only for state; the changelog chronology reads as the product's own voice |
| 9 | Error recovery | 3 | Failed history load says so with Try again; refused creates hand the title back; a capture refused in silence no longer refills the line |
| 10 | Help and documentation | 2 | Empty Activity and empty Subtasks teach; "Enter creates it here" hint; nothing says what the up/down keys do |

**Total: 30/40** (slice 1: 27/40).

## Priority issues
- [P2] Down/up arrows walk the list even when the column has more to read, so a freshly opened long task cannot be read with the keyboard arrows - needs a product decision (#169).
- [P2] Dates are numeric in the bar, the Due row and Created. A task due today could read "Today" in the Due row as the subtask lines do - needs a decision on whether the product's numeric day rule has an exception for today.
- [P3] The own comment keeps the space of its hidden Edit and Delete, so a bot comment and an own comment have different rhythm.
- [P3] The subtask status mark is a 26px target on touch while the rest of the column grows to 44px (passes 2.5.8).
- [P3] Project, tag and bot panels still use the old bordered header and muted-foreground token; they belong to their own slice.

## Fixed after the finish review (before scoring)
- Draft description sat 12px right of its heading and showed a resize grip; it now shares the task's own description field.
- The notices' protruding round close chip (not in the mock, 20px target) is now a quiet 24px control inside the notice (44px on touch).
- The rule above the property list and above Delete task ran edge to edge; both are inset to the gutters like every other rule.
- The Due row's "Not set" wrapped in the narrow value column.

## Settled, noted as cost
P1 red equals overdue red; the Priority row is coloured (hue lives on the status mark and the Priority row); numeric dates follow the product's one way to write a day; the page behind a full-screen column on a phone is covered but not inert.
