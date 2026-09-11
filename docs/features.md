# Taskly — Feature Requirements

**Status:** Draft
**Last updated:** 2026-09-10

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
| **Task** | The main entity: a unit of work that is either completed or not completed. |
| **Subtask** | A task that is a child of another task. A subtask is a full task. |
| **Project** | A container that groups tasks. Every task belongs to a project. |
| **Inbox** | The default project every user has. Tasks go there unless another project is chosen. |
| **Tag** | A label attached to a task. |
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
  - due date
  - priority
  - assignee
  - tags
- **FR-01.3** Priority takes one of four values: `P1`, `P2`, `P3`, `P4`.
- **FR-01.4** A task has exactly two states: **completed** and **not completed**.
  There are no other workflow statuses (Todoist-style).
- **FR-01.5** A user can mark a task as completed and return it to not completed.
- **FR-01.6** A task has at most one assignee. A task can have no assignee.
- **FR-01.7** The assignee is either the user or one of the user's bot users.

#### Deletion

- **FR-01.8** Deleting a task does not remove it from the system. The task is
  marked as deleted and no longer appears in the task list.
- **FR-01.9** The deletion is recorded in the activity log.
- **FR-01.10** A user can restore a deleted task from the activity log.
- **FR-01.11** Deleting a task also deletes all its subtasks. Before deleting a
  task that has subtasks, Taskly shows the user a warning.

### F-02. Subtasks

- **FR-02.1** A task can have subtasks.
- **FR-02.2** A subtask is a full task: it has all task fields and supports
  everything a task supports (comments, attachments, completion, etc.).
- **FR-02.3** Subtasks can be nested to any depth.
- **FR-02.4** A subtask always belongs to the same project as its parent.
  Moving a task to another project moves all its subtasks with it.
- **FR-02.5** When a user completes a task that has uncompleted subtasks, Taskly
  asks whether to complete the subtasks as well or leave them uncompleted.
- **FR-02.6** The REST API rejects a request to complete a task that has
  uncompleted subtasks with an error, and the task stays uncompleted. This
  applies to every API client, human or bot.
- **FR-02.7** The REST API lets a client complete such a task anyway by stating
  explicitly in the request that the subtasks stay uncompleted.
- **FR-02.8** Completing all subtasks does not complete the parent task
  automatically.

### F-03. Comments

- **FR-03.1** A task can have comments.

### F-04. Attachments

- **FR-04.1** A task can have file attachments.

### F-05. Projects

- **FR-05.1** A user can create projects.
- **FR-05.2** Every task belongs to exactly one project.
- **FR-05.3** Every user has a default project called **Inbox**. It exists from
  the moment the account is created.
- **FR-05.4** A task created without a project goes to Inbox (as in Todoist).

### F-06. Task list and filtering

- **FR-06.1** Tasks are displayed as a list.
- **FR-06.2** The task list can be filtered by:
  - project
  - assignee
  - tag
  - priority

### F-07. REST API

- **FR-07.1** Taskly exposes a REST API.

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
  | Tag | configurable | configurable | configurable | configurable |
  | Project | never | only projects in scope | never | never |

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

### F-10. Activity log (event feed)

- **FR-10.1** Taskly records changes in an activity log. The activity log is
  also the event feed; there is no separate feed.
- **FR-10.2** Each log entry identifies who made the change: the user or a
  specific bot user.
- **FR-10.3** The log records every change, including:
  - Tasks:
    - a task is created
    - a task is changed
    - a task is completed
    - a task is returned to not completed
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
  - Projects:
    - a project is created
    - a project is changed
    - a project is deleted
- **FR-10.4** A deleted task can be restored from the log (see FR-01.10).
- **FR-10.5** Log entries are kept indefinitely.
- **FR-10.6** Bot users cannot read the activity log.

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

## 6. Out of scope

- Collaboration between human users (shared projects, assigning tasks to other people, etc.).
- Task workflow statuses beyond completed / not completed.
- Superuser functions other than viewing the list of users.
- Restricting bot users by tags. Bot access is limited by projects only.
- Bot users creating, updating or deleting projects.
- Giving a bot user access to all projects at once.
- More than one token per bot user.
- Bot users reading the activity log.
- Bot users editing or deleting comments.

## 7. Open questions

| ID | Area | Question |
|---|---|---|
| Q-01 | Subtasks | When a deleted task is restored, are its subtasks restored with it? |
| Q-02 | Subtasks | FR-01.11 shows a warning in the UI. What happens when a task with subtasks is deleted through the REST API, for example by a bot? Proposal: the same approach as for completion (FR-02.6, FR-02.7) — the API returns an error unless the request explicitly confirms that subtasks are deleted too. |
| Q-03 | Activity log | Can the superuser see users' activity logs, or does each user see only their own? |
| Q-04 | Deletion | What happens to a project's tasks when the project is deleted? Is a project deleted the same way as a task (marked as deleted, restorable)? |
| Q-05 | Projects | Can Inbox be renamed or deleted? |
| Q-06 | Projects | Can projects be nested? Which fields does a project have besides a name? |
| Q-07 | Due date | Date only, or date and time? Are recurring tasks needed? |
| Q-08 | Priority | Is `P1` the highest priority? Is priority required, or does it have a default? |
| Q-09 | Tags | Are tags free text created on the fly, or managed as a separate list? Are they per user? |
| Q-10 | Comments | Can users edit or delete comments? Can comments have attachments? |
| Q-11 | Attachments | Are there limits on file size, file type, or number of files? |
| Q-12 | Filtering | Can filters be combined? Is filtering by completion state or due date needed? Sorting? Text search? |
| Q-13 | Accounts | Can people sign up on their own, or does the superuser create accounts? |
| Q-14 | Superuser | Does the superuser also use Taskly as a regular user, with their own tasks and projects? |
| Q-15 | UI vs API | Must every feature be available in both the web UI and the REST API? For example, is bot user management UI-only? |
