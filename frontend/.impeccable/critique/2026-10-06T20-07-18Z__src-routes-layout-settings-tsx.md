---
target: Settings (closing critique)
total_score: 29
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/_layout/settings.tsx"
target_fingerprint: "sha256:ec6ded415f2ff366d290c083dd45d5f20f9dab3459d9779a834d044c9c07bc81"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/_layout/settings.tsx
timestamp: 2026-10-06T20-07-18Z
slug: src-routes-layout-settings-tsx
---
⚠️ DEGRADED: single-context (closing critique batch run sequentially, no isolated sub-agents)

Method: closing critique, single context, A then B. Read settings.tsx, the Settings components' structure, AuthScreen, DESIGN.md, PRODUCT.md, features F-09/F-12 and viewed settings-{user,superuser-not-connected,superuser-connected,paperless-tested,edit,paperless-form} captures that exist (user desktop dark, user phone light, superuser connected desktop light, paperless-tested desktop light, edit desktop light and phone dark, paperless-form desktop dark, superuser-not-connected phone light). No browser, no overlay: rendered checks are from screenshots only. Detector over the route and components/Settings exited 0 with `[]` (it scans .tsx).

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Toast on connect, "Connected" in green, Test result reads in place; Sessions says nothing about count (known) |
| 2 | Match with real world | 3 | Plain labels; "Kept there", "Issue a recovery code" are human |
| 3 | User control and freedom | 3 | Every edit has Cancel; Delete my account and Disconnect confirm; Sign out everywhere has no confirm by FR-12.13 |
| 4 | Consistency and standards | 3 | One label/value grammar for all sections; label baseline sits ~6px under the value text in every row |
| 5 | Error prevention | 3 | Connect form blocks an empty token; Name and Email can be opened for editing at once |
| 6 | Recognition rather than recall | 3 | State is read in the rows; Appearance shows all three options |
| 7 | Flexibility and efficiency | 2 | No in-page jump, no Users search or paging (known); 54 users put Account ~3000px down |
| 8 | Aesthetic and minimalist design | 3 | Hairlines and text actions only, no cards; the Passkeys note is a six-line block (known) |
| 9 | Error recovery | 3 | Paperless refusal is said beside the field with the instruction under it; a failed edit keeps the draft |
| 10 | Help and documentation | 3 | Each section carries one sentence of what it does; Paperless and Passkeys explain consequences |

**Total: 29/40.** Verdict: ships with notes.

## Design Specificity Verdict
LLM assessment: specific. Settings as one ruled document where each row is a label, a value and the verb that changes it, with the Paperless connection as a state line (Connected, address, Test, Change, Disconnect) rather than a card, is the Changelog world applied to administration. A generic settings page would be tabs and form cards. The superuser's Users list reuses the Projects/Tags line grammar, so the screen reads as part of the same log.
Deterministic scan: clean, 0 findings, exit 0 (route plus components/Settings). No overlay available. No false positives to report.

## Overall Impression
A calm, honest document that makes a lot of state legible without a single card. What is missing is a sense of scale: it is written for an account with a handful of rows and is not told what to do when the superuser's Users list is 54 long.

## What's Working
- The row grammar: "Name  Test User  Change", "Connection  Connected  http://...  Test  Change  Disconnect". Every setting is one line you can scan, and the verb is where the value is.
- Edit in place: Name and Email become hairline fields with Save and Cancel on the same row (below the field on a phone), so nothing opens a dialog for a label.
- The Paperless refusal sits under the field it refused, in the late colour, with the instruction line below it, and Connect/Test/Cancel keep their positions.

## Priority Issues
- [P2] Account (Delete my account) sits below the whole Users list. Why: for the superuser the page is 4,200px tall at 54 users, the order puts the rare admin list ahead of the one irreversible act, and there is no in-page way to reach either; on a phone the foot is a very long scroll. Fix: put Users last, or show the first ten with "Show all 54"; add no tabs. Suggested command: /impeccable layout. Product decision: no.
- [P2] Name and Email can be opened at once with a Save each (settings-edit capture). Why: two live drafts on adjacent rows breaks the document's one-thing-at-a-time grammar, and Save on one does not say what happens to the other. Fix: opening one closes the other, or one Save for the pair. Suggested command: /impeccable harden. Product decision: no.
- [P3] Labels sit lower than their values. In Profile, Sessions, Paperless and Account the label's baseline is about 6px below the value's (Name at y159 against Test User at y153 in the 1280 capture). Why: it is on every row and makes the document look slightly off. Fix: align label and value on one baseline (items-baseline on the row). Suggested command: /impeccable polish. Product decision: no.
- [P3] The post-recovery notice ("Your new passkey is the last one in the list") stacks on top of the always-on Passkeys note, two blocks of explanatory text in a row. Why: the person is told consequences twice. Fix: show the notice in place of the note until dismissed or navigated away. Suggested command: /impeccable distill. Product decision: no.
- [P3] The "Paperless connected" toast covers the Profile heading and Name row on desktop (and is the only confirmation besides the row turning green). Why: the row is already the confirmation; the toast is a second one over content. Fix: drop the toast for Connect, or place it bottom-centre. Suggested command: /impeccable polish. Product decision: no.

## Persona Red Flags
**Alex (Power User)**: No in-page anchors and no search in Users; reaching Account on a long list is a scroll. Nothing on the page says Enter saves or Esc cancels an edit row.
**Sam (Accessibility)**: Destructive intent (Delete, Disconnect) is carried by wording only until hover, never on touch (known); Appearance shows selection by weight and ink, which holds in both themes. Contrast judged from the screenshots only.
**Casey (Mobile)**: Name/Email Save and Cancel drop under the field, good; Users rows are five lines each with "Issue a recovery code" on its own line, which makes the superuser's list very long.
**Riley (Stress Tester)**: Two simultaneous edits; in the paperless-form capture a non-URL address ("not-a-url") shows only the token's error, so the address's own problem is not visible; "Test" next to "Connect" invites connecting untested.

## Minor Observations
- Known and still true: Sessions/Token generic wording, "no passkeys" red on most Users rows, Delete/Disconnect red only on hover, long Passkeys note, 10/06/2026 dates, no Users search or paging, shadcn dialogs, italic "Not set", stale Paperless ids on a different instance.
- The Appearance row sits tight under Email and reads as a third profile field; it is the only row that saves on choosing, and nothing says so.
- "You are the superuser" at the right of the Users heading is the only right-aligned plain text in the document.

## Questions to Consider
Questions skipped: closing critique batch, findings are filed as issues by the coordinator
