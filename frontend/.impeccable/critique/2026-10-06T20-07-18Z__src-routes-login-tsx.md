---
target: Sign in (closing critique)
total_score: 29
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/login.tsx"
target_fingerprint: "sha256:dd3700cf280a50d4749c93203e4b2f144d28c3fbe1727ed498996272ff6c30b8"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/login.tsx
timestamp: 2026-10-06T20-07-18Z
slug: src-routes-login-tsx
---
⚠️ DEGRADED: single-context (closing critique batch run sequentially, no isolated sub-agents)

Method: closing critique, single context, A then B. Read login.tsx, AuthScreen.tsx, DESIGN.md (auth column, auth-heading), the slice-5 brief and F-12; viewed signin-desktop-light and signin-phone-dark (the other variants share the layout). No browser, no overlay: rendered checks are from screenshots only. Detector over login/signup/recover and components/Auth exited 0 with `[]`. The failure state has no capture; it is judged from source (useAuth routes errors through reportUnlessDismissed).

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | The button shows loading; the background autofill ceremony is silent by design |
| 2 | Match with real world | 3 | "Sign in with a passkey" is plain; "Pick a passkey here" is odd in a field labelled Email |
| 3 | User control and freedom | 3 | Recovery and sign-up links under the button; a dismissed prompt is not reported |
| 4 | Consistency and standards | 3 | Same column, offset and field grammar as sign-up and recover |
| 5 | Error prevention | 3 | Nothing to mistype; the unsupported-browser state replaces the action |
| 6 | Recognition rather than recall | 3 | Both ways to a passkey (field, button) are visible |
| 7 | Flexibility and efficiency | 4 | Passkey autofill waits from page load; one tap signs in |
| 8 | Aesthetic and minimalist design | 3 | Wordmark, heading, lede, one field, one button, two links |
| 9 | Error recovery | 2 | A refused sign-in is reported by a toast, away from the button (recover says it inline); no on-screen next step |
| 10 | Help and documentation | 2 | The lede explains the mechanism; a new device with no passkey gets only the two links |

**Total: 29/40.** Verdict: ships with notes.

## Design Specificity Verdict
LLM assessment: specific. No card, no split screen, no mark, a heading at one fixed offset across the three auth screens, and "Self-hosted at <host>" in the foot (the real fact every passkey is bound to) make it read as this product.
Deterministic scan: clean, 0 findings, exit 0. No overlay.

## Overall Impression
The quietest and most confident screen of the redesign. The email field that takes no email is the only thing that makes a person stop; everything else is one action wide.

## What's Working
- One filled action: ink on the page, 44px (48px on touch), full width, with the key icon naming what it will do.
- The two links are ordered by who needs them: "Lost every passkey?" before "New here?", each with a lead-in so the link text can be short.
- The foot carries the appearance control, so a person can change the theme without an account.

## Priority Issues
- [P2] A sign-in failure is reported by a toast, not at the action. Why: the screen's failure surface is the one case where a passkey is refused or none is found, and recover already says its refusal in place (role=alert, late colour); the person must look away from the button to learn it failed. Fix: one inline role=alert line under the button with the same refusal copy as recover. Suggested command: /impeccable harden. Product decision: no.
- [P3] Label (12.5px) and placeholder (16px) are both ink-3 and the placeholder is the larger, so on every auth screen the hint outweighs the label and "Pick a passkey here" can read as a typed value. Fix: label 13px ink-2, placeholder 14px ink-3. Suggested command: /impeccable typeset. Product decision: no.
- [P3] A new device with no passkey gets no pointer at the point of failure. Fix: name "Use a recovery code" and "Create an account" in the failure line. Suggested command: /impeccable onboard. Product decision: no.

## Persona Red Flags
**Jordan (First-Timer)**: Types an email into a field that ignores it; the lede says passkeys are offered "in the email field or by the button" and never says nothing typed is needed (decision #212 keeps the field).
**Sam (Accessibility)**: Field label is 12.5px ink-3 on the page (contrast not measured); the failure is a toast, announced only if the toast region is live (not verified).
**Casey (Mobile)**: 48px action, links get 44px targets on touch; the action sits in the upper third, within thumb reach.

## Minor Observations
- Known and still true: the field deviates from the mock on purpose (#212); label column 76px, not the mock's 88px.
- At 860px tall the screen is two thirds blank under the links; generous by design.

## Questions to Consider
Questions skipped: closing critique batch, findings are filed as issues by the coordinator
