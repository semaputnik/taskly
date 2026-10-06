---
target: Sign up (closing critique)
total_score: 29
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/signup.tsx"
target_fingerprint: "sha256:f19bafb645f55a9fbb5697b804b1637d64d0f7c6eb3abde6c2acde4efdc638c9"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/signup.tsx
timestamp: 2026-10-06T20-07-18Z
slug: src-routes-signup-tsx
---
⚠️ DEGRADED: single-context (closing critique batch run sequentially, no isolated sub-agents)

Method: closing critique, single context, A then B. Read signup.tsx, AuthScreen.tsx, DESIGN.md (auth screens), the slice-5 brief and F-09/F-12; viewed signup-desktop-light and signup-phone-dark. No browser, no overlay: rendered checks are from screenshots only. Detector over login/signup/recover and components/Auth exited 0 with `[]`. The validation-error and refusal states have no capture; they are judged from source.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Loading on the button; the lede says a passkey is created next |
| 2 | Match with real world | 3 | "Create a passkey and sign in" names both things that will happen |
| 3 | User control and freedom | 3 | "Already have an account? Sign in"; a dismissed prompt is not an error |
| 4 | Consistency and standards | 3 | Same fields, offset and button as recover and sign-in |
| 5 | Error prevention | 3 | Email type, 30-character name limit shared with Settings, validation on blur |
| 6 | Recognition rather than recall | 3 | Both fields labelled; the placeholder says "Optional" |
| 7 | Flexibility and efficiency | 3 | autocomplete=username and name; two fields and one tap |
| 8 | Aesthetic and minimalist design | 4 | Nothing on the screen that is not needed |
| 9 | Error recovery | 2 | A duplicate email or failed ceremony goes to the toast hook, away from the fields |
| 10 | Help and documentation | 2 | Nothing says there is no password and no email recovery (FR-12.1, FR-12.2) |

**Total: 29/40.** Verdict: ships with notes.

## Design Specificity Verdict
LLM assessment: specific, though the least distinctive of the three because a sign-up form is a sign-up form. What makes it this product's is the honest lede ("Your email names the account. The passkey ... is how you will sign in.") and the absence of a password field, a confirmation field and a pitch.
Deterministic scan: clean, 0 findings, exit 0. No overlay.

## Overall Impression
Two fields and a button, correctly. It under-tells the one thing a person creating a passkey-only account should know before committing: a lost device means asking the superuser.

## What's Working
- The primary action names the outcome in both steps, so the browser sheet is no surprise.
- "Optional" as the placeholder of Name settles the question without a second label.
- Validation is on blur with the same wording and limit as the Settings name field.

## Priority Issues
- [P2] The screen never says what losing the passkeys means. Why: sign-up is the only moment to learn there is no password reset and no email recovery, and that recovery goes through the superuser (FR-12.1, FR-12.15); the person finds out at the worst time. Fix: one muted line under the action, e.g. "No password and no email: if you lose every passkey, the superuser issues a recovery code." Suggested command: /impeccable clarify. Product decision: yes (the copy states policy).
- [P2] A refused registration (email already taken, failed ceremony) is reported by a toast, not under the email field. Why: a taken address is a field problem and the person must connect a toast to a field; recover keeps its refusal inline. Fix: set the field error from the refusal. Suggested command: /impeccable harden. Product decision: no.
- [P3] Label 12.5px ink-3 against a 16px placeholder, as on sign-in; the label is smaller than what it labels. Fix: see sign-in. Suggested command: /impeccable typeset. Product decision: no.

## Persona Red Flags
**Jordan (First-Timer)**: Does not know what a passkey is beyond the lede; nothing previews the "biometric or PIN" step (FR-12.5) before the sheet opens.
**Casey (Mobile)**: Fields 44px with autocomplete set; the screen is blank below the link, and the only way back is the text link.
**Riley (Stress Tester)**: A 31-character name shows its error on blur only; behaviour on a pasted email with spaces is not verified.

## Minor Observations
- Known and still true: label column 76px against the mock's 88px.
- No capture of the validation state, so message placement under the hairline is unchecked.

## Questions to Consider
Questions skipped: closing critique batch, findings are filed as issues by the coordinator
