---
target: Task column and task draft/capture (closing critique)
total_score: 28
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/components/Tasks/TaskDetail.tsx"
target_fingerprint: "sha256:baf47324f0654817086c334204c7e0941cd2917a6ad38b8d25f691c9afae9820"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/components/Tasks/TaskDetail.tsx
timestamp: 2026-10-06T19-55-35Z
slug: src-components-tasks-taskdetail-tsx
---
⚠️ DEGRADED: single-context (sub-agent cannot be waited on in this run)

Method: closing critique, single context. Read source (TaskDetail.tsx, capture.tsx, NewTask.tsx outline), DESIGN.md, PRODUCT.md, the task-panel mock, and viewed task-column-{desktop,phone}-{light,dark}. The task-draft-or-capture-sheet desktop captures show only the plain list (the draft is not in the shot), so the draft was judged from source (NewTask.tsx); the phone captures show the capture sheet. Detector scan ran (clean). No browser, no overlay.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 2 | "5 of 5" walk position and a "Not saved yet" bar on a draft, but no saved cue for field edits |
| 2 | Match with real world | 3 | "opened by you, 10/06/2026" reads naturally; "Does not repeat" is wordy |
| 3 | User control and freedom | 3 | Escape closes; Discard / Keep editing guards an unsaved draft; Down/Up walk the list |
| 4 | Consistency and standards | 3 | One property list shape for task, project, bot; the Discard dialog is the inherited kit |
| 5 | Error prevention | 3 | The draft commits in one request, nothing half-written; delete is out of the way |
| 6 | Recognition rather than recall | 3 | Every property labelled; tags removable with a visible x on phone |
| 7 | Flexibility and efficiency | 4 | Enter and Cmd/Ctrl+Enter capture and stay, URL-addressable, walk |
| 8 | Aesthetic and minimalist design | 3 | Plain label/value rows and hairline sections; the Created row is set off-scale |
| 9 | Error recovery | 2 | A blank title is silently ignored; refused saves not visible in any capture |
| 10 | Help and documentation | 2 | "Enter creates it here" hint on subtasks; none for the title's save-on-blur |

**Total: 28/40.** Verdict: ships with notes.

## Design Specificity Verdict
LLM assessment: specific. The record is read as a document: the status mark as the control beside the title, properties as rows, then Description, Subtasks, Files and Activity as hairline sections, and a bar that says how the task came to be. The draft sharing that same layout (ADR-0005) is a real product idea.
Deterministic scan: `impeccable detect --json` exited 0 with `[]` on this file. The scanner was proven to read .tsx (a probe file with a side-tab border returned findings, exit 2). No browser overlay was available, so rendered checks were judged from screenshots only.

## Overall Impression
Confident and uniform with the bot and project columns. The biggest gap is quiet: field edits and the draft's state have almost no feedback.

## What's Working
- The status mark beside the title is the close control: one thing, no extra checkbox row.
- Draft and task share one layout, so "More options..." from the phone sheet lands somewhere familiar.
- The walk position ("5 of 5") with up/down keeps the list context.

## Priority Issues
- [P2] Autosave is silent. Why: properties save when changed and the title on blur, with no "Saved" or error cue in the bar or fields, so a reader cannot tell a failed save from a good one. Fix: a brief text-only "Saved" or error word in the bar. Suggested command: /impeccable harden. Product decision: no.
- [P2] Emptying the title is ignored without a word (the commit does nothing for a blank title). Why: the field snaps back and the reader does not know why. Fix: restore the old title and say "A task needs a title" under the field. Suggested command: /impeccable clarify. Product decision: no.
- [P3] The phone bar truncates "opened by you, date" to "ope..." beside "5 of 5" and the arrows. Fix: drop the counter or let the bar wrap on narrow widths. Suggested command: /impeccable adapt. Product decision: no.
- [P3] The Created row is smaller and lighter than the other values and sits lower than its label (visible on phone). Fix: align baseline and size, or fold it into the bar. Suggested command: /impeccable polish. Product decision: no.
- [P3] Delete task is below the fold on the phone, and Discard and Delete confirmations are the inherited dialog kit, not the product's plain text. Fix: restyle as sentences and text actions. Suggested command: /impeccable polish. Product decision: no.

## Persona Red Flags
**Alex (Power User)**: Strong: keyboard commit, stay-open chord, walk. No keyboard path to set status or priority.
**Sam (Accessibility)**: Status shows the word "Backlog" beside its ring (good); icon-only close, chevrons and tag x depend on accessible names, unverified here.
**Casey (Mobile)**: The full draft is reachable only through "More options..."; Activity and the comment field sit at the end of a long scroll, competing with the keyboard.

## Minor Observations
- The desktop comment box is clipped at the capture's bottom edge ("Ctrl Enter to post" cut off), likely a capture artifact; confirm in a browser.
- "Does not repeat" in muted ink looks disabled rather than unset.
- The draft's Create task button and chord hint exist only in source here; a capture of the open draft would be the evidence.

## Questions to Consider
- Should the column say when it last saved, as the bar already says when the task was opened?
- Does the phone need the walk arrows, or is close enough?

Questions skipped: closing critique batch, findings are filed as issues by the coordinator
