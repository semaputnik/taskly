# Taskly — Feature Requirements

**Status:** Draft
**Last updated:** 2026-09-15

This document lists the features Taskly must provide. It records confirmed
requirements only. Anything not yet decided is listed under
[Open questions](#7-open-questions) and is not treated as a requirement.
Release planning (which features go into which version) will be done separately.

## 1. Overview

Taskly is a personal task tracker that also lets a user work with AI agents.

- Taskly is a multi-user application. Each user manages their own tasks.
- Human users do not collaborate with each other.
- A user connects AI agents and other external integrations through bot users.
  Bots work with the user's data through the REST API, within the permissions
  the user granted them.

## 2. Glossary

| Term | Definition |
|---|---|
| **User** | A person with an account in Taskly. Also called a *human user* to distinguish it from a bot user. |
| **Superuser** | The single administrative account. |
| **Bot user** | An account a user creates for their own integrations. It has far fewer permissions than a human user. |
| **Owner** | The user who created a bot user. |
| **Scope** | The set of permissions granted to a bot user: which projects it can see and what it can do. |
| **Token** | The credential a bot user uses to authenticate to the REST API. A bot user has one token. |
| **Task** | The main entity: a unit of work with a status — To do, In progress, Waiting or Done. A task that is not Done is *open*. |
| **Subtask** | A task that is a child of another task. A subtask is a full task. |
| **Project** | A container that groups tasks. Every task belongs to a project. Projects are flat: there is no nesting. |
| **Inbox** | The default project every user has. Tasks go there unless another project is chosen. Cannot be renamed or deleted. |
| **Archived project** | A project a user has hidden from daily use without deleting it. Read-only; hidden from default views; no bot access. Distinct from a *deleted* project — see [F-05](#f-05-projects). |
| **Tag** | A named label a user attaches to tasks. Belongs to the user and is shared across their projects. |
| **Comment** | A text note attached to a task. |
| **Attachment** | A file attached to a task. |
| **Assignee** | The actor responsible for a task: the user or one of their bot users. Optional. |
| **Activity log** | The record of changes made in Taskly. Also called the *event feed*; the two are the same thing. |

## 3. Roles

| Role | Description |
|---|---|
| **User** | Regular account. Manages their own tasks, projects and bot users. |
| **Bot user** | Created by a user for integrations. Acts only within its scope, through the REST API. |
| **Superuser** | Exactly one per installation. Does administrative work (see [F-09](#f-09-administration)). |

## 4. Features

### F-01. Tasks

- **FR-01.1** A user can create, view, edit and delete tasks.
- **FR-01.2** A task has the following fields:
  - title
  - description
  - due date (date only, no time of day)
  - priority
  - assignee
  - tags
- **FR-01.3** Priority takes one of four values: `P1`, `P2`, `P3`, `P4`.
  `P1` is the highest priority, `P4` the lowest. Priority is optional; a task
  with no priority set behaves as `P4`.
- **FR-01.4** A task has exactly one of four statuses: **To do**, **In
  progress**, **Waiting** and **Done** (`todo`, `in_progress`, `waiting`,
  `done` in the REST API). A task is **open** when its status is To do, In
  progress or Waiting, and **closed** when it is Done. Waiting means the task
  is open but its next move belongs to someone or something other than the
  owner. A new task is To do unless it is created with another status. The
  statuses are fixed; a user cannot define their own (ADR-0004).
- **FR-01.5** A user, or a bot user allowed to update the task, can move a task
  to any status. Closing a task is a single action from any open status (the
  checkbox), and undoing it returns the task to To do.
- **FR-01.6** A task has at most one assignee. A task can have no assignee.
- **FR-01.7** The assignee is either the user or one of the user's bot users.

#### Tags

- **FR-01.20** A tag is an entity of its own, with a name. A user creates a
  tag either on the Tags page or on the fly, by typing a name that is not a tag
  yet onto a task.
- **FR-01.21** Tags belong to the user, not to a project: a user's tags are
  shared across all of their projects.
- **FR-01.22** A tag's name is unique among the user's tags. Names are
  case-sensitive: `urgent` and `Urgent` are two tags. Creating a tag, or
  renaming one, to a name that is already taken is refused.
- **FR-01.23** A tag stays until the user deletes it, whether or not any task
  carries it.
- **FR-01.24** A user can rename a tag. Every task that carries it shows the new
  name. Activity log entries written before the rename keep the name the tag
  had then.
- **FR-01.25** A user can delete a tag. It is taken off every task that carries
  it. Deleting a tag is permanent: it cannot be restored from the activity log.
- **FR-01.26** The Tags page lists the user's tags with the number of tasks
  each is on, and lets the user create, rename and delete them. Before a tag is
  deleted, the page asks for confirmation and says how many tasks will lose it.
  The number is the live tasks, as the task list filtered by the tag shows them;
  tasks archived with their project are counted beside it, and deleting the tag
  reaches them too.
- **FR-01.27** A user can merge tags: every task carrying the merged tags
  carries the surviving one instead, once, and the merged tags are deleted,
  archived tasks included. The user chooses which name survives and confirms
  after being told how many tasks change — the tasks the user can see, deleted
  ones left out as a tag's own count leaves them out, though their tag moves
  too. A merge is one activity log entry and cannot be restored. Renaming into
  a taken name stays refused.
- **FR-01.28** The Tags page offers groups of tags whose names differ only in
  letter case, separators, whitespace or a trailing plural "s" (not for a name
  of three letters or fewer, nor one ending in "ss"), for merging. A group
  is never merged without confirmation, and a group the user keeps apart is not
  offered again until one of its tags is renamed or another joins it. Typing a
  new name onto a task names the existing tags it would duplicate and offers
  them instead. A tag a bot user created names that bot user, to the user.

#### Deletion

- **FR-01.8** Deleting a task does not remove it from the system. The task is
  marked as deleted and no longer appears in the task list.
- **FR-01.9** The deletion is recorded in the activity log.
- **FR-01.10** A user can restore a deleted task from the activity log.
  Restoring a task also restores its subtasks, except any subtask that was
  already deleted independently before the parent was deleted — that subtask
  stays deleted.
- **FR-01.11** Deleting a task also deletes all its subtasks. Before deleting a
  task that has subtasks, Taskly shows the user a warning.
- **FR-01.12** The REST API rejects a request to delete a task that has
  subtasks with an error, unless the request explicitly confirms cascading
  deletion. This mirrors the behavior of closing a task (FR-02.6, FR-02.7).

#### Recurrence

- **FR-01.13** A task can be marked as recurring, with a fixed-interval rule:
  daily, weekly, monthly, or every N days.
- **FR-01.14** Moving a recurring task to Done creates its next occurrence as
  a new task, which starts as To do. The new task copies the done one's fields
  (title, description, priority, assignee, tags) and its subtask tree, with
  every subtask To do. Comments and attachments are not copied — they belong
  to the occurrence that was done. Moving an occurrence between open statuses
  never creates an occurrence.
- **FR-01.15** The next occurrence's due date is the done occurrence's due
  date plus the recurrence interval — a fixed schedule, independent of when
  the occurrence was actually done.
- **FR-01.16** Only one open occurrence of a recurring task exists at a time.
  The next occurrence is not created until the current one is Done, even if
  its due date has already passed. Only the latest occurrence can be moved out
  of Done, and the recurrence rule can change only while the task is open.
- **FR-01.17** A user can change the due date of the open occurrence of a
  recurring task, like on any task. Taskly asks whether the change applies
  only to this occurrence or to this and all following occurrences.
- **FR-01.18** "Only this occurrence": changes this task's due date. The next
  occurrence's due date is still computed from the original, un-edited
  schedule (FR-01.15) — the edit does not shift the series.
- **FR-01.19** "This and all following occurrences": changes this task's due
  date and shifts the series — the next occurrence's due date is computed
  from the new due date plus the recurrence interval (FR-01.15), instead of
  from the original.

### F-02. Subtasks

- **FR-02.1** A task can have subtasks.
- **FR-02.2** A subtask is a full task: it has all task fields and supports
  everything a task supports (comments, attachments, statuses, etc.).
- **FR-02.3** Subtasks can be nested to any depth.
- **FR-02.4** A subtask always belongs to the same project as its parent.
  Moving a task to another project moves all its subtasks with it.
- **FR-02.5** When a user moves a task that has open subtasks to Done, Taskly
  asks whether to move the subtasks to Done as well or leave them as they are.
- **FR-02.6** The REST API rejects a request to move a task that has open
  subtasks to Done with an error, and the task keeps its status. This applies
  to every API client, human or bot.
- **FR-02.7** The REST API lets a client move such a task to Done anyway by
  stating explicitly in the request whether the subtasks stay as they are or
  are moved to Done too. Moving a task between open statuses never touches its
  subtasks.
- **FR-02.8** Closing all subtasks does not close the parent task
  automatically.
- **FR-02.9** Every task, wherever the REST API returns it, reports how many
  subtasks it has one level down and how many of those are Done
  (`subtask_count`, `subtasks_done`). Deleted subtasks are not counted.

### F-03. Comments

- **FR-03.1** A task can have comments.
- **FR-03.2** A human user can edit or delete their own comments. This does
  not apply to bot users, whose comments are append-only (FR-08.10).
- **FR-03.3** A comment cannot have its own attachments; attachments stay at
  the task level (see [F-04](#f-04-attachments)).

### F-04. Attachments

- **FR-04.1** A task can have file attachments.
- **FR-04.2** There is a limit on attachment file size. There is no limit on
  file type or on the number of attachments per task. (The exact size limit
  is a configuration detail, not fixed here.)
- **FR-04.3** Attachments are stored internally by Taskly by default. The
  storage is a swappable backend (see
  [ADR-0002](./adr/0002-attachment-storage-backend.md)) so that an external
  store, such as a per-user Paperless-ngx instance (see
  [Future ideas](#5-future-ideas)), can be added later without changing how
  attachments work for users.

### F-05. Projects

- **FR-05.1** A user can create projects.
- **FR-05.2** Every task belongs to exactly one project.
- **FR-05.3** Every user has a default project called **Inbox**. It exists from
  the moment the account is created.
- **FR-05.4** A task created without a project goes to Inbox (as in Todoist).
- **FR-05.5** Projects are flat. A project cannot contain another project.
- **FR-05.6** The Inbox project cannot be renamed or deleted.
- **FR-05.7** A project has a name and an optional description.

#### Deletion

- **FR-05.8** Deleting a project marks it as deleted, the same way as a task
  (see [FR-01.8](#f-01-tasks)). It is not removed from the system.
- **FR-05.9** Deleting a project also deletes all its tasks. Restoring the
  project from the activity log restores its tasks with it.

#### Archiving

- **FR-05.10** A user can archive a project and unarchive it again. This is a
  direct, immediately-reversible action — it does not go through the activity
  log or the deletion/restore flow.
- **FR-05.11** Archiving a project archives all its tasks with it. Unarchiving
  reverses this for all of them.
- **FR-05.12** An archived project and its tasks are read-only for the human
  user: nothing in it can be created, edited, or deleted while archived.
- **FR-05.13** A bot user has no access — read or write — to an archived
  project or its tasks, regardless of what its scope otherwise grants
  (see [FR-08.6](#f-08-bot-users)).
- **FR-05.14** An archived project and its tasks are hidden from the default
  task list and from filters (see [F-06](#f-06-task-list-and-filtering))
  unless the user explicitly asks to see the archive.

### F-06. Task list and filtering

- **FR-06.1** Tasks are displayed as a list.
- **FR-06.2** The task list can be filtered by:
  - project
  - assignee
  - tag
  - priority
  - status: Open, or any one or more of the four statuses
  - due date
- **FR-06.3** Filters can be combined; a task must match all active filters.
- **FR-06.4** The task list can be sorted, at minimum by due date and by
  priority.
- **FR-06.5** The task list can be shown as a table or as compact rows. A
  compact row shows the title, and beneath it the task's subtask progress, due
  date, recurrence and tags. The choice is part of the list's URL and does not
  change its filters, order or page.
- **FR-06.6** Priorities are told apart by colour as well as by name: P1 red,
  P2 amber/yellow, P3 blue, and P4 (or no priority) uncoloured. A compact row
  shows its task's priority as the colour of its completion checkbox.
- **FR-06.7** The dashboard shows the user's In progress tasks in a panel of
  their own, highest priority first, alongside what is overdue and due today.

### F-07. REST API

- **FR-07.1** Taskly exposes a REST API.
- **FR-07.2** Everything a bot user needs to do its own work is available
  through the REST API: tasks, comments and attachments within its scope (see
  [F-08](#f-08-bot-users)), and its owner's tags, which belong to the user
  rather than to a project and so are not narrowed by the scope at all
  (FR-08.9, ADR-0003).
- **FR-07.3** Creating, scoping, and issuing tokens for bot users is a human
  action available only in the web UI, not through the REST API. A bot cannot
  create or configure itself or another bot.

### F-08. Bot users

#### Creation and ownership

- **FR-08.1** A user can create bot users for their integrations.
- **FR-08.2** A bot user belongs to the user who created it.
- **FR-08.3** There is no limit on the number of bot users a user can create.
- **FR-08.4** A bot user has far fewer permissions than a human user. It can only
  do what its scope allows.
- **FR-08.5** A bot user accesses Taskly through the REST API using its token.

#### Scope: project access

- **FR-08.6** The scope lists the projects the bot user can access. Projects are
  always listed explicitly; there is no "all projects" option.
- **FR-08.7** A bot user can only access tasks in the projects listed in its
  scope. This applies to every action on tasks: create, read, update, delete.
- **FR-08.8** A bot user cannot move a task to a project outside its scope.

#### Scope: permissions

- **FR-08.9** Permissions are granted per entity type:

  | Entity | Create | Read | Update | Delete |
  |---|---|---|---|---|
  | Task | configurable | configurable | configurable | configurable |
  | Tag | configurable | always | never | never |
  | Project | never | only projects in scope | never | never |

  Tags (see ADR-0003):
  - Creating tags is a permission of its own. It covers both creating a tag
    directly and typing a name that is not a tag yet onto a task.
  - A bot user reads all of its owner's tags, with the number of tasks each is
    on, whatever its scope. Tags belong to the user rather than to a project,
    so the scope has nothing to narrow them by.
  - Applying and removing tags on a task is part of creating or updating the
    task: it takes the create or update permission on tasks, plus the
    permission to create tags for any name that is not a tag yet.
  - Renaming and deleting tags is for the user only. Both change tasks in
    every project, including those outside the bot user's scope.

- **FR-08.10** Comments:
  - Adding comments to tasks is a separate permission.
  - A bot user can read a task's comments if it can read the task.
  - A bot user cannot edit or delete comments, including its own. Comments
    from bots are append-only, so their history stays transparent.
- **FR-08.11** Attachments:
  - A bot user can download a task's attachments if it can read the task.
  - A bot user can add and delete a task's attachments if it can update the task.

#### Token

- **FR-08.12** A bot user has exactly one token.
- **FR-08.13** The token is shown once, when it is issued. It cannot be viewed
  again afterwards.
- **FR-08.14** The user can set an expiration date for the token.
- **FR-08.15** The user can revoke the token.
- **FR-08.16** After a token is revoked, the user can issue a new token for the
  same bot user.
- **FR-08.17** The user can see when the token was last used.

#### Deletion

- **FR-08.18** The user can delete a bot user.
- **FR-08.19** A deleted bot user is not removed from the system. It is marked
  as deleted, so the history of its actions is preserved.
- **FR-08.20** A deleted bot user cannot access the REST API.
- **FR-08.21** Tasks assigned to a bot user stay assigned to it after the bot
  user is deleted.

### F-09. Administration

- **FR-09.1** The system has exactly one superuser.
- **FR-09.2** The superuser can view the list of registered users.
- **FR-09.3** The superuser has no other administrative functions for now.
- **FR-09.4** A person can register their own account; account creation does
  not require an invitation or the superuser's action.
- **FR-09.5** The superuser also uses Taskly as a regular user, with their own
  tasks and projects.

### F-10. Activity log (event feed)

- **FR-10.1** Taskly records changes in an activity log. The activity log is
  also the event feed; there is no separate feed.
- **FR-10.2** Each log entry identifies who made the change: the user or a
  specific bot user.
- **FR-10.3** The log records every change, including:
  - Tasks:
    - a task is created
    - a task is changed
    - a task is completed (moved to Done)
    - a task is reopened (moved out of Done)
    - a task is moved between open statuses, with the status before and after
    - a task is deleted
    - a task is moved to a project
    - an assignee is set on a task
    - an assignee is removed from a task
  - Comments:
    - a comment is added to a task
    - a comment is edited
  - Attachments:
    - an attachment is added to a task
    - an attachment is deleted
  - Tags:
    - a tag is created, on the Tags page or by being typed onto a task
    - a tag is renamed
    - a tag is deleted
  - Projects:
    - a project is created
    - a project is changed
    - a project is deleted
- **FR-10.4** A deleted task or project can be restored from the log
  (see FR-01.10, FR-05.8).
- **FR-10.5** Log entries are kept indefinitely.
- **FR-10.6** Bot users cannot read the activity log.
- **FR-10.7** A user sees only their own activity log. The superuser is not an
  exception: they see only their own log, not other users'.

### F-11. Webhooks — *Deferred*

Taskly will send events to external integrations through webhooks. This
feature is postponed to a later iteration. Details to settle when we come back
to it:

- Who configures a webhook: the user, or per bot user?
- Which events can trigger a webhook?
- Are delivery retries and payload signing needed?

## 5. Future ideas

Not requirements yet. Recorded so they are not lost.

- **Restore a deleted bot user.** Bring a deleted bot user back and issue it a
  new token.
- **Paperless-ngx as an attachment storage backend.** Let a user optionally
  connect their own Paperless-ngx instance so their task attachments are
  stored and processed (OCR, classification) there instead of internally,
  with the Paperless document linked back to its Taskly task. Internal
  storage (FR-04.3) stays the default for users who don't connect one.

## 6. Out of scope

- Collaboration between human users (shared projects, assigning tasks to other people, etc.).
- Superuser functions other than viewing the list of users.
- Restricting bot users by tags. Bot access is limited by projects only.
- Bot users creating, updating or deleting projects.
- Giving a bot user access to all projects at once.
- More than one token per bot user.
- Bot users reading the activity log.
- Bot users editing or deleting comments.
- Bot users renaming or deleting tags.
- Nested projects (projects are flat — see FR-05.5).
- Text search over tasks.

## 7. Open questions

Q-01 through Q-16, raised while drafting this document and while splitting it
into issues, have been resolved into the requirements above. There are no open
questions at the moment.
