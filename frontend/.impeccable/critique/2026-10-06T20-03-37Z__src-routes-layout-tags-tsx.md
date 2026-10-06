---
target: Tags page (closing critique)
total_score: 28
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/_layout/tags.tsx"
target_fingerprint: "sha256:32d697b8e324dd210fe56e199d78260a017f66abba8e9a0809a2268ad56163d7"
target_path: /Users/semaputnikov/Documents/Projects/taskly/.claude/worktrees/agent-a2aa995ef6b1d9c03/frontend/src/routes/_layout/tags.tsx
timestamp: 2026-10-06T20-03-37Z
slug: src-routes-layout-tags-tsx
---
⚠️ DEGRADED: single-context (closing critique batch run sequentially, no isolated sub-agents)

Method: closing critique, single context. Read source (tags.tsx, LookAlike.tsx, TagLine.tsx), DESIGN.md (Tags page, Tag column), PRODUCT.md, CONTEXT.md, the slice-5 surface brief and the changelog-tags mock, and viewed tags-{desktop,phone}-{light,dark}. Detector over the route and components/Tags exited 0 with `[]` (the scanner reads .tsx: a probe returned a finding, exit 2). No browser, no overlay: rendered checks are from screenshots only. The fixture has four tags, one look-alike group, all created by the user.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Counts sentence; both requests read together so suggestions never push the lines down |
| 2 | Match with real world | 3 | "Look alike", "Merge into Urgent", "Keep apart" are plain words |
| 3 | User control and freedom | 3 | Keep apart dismisses a suggestion; a merge is confirmed and says it cannot be undone |
| 4 | Consistency and standards | 3 | Same grid as Projects with a tag glyph for the marker; never a pill |
| 5 | Error prevention | 3 | A rename that hits a used name opens the merge confirmation instead of merging |
| 6 | Recognition rather than recall | 3 | The suggested spelling is named in the action; created-by is on every line |
| 7 | Flexibility and efficiency | 2 | No search, no sort, no way to find an unused tag; one-step merge from the group line is good |
| 8 | Aesthetic and minimalist design | 3 | "created by you" repeats on every row and says nothing when all are the owner's |
| 9 | Error recovery | 2 | Merge and tag delete cannot be undone (PRODUCT); the confirmations carry that, no other recovery |
| 10 | Help and documentation | 3 | The sentence says tags are created by typing them onto a task, too |

**Total: 28/40.** Verdict: ships with notes.

## Design Specificity Verdict
LLM assessment: specific. Putting the "look alike" group above the list, as a sentence-shaped line with its two verbs, is the page's idea: a tag list's real job is hygiene, and the page leads with it. A generic tags page would be a cloud of chips with counts.
Deterministic scan: clean, 0 findings, exit 0. No overlay.

## Overall Impression
A confident page that knows what tags are for. It is built for a vocabulary of a dozen tags; it has no answer for a hundred.

## What's Working
- The group line reads as a sentence: "Urgent and urgent  1 and 1 tasks   Merge into Urgent  Keep apart".
- "N open ->" is the same link as Projects and is what the Tasks list shows (FR-01.26), so the number never disagrees with the list.
- The tag glyph at 1.4 stroke instead of a pill keeps the page typographic.

## Priority Issues
- [P2] There is no way to find a tag. Why: tags are made by typing them onto tasks and by bots, so the vocabulary grows without the user looking at it, and this is the only place to rename, merge or delete; at 60 tags the page is a long ruled list with no search and alphabetical order only. Fix: a text filter in the control position above the list. Suggested command: /impeccable shape. Product decision: no.
- [P3] "Look alike 1" counts groups while the sentence says "2 look alike" (tags) and DESIGN.md says the heading counts tags. Why: two units on one screen. Fix: make code and doc agree, preferably tags. Suggested command: /impeccable polish. Product decision: no.
- [P3] "No open tasks" does not tell an unused tag from a tag carried only by done tasks, which is what a user needs to know before deleting. Fix: "Not on any task" when it is carried by nothing. Suggested command: /impeccable clarify. Product decision: no.
- [P3] "created by you" is printed on every line when every tag is the owner's. Fix: show the line only for a tag a bot user made (the bot attribution is what the line is for). Suggested command: /impeccable distill. Product decision: no.
- [P3] Known and still true: "1 and 1 tasks" in the Look alike row (should read "1 task each").

## Persona Red Flags
**Alex (Power User)**: No search and no keyboard route to merge; Down/Up walks the tags.
**Jordan (First-Timer)**: "Look alike" is clear; "Keep apart" does not say it hides the suggestion until a name changes.
**Casey (Mobile)**: Merge into and Keep apart sit right-aligned on a second row, 14px apart; each has a 44px target in source but the pair is close.
**Riley (Stress Tester)**: Case-only twins (urgent, Urgent) are the exact fixture; a name with trailing spaces renders with whitespace-pre, so it can look identical to its twin.

## Minor Observations
- The hierarchy between "Look alike" and "Tags" headings is the same weight, so a suggestion and the inventory read as peers; fine when there is one group, heavy when there are several.
- On phone the look-alike actions are 13.5px text in ink and ink-3; the ink-3 "Keep apart" is the quietest control on the screen and also an irreversible-feeling one.
- No Tags tab in the phone bar (reached from the account menu).

## Questions to Consider
- Should an unused tag be offered for deletion the way a look-alike is offered for merging?
- Does a bot-created tag deserve a visible difference from the user's own, since the user did not choose its spelling?

Questions skipped: closing critique batch, findings are filed as issues by the coordinator
