# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

Taskly is **single-context**: one domain, one glossary at the root. The Bun workspaces (`frontend`, `packages/*`) are a packaging boundary, not a bounded-context boundary — don't treat them as separate contexts.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root: the domain glossary.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in.
- **`docs/features.md`**: the numbered requirements (`FR-XX.Y`) the glossary and ADRs were derived from. Cite requirements by their `FR-XX.Y` id rather than restating them.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

```
/
├── CONTEXT.md
├── docs/
│   ├── features.md
│   └── adr/
│       ├── 0001-recurring-tasks-new-instance.md
│       └── 0002-attachment-storage-backend.md
├── backend/
├── frontend/
└── packages/
```

Next ADR number: **0003**.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids — in particular, "archived" and "deleted" are distinct, non-overlapping states, and "audit log" is not a synonym for the per-user activity log.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0001 (recurring tasks spawn a new task per occurrence), but worth reopening because…_
