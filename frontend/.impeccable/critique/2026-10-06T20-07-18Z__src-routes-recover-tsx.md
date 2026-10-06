---
target: Recover (closing critique)
total_score: 30
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/recover.tsx"
target_fingerprint: "sha256:8edd587a59f74a4707bafbdf34ca0780394f6aadb32f8d63260732b8f635580b"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/recover.tsx
timestamp: 2026-10-06T20-07-18Z
slug: src-routes-recover-tsx
---
⚠️ DEGRADED: single-context (closing critique batch run sequentially, no isolated sub-agents)

Method: closing critique, single context, A then B. Read recover.tsx, AuthScreen.tsx, DESIGN.md (auth screens), the slice-5 brief and F-12 (FR-12.15 to .19); viewed recover-desktop-dark and recover-phone-light. No browser, no overlay: rendered checks are from screenshots only. Detector over login/signup/recover and components/Auth exited 0 with `[]`. The refusal state has no capture; it is judged from source.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Loading on the button; the lede names what will happen |
| 2 | Match with real world | 3 | "The code the superuser gave you" is how it was obtained |
| 3 | User control and freedom | 3 | "Back to sign in"; no tries-left count by design (FR-12.18) |
| 4 | Consistency and standards | 3 | Same grammar as sign-up; recover's refusal is inline, the other two screens' are not |
| 5 | Error prevention | 3 | Monospace code with an XXXX template; autocomplete one-time-code; code trimmed |
| 6 | Recognition rather than recall | 3 | The template placeholder shows the shape of the code |
| 7 | Flexibility and efficiency | 3 | Paste works; one tap after |
| 8 | Aesthetic and minimalist design | 4 | Two fields, one action, one link |
| 9 | Error recovery | 3 | One refusal line (late colour, role=alert) beside the code in the API's words; draft kept; no next step named |
| 10 | Help and documentation | 2 | The lede says where the code comes from; a failed code gets no next step |

**Total: 30/40.** Verdict: ships with notes.

## Design Specificity Verdict
LLM assessment: specific. A recovery screen that says in its lede exactly what spending a code does ("It creates a new passkey and signs you out everywhere else") and sets the code in letter-spaced monospace is a screen that knows the product's recovery model, not a "forgot password" page.
Deterministic scan: clean, 0 findings, exit 0. No overlay.

## Overall Impression
The best-judged of the four: it explains the irreversible consequence before the click and says refusals beside the field. Its gap is the last mile when the code is refused.

## What's Working
- The lede does the confirmation, so no modal is needed.
- The code field's monospace with 0.12em tracking and the template make a 16-character code easy to check against the superuser's message.
- A dismissed prompt is not reported as failure; wrong, spent and expired codes read the same (FR-12.18), so the screen cannot be used to probe codes.

## Priority Issues
- [P2] A refused code ends in a dead end. Why: a code that expired after 24 hours or burned after five tries needs the person to ask the superuser for a new one, and the refusal line (the API's one sentence) is the only place that can say so; the lede says it only before the failure. Fix: append "Ask the superuser for a new code." to the refusal. Suggested command: /impeccable clarify. Product decision: no.
- [P3] While a refusal stands, only the late-coloured line marks it; the code field's hairline stays neutral, unlike the Paperless form in Settings. Fix: draw the hairline in late until the field changes. Suggested command: /impeccable polish. Product decision: no.
- [P3] Label 12.5px ink-3 against a 16px template placeholder, which reads as typed text. Fix: placeholder 14px ink-3. Suggested command: /impeccable typeset. Product decision: no.
- [P3] The Email field gives no hint that it must be the account's own address, and a typo gives the same refusal as a wrong code (by FR-12.18). Fix: placeholder "Your account's email". Suggested command: /impeccable clarify. Product decision: no.

## Persona Red Flags
**Jordan (First-Timer)**: Arrives with a message from the superuser; "creates a new passkey" is not previewed, and the next thing is the browser sheet.
**Casey (Mobile)**: Pastes the code from a chat app; the tracked monospace template fits 16 characters at 390px (placeholder visible in the capture).
**Riley (Stress Tester)**: Five wrong tries burn the code and the screen never says how many are left (by design); lowercase and trailing-space handling is not verified.

## Minor Observations
- Known and still true: no "tries left" by FR-12.18; label column 76px against the mock's 88px.
- The refusal sits between the code field and the button, where the eye is.

## Questions to Consider
Questions skipped: closing critique batch, findings are filed as issues by the coordinator
