---
target: Bots, the bot user's column and its webhooks (slice 4)
total_score: 29
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:frontend/src/routes/_layout/bots.tsx"
target_path: frontend/src/routes/_layout/bots.tsx
timestamp: 2026-10-06T09-30-00Z
slug: src-routes-layout-bots-tsx
---
Method: finish review (read-only reviewer over source, the slice-4 brief, the approved bots and phone-navigation mocks and 32 captures: desktop 1440x900 and phone 390x844, light and dark, of the Bots page, the column top and webhooks, the deleted bot user's column, the new-bot draft, the capture sheet and the account menu), then the fixes below, a verdict pass over them, then this score on the build after them. Captures were taken on an isolated stack with a bot user holding a token and both webhooks (one delivery delivered, one failed), a bot user without a token and a deleted bot user.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Counts sentence, token state as dot and word, last delivery in words, "last delivery failed" in red on the line |
| 2 | Match with real world | 3 | "Bot user", never "agent"; reach in one sentence; the log's own words for what a bot did |
| 3 | User control and freedom | 3 | Every change saves on its own; Clear and Regenerate confirmed with what is lost; Escape forgets a URL edit; no way back from a webhook Clear |
| 4 | Consistency and standards | 3 | Lines, property list and sections follow the task column; the dialogs, the webhook URL field and the Create and issue token button are still the inherited kit |
| 5 | Error prevention | 3 | A secret cannot be dismissed by accident (Escape and outside clicks refused, "stored" ticked, a second step when uncopied); targets grow to 44px under touch |
| 6 | Recognition rather than recall | 3 | Projects and permissions are said in words on the line; dashed rows say what can never change |
| 7 | Flexibility and efficiency | 3 | Down and Up walk the bot users, state in the URL, a draft in the column like a task |
| 8 | Aesthetic and minimalist design | 3 | Hairlines and words only, as the mock; the phone line is four lines tall for a bot user with both webhooks |
| 9 | Error recovery | 3 | A refused URL is answered in the field in the server's words with the typed text kept; a failed delivery says why and when it is retried |
| 10 | Help and documentation | 2 | The webhook contract is in the OpenAPI description only; the column does not link to it |

**Total: 29/40** (slice 3 task list: 29/40). Verdict: ships. Faithful to the approved mocks, no P0 or P1 left.

## Verification
Touched specs (bots, bot-console, bot-tags, bot-webhooks, token-dialog, activity, task-list, phone, record-panels, destructive-confirmations, day-page) plus design-system (contrast, both themes) and product-voice ran green at --workers=1 on an isolated stack, and then the full suite once (260 tests, both themes in design-system) after the last change. The 44px heights under a coarse pointer and the 16px input sizes were confirmed in source, not in a touch capture.

## Fixed after the finish review (before scoring)
- [P1] The log's time column wrapped "06:34 AM" onto two lines, in the bot column's Activity section too: the column is 4.25rem and the time does not wrap.
- [P2] Filter buttons (and the order menu) were 28px tall on a phone: 44px under a coarse pointer.
- [P2] The new-bot draft and the Issue token dialog used a native date field ("dd.mm.yyyy" beside "10/06/2026"): both use the product's day field, which gained a `min`.
- [P2] The secret field and the webhook URL field were set below 16px on a phone, which makes iOS Safari zoom in on focus.
- [P3] The capture sheet carried a shadow DESIGN.md forbids for a bottom sheet (invisible under the scrim anyway): removed.
- [P3] On a phone the last-use column took a third of the bot line: it joins the facts under `sm`.
- [P3] "the bot can't be restored" said "bot"; a failed delivery said "in 0 ms".

## Priority issues (open)
- [P3] The secret and token dialogs, the Clear and Regenerate confirmations and Delete bot user are the inherited kit (a bordered destructive alert, an outline Copy button, a framed field); they read as another world beside the column. Restyle as plain sentences, a hairline mono field and text actions, keeping the flow as built.
- [P3] Done Green marks "Working" and "Delivered" (token dot, word, delivery verdict), which the Action-Only Colour Rule reserves for done and close; the mock draws them so, and DESIGN.md records it as carried, not precedent.
- [P3] The bot plate sets two initials in mono, which the Mono rule does not cover.
- [P3] The webhook contract has no link from the column.

## Settled, noted as cost
URLs, ids and secrets in mono (DESIGN.md amended; the mock settles it). The secret is shown once: how it is stored at rest (an encrypted value, against FR-11.9's "digest") is with the user. A deleted bot user's column is read-only and still lists what it did.
