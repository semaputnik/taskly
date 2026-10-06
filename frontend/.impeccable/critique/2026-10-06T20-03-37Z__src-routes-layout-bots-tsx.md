---
target: Bots page and bot user column (closing critique)
total_score: 28
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/_layout/bots.tsx"
target_fingerprint: "sha256:20696c2291cc42c6359c3f8f369a8a878b8af69631c925eabc4c575706dd75ac"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/_layout/bots.tsx
timestamp: 2026-10-06T20-03-37Z
slug: src-routes-layout-bots-tsx
---
⚠️ DEGRADED: single-context (closing critique batch run sequentially, no isolated sub-agents)

Method: closing critique, single context. Read source (bots.tsx, BotLine.tsx, the opening of Webhooks.tsx), DESIGN.md (Bots page, Bot line, Bot user's column, Webhooks, Secret reveal), PRODUCT.md, CONTEXT.md, the slice-4 critique snapshot (2026-10-06T09-30-00Z, 29/40) and the changelog-bots mock, and viewed bots-{desktop,phone}-{light,dark} and bot-column-{desktop,phone}-{light,dark}. The fixture bot user has no token and no webhooks, so the working-token, failed-delivery, secret-reveal and deleted-bot states are judged from DESIGN.md and source, not from captures; the column captures end at "On its plate". Detector over bots.tsx and components/Bots exited 0 with `[]` (the scanner reads .tsx: a probe returned a finding, exit 2). No browser, no overlay.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Token state as dot and word; counts sentence says "It made no changes this week."; last delivery in words |
| 2 | Match with real world | 3 | "Bot user", never "agent"; reach in one sentence; "append-only" and "never" are said |
| 3 | User control and freedom | 3 | Every change saves; Clear and Regenerate confirmed with what is lost; a secret cannot be dismissed by accident |
| 4 | Consistency and standards | 3 | Lines, property list and sections follow the task column; bots.tsx still holds its own copy of the heading; dialogs are the inherited kit |
| 5 | Error prevention | 3 | Dashed rows name what can never be granted; Shown-Once rule on secrets |
| 6 | Recognition rather than recall | 2 | The meta line is words with no separators, so "Website relaunch  reads" is read as a clause |
| 7 | Flexibility and efficiency | 3 | Down/Up walk, URL state, draft in the column |
| 8 | Aesthetic and minimalist design | 3 | Hairlines and words only; the webhook rows are the densest part of the product |
| 9 | Error recovery | 3 | A refused URL is answered in the field with the text kept; a failed delivery says why and when it retries |
| 10 | Help and documentation | 2 | The webhook contract has no link from the column (carried from slice 4) |

**Total: 28/40.** Verdict: ships with notes. (Slice 4: 29/40; one point lower for the target-size gap below.)

## Design Specificity Verdict
LLM assessment: specific, the most distinctive screen of the group. The plate that goes grey when the token does not work, the dashed rows for what a bot user can never do, the secret shown once: these are Taskly's own premise (bots held to the narrowest reach) in form. No other tracker would have this page.
Deterministic scan: clean, 0 findings, exit 0. No overlay.

## Overall Impression
Strong and distinctive; the page is about reach and the column tells it truthfully. The gap is the moment PRODUCT names first: "checking what a bot user changed while the human was away". The list shows an aggregate, not per bot.

## What's Working
- The column answers "can this bot do harm" in one scroll: token, projects, permissions, with the impossible rows drawn dashed so the list reads as the whole of it.
- Empty webhooks say what absence means for the bot user ("this bot user is not told about comments") instead of "None".
- Under touch the checkbox rows and actions grow to 44px (in source).

## Priority Issues
- [P2] The bot name link has no coarse-pointer target growth. Why: Project and Tag lines give their name link `pointer-coarse:-my-3 pointer-coarse:py-3`; BotLine's does not, so on a phone the only way to open a bot user's column is a text line about 20px high, and slice 4 recorded targets as growing to 44px. Fix: add the same two classes. Suggested command: /impeccable adapt. Product decision: no.
- [P2] The page gives no per-bot answer to "what did it do". Why: the sentence counts "N changes this week" across all bots and the line shows only "used 3 hours ago"; to see one bot's work the user opens its column and its five latest lines. Fix: "12 changes this week" on the line, linking to the Activity page narrowed to that bot. Suggested command: /impeccable shape. Product decision: yes.
- [P3] The meta line runs token, project, verbs and webhooks together with only a gap between them ("No token  Website relaunch  reads"), and a bot user with two projects reads as "A, B reads, updates". Fix: middot separators or "reaches" and "may" lead words (the screen reader already hears "Projects:" and "Permissions:"). Suggested command: /impeccable clarify. Product decision: no.
- [P3] On a phone "Issue token" drops to its own row and sits 4px right of the text column (124px against 120px). Fix: align it to the value column. Suggested command: /impeccable layout. Product decision: no.
- [P3] Carried from slice 4, still true: the secret and token dialogs and confirmations are the inherited kit; Done Green marks "Working" and "Delivered" outside done and close (DESIGN.md records it as carried); the plate sets mono initials.

## Persona Red Flags
**Alex (Power User)**: No per-bot activity count on the list; Down/Up and URL state are good.
**Jordan (First-Timer)**: "Issue token", "Task ready" and "append-only" are explained on the page; a first bot user is created with only "reads tasks" ticked and no project, which the draft explains.
**Casey (Mobile)**: The name link is the small target; the line is four lines tall with a token and both webhooks.
**Sam (Accessibility)**: Token state is a dot plus a word, never the dot alone; "last delivery failed" is red and in words.

## Minor Observations
- Known: Delete bot user, Clear and Disconnect-style actions go red only on hover; dates read 10/06/2026.
- The projects list in the column is in whatever order the API returns (Home, Inbox in one capture, Inbox, Website, Home in another), same root cause as the Projects page.
- "Set a URL" under each webhook is 13px flat text; 44px on touch.

## Questions to Consider
- If the owner opens this page after a week away, what is the first thing they should see: which bots are alive, or which bots did something they did not expect?
- Should a bot user with no token and no activity for 30 days offer itself for deletion?

Questions skipped: closing critique batch, findings are filed as issues by the coordinator
