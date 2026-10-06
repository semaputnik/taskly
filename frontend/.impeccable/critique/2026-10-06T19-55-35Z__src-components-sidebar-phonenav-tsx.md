---
target: Phone tab bar and capture sheet (closing critique)
total_score: 28
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/components/Sidebar/PhoneNav.tsx"
target_fingerprint: "sha256:d5e6cfdd90873e26b94d2c51030b0d2b5967a367973f20825a4e061f17ad51ee"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/components/Sidebar/PhoneNav.tsx
timestamp: 2026-10-06T19-55-35Z
slug: src-components-sidebar-phonenav-tsx
---
⚠️ DEGRADED: single-context (sub-agent cannot be waited on in this run)

Method: closing critique, single context. Read source (PhoneNav.tsx, capture.tsx), DESIGN.md, PRODUCT.md, the phone-nav mock, and viewed the phone captures: tasks-phone and today-phone (tab bar in place) and task-draft-or-capture-sheet-phone-{light,dark} (the capture sheet over the list). Detector scan ran (clean). No browser, no overlay; touch sizes judged from source.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Current tab by weight and ink, aria-current; no cue that the avatar holds more places |
| 2 | Match with real world | 3 | Today, Tasks, add, Bots, Activity are plain words |
| 3 | User control and freedom | 3 | The sheet closes on Escape or a scrim tap and keeps what was typed |
| 4 | Consistency and standards | 3 | A bottom bar of five with a centre action is a known pattern |
| 5 | Error prevention | 3 | The sheet follows the visual viewport above the keyboard; typed text survives closing |
| 6 | Recognition rather than recall | 2 | Projects, Tags and Settings sit under an unlabelled initial in the top bar |
| 7 | Flexibility and efficiency | 3 | Add from any screen in one tap; "More options..." for the full draft |
| 8 | Aesthetic and minimalist design | 3 | The single filled circle is the only ink block; no shadow on the sheet |
| 9 | Error recovery | 3 | Failure handling belongs to the capture line; not seen in any capture |
| 10 | Help and documentation | 2 | "Goes to Inbox" says where it lands; nothing says Return creates |

**Total: 28/40.** Verdict: ships with notes.

## Design Specificity Verdict
LLM assessment: specific, within a convention. Five columns with a filled add circle is the standard phone nav, but the colourless active state (weight and ink only), the hairline top rule instead of a shadow, and a sheet that is just the capture line with "Goes to Inbox" and "More options..." are authored.
Deterministic scan: `impeccable detect --json` exited 0 with `[]` on this file. The scanner was proven to read .tsx (a probe file with a side-tab border returned findings, exit 2). No browser overlay was available, so rendered checks were judged from screenshots only.

## Overall Impression
Correct and quiet. The cost of that quiet is discoverability: the active tab and the hidden Projects are both signalled very lightly.

## What's Working
- The add circle in the thumb zone raises one line, not a form; the full draft is a deliberate second step.
- The sheet states its destination ("Goes to Inbox") before the reader commits.
- The active tab is marked by ink and weight and announced as current, never by colour.

## Priority Issues
- [P2] Projects, Tags and Settings are only behind an unlabelled initial circle in the top bar. Why: Projects is a primary noun of the product (every task has one) and a first-time phone user will not guess that the avatar opens it. Fix: a labelled "More" in the bar, or give Projects a tab in place of Activity. Suggested command: /impeccable shape. Product decision: yes (which five).
- [P2] The active tab differs by weight and ink at 11px only. Why: Today versus Tasks differ subtly in the captures, especially in dark at a glance. Fix: add a hairline or small mark above the active label, still without colour. Suggested command: /impeccable polish. Product decision: no.
- [P3] The sheet shows no way to save: creating is the keyboard's Return alone, and the only visible action is "More options...". Why: a first-timer sees no way to finish. Fix: a "Return to add" hint or a small Add text action. Suggested command: /impeccable clarify. Product decision: no.
- [P3] Tab labels are 11px with ink-3 for the inactive ones, at the edge of readable. Fix: 12px labels. Suggested command: /impeccable typeset. Product decision: no.

## Persona Red Flags
**Casey (Mobile)**: Add is under the thumb and the sheet rises above the keyboard (good); Settings and Projects need a reach to the top-right avatar, the furthest point from the thumb.
**Jordan (First-Timer)**: An avatar as a menu is not self-evident; the sheet shows no save control.
**Sam (Accessibility)**: The nav has a Main label and current-page state; the add button has aria-haspopup and expanded; scrim tap and Escape both close.

## Minor Observations
- The bar hides while a record column is open, which is right, but leaves no direct way to Today except Back.
- The sheet's drag handle is decorative; drag-to-close could not be verified.
- Full-page phone captures composite the bar mid-page; ignored as instructed.

## Questions to Consider
- Is Bots a daily destination on a phone, or would Projects earn the slot?
- Could the add circle show the destination project when a list is filtered to one?

Questions skipped: closing critique batch, findings are filed as issues by the coordinator
