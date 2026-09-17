# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary users are:

- **The owner.** Taskly is first of all the owner's own task tracker, and product decisions are made for their use.
- **Technical people who work with AI agents.** Developers and power users who keep their personal tasks in Taskly and give part of that work to their own agents and integrations. They come back to see what those agents did.

Several human accounts can exist on one installation. Each account manages only its own tasks, and there is no collaboration between accounts. One superuser administers the installation. Bot users are actors, not audiences: they never see the web UI.

Typical moments of use:

- writing a task down before it is forgotten;
- triaging what is due or overdue;
- checking what a bot user changed while the human was away;
- setting up a bot user and its scope.

## Product Purpose

Taskly is a personal task tracker. It holds tasks, subtasks, projects, tags, comments and attachments. AI agents and other integrations can work on those same tasks as bot users through a REST API, within limits the human sets.

Success means:

- capturing a task costs almost nothing;
- the list stays trustworthy;
- the human can always tell what any bot user did and undo it.

Requirements are numbered in `docs/features.md`, and the domain glossary is `CONTEXT.md`.

## Positioning

Taskly is self-hosted, and the data stays on the owner's own server. That is the position a hosted tracker such as Todoist, Things or Linear cannot take. Bot-user access to tasks is secondary to it, and it inherits the same premise: an agent reaches the owner's data on the owner's installation, only within the scope the owner granted.

## Operating Context

- **Installation.** One installation per owner, deployed with Docker Compose on their own server (`deployment-docker-compose.md`) or to FastAPI Cloud (`deployment.md`). FastAPI serves the built frontend, and email goes out through React Email templates (`packages/react-email`).
- **Clients.** A web app used on desktop and on phones.
- **Bot access.** Bot users authenticate with a bearer token, one per bot user, shown once when issued. They reach only the projects named in their scope.
- **Admin work in the web UI only.** Bot users are created, scoped and given tokens in the web UI; the API offers none of this.
- **Traceability.** Every change is recorded in the user's own activity log and names the actor who made it, whether the human or a specific bot user. Deleted tasks and projects can be restored from that log.

## Capabilities and Constraints

- **Tasks.** A task has a title, description, due date (date only), priority P1–P4, an optional assignee (the user or one of their bot users), tags, and a recurrence rule (daily, weekly, monthly or every N days). A task is To do, In progress, Waiting or Done; Waiting stays open, and moving a recurring task to Done spawns its next occurrence as a new task.
- **Subtasks** nest to any depth and are full tasks. A subtask belongs to the project of its root task.
- **Projects** are flat. Every user has an Inbox that cannot be renamed or deleted. Projects can be archived, which is distinct from deleted: an archived project is read-only for the human and invisible to bots.
- **Deletion** of tasks and projects is soft and restorable from the activity log. Tag deletes and merges, comment and attachment deletion, and bot-user deletion cannot be undone.
- **Tags** belong to the user, not to a project. Only the human renames, merges or deletes them.
- **Bot users** are deliberately weak. They have no login, no password and no email. Their scope is an explicit list of projects plus permissions (task create/read/update/delete, comments, tag creation). They never reach archived projects, never read the activity log, and cannot edit or delete comments. Their comments are append-only.
- **Out of scope:**
  - collaboration between humans;
  - text search;
  - nested projects;
  - giving a bot access to all projects at once.
- **Deferred:** webhooks (F-11).
- **Terminology** follows `CONTEXT.md`. Say "bot user", never "service account" or "API key". Say "activity log", never "audit log". "Archived" and "deleted" are different states.
- **Interface language:** English. All specs, docs, code comments and issues are written in English.

## Brand Commitments

- **Name.** The product is **Taskly**, and it has its own voice, not that of the FastAPI template it was bootstrapped from (#67). No "FastAPI Template" titles, no generic "Success!" or "Something went wrong!".
- **Voice.** Precise, calm and unobtrusive:
  - controls say what they do, and there is no generic "Save";
  - errors state what failed;
  - an absent value is said in words, never "N/A";
  - confirmations name what is lost and the way back when there is one.
- **Visual system.** The visual system is recorded in `frontend/DESIGN.md`, not here.

## Evidence on Hand

- `docs/features.md` holds the confirmed requirements. `docs/adr/` holds the decisions on recurrence, attachment storage and tags.
- `frontend/public/assets/images/favicon.png` is the only brand asset in the repository.
- No customers, testimonials, usage figures or pricing exist. Future work must not invent them.

## Product Principles

1. **The owner's data stays the owner's.** Nothing leaves their installation, and nothing is exposed beyond what they granted.
2. **Nothing is lost quietly.** Destruction is proportional to its consequence: soft delete with restore where possible, and an explicit confirmation where not. A draft or a typed value is never discarded silently.
3. **Every change has a named author.** A bot user's action is always attributable and never passed off as its owner's.
4. **Bots are held to the narrowest reach.** Every bot permission is explicit and per project. What a bot user can never do has no setting at all.
5. **Capture and triage are the core loop.** Writing a task down must be the cheapest act in the product, and one panel both reads and edits a record.

## Accessibility & Inclusion

WCAG 2.2 AA is required on desktop and mobile. That includes:

- 4.5:1 text contrast in both light and dark themes;
- targets of at least 24×24;
- full keyboard operation, including the global `c` capture shortcut;
- announcements for screen readers when a change has no visible receipt.
