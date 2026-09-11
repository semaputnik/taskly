# Taskly

A personal task tracker where a user's tasks can also be operated on by AI agents and other integrations acting as bot users through a REST API. See `CONTEXT.md` for the domain glossary and `docs/features.md` for the numbered requirements.

## Agent skills

### Issue tracker

Issues live as GitHub issues in `semaputnik/taskly`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label named after its role (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
