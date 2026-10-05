# Running issues through subagents

How the main session runs a batch of issues through implementer subagents, and the
brief each subagent gets. Written from the first batch (#130, #134–#140, iteration
`iteration-2026-10-05`); every rule below is there because its absence cost time.

## The coordinator

The main session coordinates and does not implement. It launches subagents, reads
their reports, merges what is ready, and launches what that unblocks. If launching a
subagent for an issue is refused (the auto-mode classifier refused one for sign-in
work), ask the user how to proceed rather than implementing it in the main session:
while the coordinator is in code, nobody notices that the next issue is unblocked.

## Before the batch

Check these once, before the first launch, and put the answers in every brief:

1. **Iteration branch.** Cut one shared branch from master (`iteration-YYYY-MM-DD`)
   and push it. Every subagent branches from it and opens its PR against it; the user
   reviews the iteration branch as a whole. Never let subagents merge into master:
   its ruleset requires an approval from someone other than the last pusher, so a
   subagent cannot merge there.
2. **Master is green.** Run the lint and the CI checks on the iteration branch's base.
   A broken base (in the first batch, biome errors in a committed mock) is found by
   every subagent separately and fixed in every PR, with conflicts to match. Fix it
   once, on the iteration branch, before launching.
3. **Migration head.** Note `cd backend && uv run alembic heads`. Two issues that
   both add a migration will both chain after it; say in both briefs which one goes
   first, or have the second re-chain after the first merges.
4. **Known flaky tests.** List the Playwright tests known to flake (semaputnik/taskly#150
   tracks the ones from the first batch). CI runs with `--fail-on-flaky-tests`, so a
   flake fails the job even when the retry passes.
5. **Ports and databases.** Assign each subagent its own test database
   (`TEST_DB_NAME=app_test_<issue>`) and its own ports for any server it starts.
   Taken already: 8000 and 5173 (dev stack, shared with the taler project), 8010 and
   5174 (demo stack), 8765 (career-hub).
6. **Neighbours.** For issues that run in parallel, name the other issue in each brief
   and the files both will touch, and ask each to keep its edits to those files small
   and local.
7. **Open decisions.** Read each issue against `docs/features.md` and `CONTEXT.md`.
   Where they disagree (in the first batch, "five open statuses" against FR-06.11's
   four), or where the issue leaves a product choice open (where to keep the last
   visit, whether an inline restore asks first), settle it with the user before
   launching. Otherwise the subagent settles it, and the user only finds out from
   the report.

## The brief

Every brief carries these sections. Fill in the angle-bracket parts.

```text
You are implementing GitHub issue #<n> in semaputnik/taskly ("<title>"), up to a PR
merged into the iteration branch.

## Branch strategy
Base branch: <iteration branch>. Branch from it as <slug>-<n>; open the PR against it,
never against master. When behind, `git merge origin/<iteration branch>` (no rebase).

## Process
Follow the `implement` skill: /Users/semaputnikov/.claude/plugins/cache/
claude-plugins-official/mattpocock-skills/<version>/skills/engineering/implement/
SKILL.md (TDD where possible, typecheck often, full suite once, /code-review with
fixed point origin/<iteration branch>, commit).

## Read first
The issue and its linked issues, CLAUDE.md, CONTEXT.md, docs/features.md (<FRs>),
docs/adr/, docs/agents/*.md, <design brief and mock if UI>.

## Context
- Already in the base branch: <what earlier issues built, with file paths>.
- Running in parallel: <issue, what it touches, shared files>.
- Decisions already made with the user: <list, or "none">.
- Out of scope, owned by other issues: <#n: what>.

## Rules
- pytest only via `cd backend && TEST_DB_NAME=app_test_<n> bash scripts/test.sh`;
  never against the `app` database.
- No local Playwright against :8000/:5173. Servers for visual checks only on
  <assigned ports>; stop them by PID, never pkill.
- Migrations chain after <head>; drop native enums explicitly in downgrade().
- Before each commit, run `uv run prek run --from-ref origin/<iteration branch>
  --to-ref HEAD --show-diff-on-failure` and commit what it rewrites.
- Known flakes: <list>. If only these fail and pass on retry, rerun the failed job
  (`gh run rerun <id> --failed`); do not change unrelated code.
- English everywhere; commits end with the Co-Authored-By line.

## Finish
Push; PR against <iteration branch> with "Part of #<n>" (not "Closes": the issue
closes when the iteration reaches master); wait for CI; fix and repeat until green;
merge with `gh pr merge --merge --delete-branch`; never `--admin`.

## Report
1. PR, merge commit.
2. What was built, briefly.
3. Decisions for the user: every product choice made without them, one line each.
4. Deviations from the issue, and why.
5. Left open, and why.
6. CI iterations.
```

## Writing issues for subagents

An issue is ready for an agent when a subagent can finish it without making a product
decision. Before labelling it `ready-for-agent`:

- **Out of scope, owned by #n.** Say which neighbouring issue owns what is close by.
  In the first batch #134 built part of #136's task line because neither issue drew
  the line between them.
- **Acceptance criteria within reach.** Every criterion must be checkable and
  reachable by the subagent alone. "The critique scores 32/40" was not: closing the
  gap took product decisions only the user could make.
- **Infrastructure.** Say what the work needs from CI or the deployment that the
  issue does not build. Passkey sign-in needed the CI browser to reach the app on a
  secure origin, which nobody had planned.
- **Conventions.** Point at CONTEXT.md for every user-facing term the issue uses
  informally ("agents" is "bot users").
