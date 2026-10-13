# Taskly — Feature Requirements

**Status:** Draft
**Last updated:** 2026-10-06

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
| **Passkey** | The only credential a human user signs in with. A user holds one or more. There are no passwords. |
| **Recovery code** | A one-time code the superuser issues to a user who has lost every passkey, spent by creating a new one. |
| **Task** | The main entity: a unit of work with a status — Backlog, To do, In progress, Waiting, Review or Done. A task that is not Done is *open*. |
| **Subtask** | A task that is a child of another task. A subtask is a full task. |
| **Project** | A container that groups tasks. Every task belongs to a project. Projects are flat: there is no nesting. |
| **Inbox** | The default project every user has. Tasks go there unless another project is chosen. Cannot be renamed or deleted. |
| **Archived project** | A project a user has hidden from daily use without deleting it. Read-only; hidden from default views; no bot access. Distinct from a *deleted* project — see [F-05](#f-05-projects). |
| **Tag** | A named label a user attaches to tasks. Belongs to the user and is shared across their projects. |
| **Comment** | A text note attached to a task. |
| **Attachment** | A file attached to a task. |
| **Assignee** | The actor responsible for a task: the user or one of their bot users. Optional. |
| **Reporter** | Who filed a task: the user or one of their bot users. Always set, and never changed. Called *Created by* in the interface. |
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
  - reporter (see FR-01.29)
  - tags
- **FR-01.3** Priority takes one of four values: `P1`, `P2`, `P3`, `P4`.
  `P1` is the highest priority, `P4` the lowest. Priority is optional; a task
  with no priority set behaves as `P4`.
- **FR-01.4** A task has exactly one of six statuses: **Backlog**, **To do**,
  **In progress**, **Waiting**, **Review** and **Done** (`backlog`, `todo`,
  `in_progress`, `waiting`, `review`, `done` in the REST API). A task is
  **open** when its status is anything but Done, and **closed** when it is
  Done. Backlog is work written down but not yet decided on; To do is that
  decision. Waiting means the task is open but its next move belongs to
  someone or something other than the owner. Review means the doer has
  finished and the next move is the owner's: check the work and close it, or
  send it back; it is how a bot user hands work over. A new task is Backlog
  unless it is created with another status, in the interface and the REST API
  alike. The statuses are fixed; a user cannot define their own (ADR-0004,
  ADR-0008). Wherever the interface lists them, the order is Backlog, To do,
  In progress, Review, Waiting, Done.
- **FR-01.4a** Status and assignee are independent. Moving a task to Review
  does not assign it to the owner, and a bot user may put a task it still
  holds into Review. A bot user that wants its finished work on the owner's
  dashboard assigns the task to the owner as well (FR-06.7); the REST API
  documentation records this as the convention.
- **FR-01.5** A user, or a bot user allowed to update the task, can move a task
  to any status. Closing a task is a single action from any open status (the
  checkbox), and undoing it returns the task to To do.
- **FR-01.6** A task has at most one assignee. A task can have no assignee.
- **FR-01.7** The assignee is either the user or one of the user's bot users.
- **FR-01.29** A task records its **reporter**: who filed it, either the user
  or one of the user's bot users. Every task has exactly one — unlike the
  assignee, it can be neither absent nor ambiguous. It is taken from whoever
  made the request that created the task and is never read from a request
  body, so no caller can file a task as somebody else, and a bot user's work
  is never recorded as its owner's. It cannot be changed after the task is
  created. The interface calls it **Created by**. A bot user deleted later is
  still named on what it filed (FR-08.19). Each occurrence of a recurring task
  carries the reporter of the occurrence before it (FR-01.14). Tasks that
  predate this requirement name the user.

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
  every subtask To do. The next occurrence starts in To do, not Backlog:
  the decision to do the work was made when the series was set up. Comments
  and attachments are not copied — they belong to the occurrence that was
  done. Moving an occurrence between open statuses never creates an
  occurrence.
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
- **FR-04.3** Attachments are kept in Taskly by default. The storage is a
  swappable backend (see [ADR-0002](./adr/0002-attachment-storage-backend.md));
  the one alternative is a user's own Paperless-ngx instance, below.

#### Paperless connection

- **FR-04.4** A user can connect their own Paperless-ngx instance in Settings
  by giving its address and an API token, and can test the connection there.
  The connection is optional and off until set; one per user. The token is
  kept so that it can be used but never shown again, only replaced. It is
  stored encrypted, under the installation's own `PAPERLESS_TOKEN_KEY`
  setting rather than a key derived from `SECRET_KEY`: changing that key
  makes stored tokens unreadable until each user enters theirs again. The
  address follows the same rule as a webhook URL on loopback and private
  ranges (FR-11.3), under the same installation setting.
- **FR-04.5** While a user has a Paperless connection, every PDF attached to
  their tasks — by them or by one of their bot users — is kept in Paperless.
  A file is a PDF by its content, not by its name or declared type. Every
  other file, and every file of a user without a connection, is kept in
  Taskly as before. The size limit (FR-04.2) applies before anything is sent.
- **FR-04.6** A PDF is accepted at once and is downloadable from that moment.
  Taskly keeps it until Paperless has consumed it, hands it over in the
  background, and then releases its own copy. Deliveries to Paperless are
  retried on the schedule of FR-11.10; after the last attempt the file stays
  kept in Taskly, the attachment shows why, and the owner can ask for it to
  be sent again.
- **FR-04.7** A PDF that Paperless already holds is not sent again: the
  attachment is linked to the existing document. One Paperless document may
  stand behind several attachments.
- **FR-04.8** Taskly never deletes a document from Paperless. Removing an
  attachment kept there drops the link only; deleting or restoring a task,
  and deleting the account, change nothing in Paperless. Disconnecting
  Paperless leaves attachments kept there where they are; they are out of
  reach until the connection is set again, and Settings says how many before
  the user confirms.
- **FR-04.9** A document sent to Paperless carries the file's original name
  as its title, a tag named `Taskly`, created on first use, and a note naming
  the task and linking to it in Taskly. A document linked under FR-04.7 gets
  the tag and a note too, one note per task it is attached to.
- **FR-04.10** Downloading an attachment kept in Paperless returns the
  original file, not Paperless's archived copy. If Paperless cannot be
  reached, the download fails with an error that says so.
- **FR-04.11** Every attachment says where it is kept, in the interface and
  the REST API; one kept in Paperless links to the document there.
- **FR-04.12** Connecting Paperless moves nothing: PDFs already kept in Taskly
  stay there.

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
  unless the user explicitly asks to see the archive. Archived projects are
  read on the Projects page, in a section of their own after the live ones,
  each with the way to its kept tasks; there is no separate archive screen.
- **FR-05.15** The Projects page lists every live project with its open-task
  count, and that count is the one-click way into the task list narrowed to
  the project. A project's own panel repeats the way in and shows its first
  open tasks with a capture line that files into the project.

### F-06. Task list and filtering

- **FR-06.1** Tasks are displayed as a list.
- **FR-06.2** The task list can be filtered by:
  - title text (contains, case-insensitive; FR-06.14)
  - project
  - assignee
  - reporter — the user, or one of their bot users (FR-01.29); there is no
    "nobody" to filter for, since every task has one
  - tag
  - priority
  - status: any one of the five open statuses
  - due date
- **FR-06.3** Filters can be combined; a task must match all active filters.
- **FR-06.4** The task list can be sorted by due date, by priority and by
  when each task was filed. Each order has a natural direction it runs in
  when none is named: soonest first, P1 first, and newest first. Choosing an
  order gives that direction; choosing it again reverses it. The order and
  any reversal live in the list's URL. The list's default order is newest
  filed first, with every subtask shown under its root task rather than at
  its own place in the order; the day page, not the list, answers what is
  most pressing.
- **FR-06.5** The task list has one view: task lines. A line shows the
  status mark, the title, and beneath it the task's subtask progress, due
  date, recurrence, tags and assignee (FR-06.13), with the project at the
  end. There is no table view and no selection of several lines: a change to
  many tasks at once is made by a bot user through the REST API's batch
  endpoint, which stays (FR-10.9). A subtask line is indented under its root
  task with a branch mark. A due day that has passed reads "Yesterday" and
  then "N days late" up to 14 days late; further back it reads the date
  in words ("due 3 Feb 2026"), still in the alert
  colour. The same words are used on the dashboard, the task list, the task
  column's subtask lines and everywhere else a task line is shown.
- **FR-06.6** Priorities are told apart by colour as well as by name: P1 red,
  P2 amber/yellow, P3 blue, and P4 (or no priority) uncoloured. A compact row
  shows its task's priority as the colour of its completion checkbox.
- **FR-06.7** The dashboard has a **My work** panel: the user's tasks whose
  assignee is the user themselves, in To do, In progress, Review or Waiting,
  grouped by status in the order In progress, Review, To do, Waiting, highest
  priority first within a group. Each group shows a few tasks and, past
  that, a link to the task list narrowed to that status and to the user as
  assignee. Tasks with no assignee, tasks on a bot user and tasks in Backlog
  are not in it: the dashboard is for the work in the user's hands, and the
  Tasks page is where everything else is managed. The interface labels the
  panel "In my hands": that is the label of the My work term. With no tasks
  it has no heading, only one line saying that nothing is in the user's
  hands.
- **FR-06.8** The task list shows open tasks only. A Done task is not listed
  and cannot be filtered for; completed work is read in the activity log
  (FR-10.8, ADR-0006). Open work is the list's baseline rather than a filter
  on it, so clearing the filters returns to it and no chip offers to remove
  it. This governs the task list alone: an archived project's tasks
  (FR-05.14), the subtasks shown inside a task, and the activity log all keep
  showing Done tasks.
- **FR-06.9** Completing a task from the task list takes its row out of the
  list, so the change is confirmed by a notice naming the task and offering to
  undo it, which returns the task to To do (FR-01.5). Changing a status
  anywhere the task stays on screen is not announced.
- **FR-06.10** A user whose tasks are all Done is told so, and pointed at the
  activity log — not told that they have no tasks.
- **FR-06.11** The dashboard's date bands — Overdue, Due today, This week —
  take every open status except Waiting, Backlog included: a due date counts
  whatever the task's status. Unlike My work, the bands are not narrowed to
  the user as assignee. Waiting tasks have no band of their own: a Waiting
  task on the user is read in My work, and one on a bot user or unassigned is
  read on the Tasks page.
- **FR-06.12** The dashboard opens with the date and one sentence of real
  counts: how many tasks need the user today — those in Overdue and Due
  today — and how many changes their bot users made since the user's last
  visit. A visit is one browser tab's session, counted from the last time the
  dashboard was read on that device; a first visit counts every change the
  bot users have made. When the bot users have changed nothing, the
  sentence says that instead of counting a zero. When nothing is overdue or
  due today, the dashboard says so in a sentence instead of drawing the
  bands. The dashboard's Changes preview lists the bot users' changes only;
  the user's own changes in the same window are folded into one line at its
  end that opens the activity log narrowed to the user.
- **FR-06.13** Wherever a task line is shown, its meta line names the
  assignee when there is one: "you", the bot user's name, or, for a task in
  Review that a bot user handed over, the bot user's name followed by an
  arrow and "you". An unassigned task names nobody.
- **FR-06.14** Typing in the capture line also searches: while the typed
  text is at least two characters long, the line offers the open tasks whose
  title contains it, case-insensitively, newest first, at most eight, each
  with its status mark and project, the matched text marked. Enter still
  creates a task from the typed text; the arrow keys and Enter, or a tap,
  open a match instead. The REST API's task list accepts the same title
  filter. Nothing is searched while the line is empty, and nothing beyond
  open tasks' titles is searched (descriptions and comments are not).
- **FR-06.15** The capture line is at the top of the page on a desktop,
  with its matches opening downward; there is no floating button and no
  "Add a task" entry in the desktop navigation, and the `c` key opens the
  full draft from any screen. On a phone the navigation is a bar at the
  bottom of the screen with Today, Tasks, a central add control, Bots and
  Activity; Projects, Tags, Archive, Settings, appearance and signing out
  are reached from the Menu control in the top bar, which says its name
  beside the avatar. The add control, on
  any screen, raises a capture sheet above the keyboard carrying the same
  line and its matches, a visible Create action once words are typed (Return
  creates too), and an "Add details…" line into the full draft,
  which takes the typed words as its title. A sheet closed with words in it
  leaves a dot on the add control, which then reads "Add a task, draft kept";
  the dot goes when the task is created or the words are cleared; the day page and the task list
  carry no capture line of their own on a phone.

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
- **FR-07.4** `GET /caller` is the one thing a bot user may read about
  itself, read-only and open to a human session too: who is calling, the
  owner id whose data the call reaches, exactly the permissions its scope
  grants (every one `true` for a human), the projects of its scope with their
  open-task counts (`null` for a human), and the server's current date. An
  archived project never appears there (FR-05.13), and a scope change is
  read on the bot's next call, with no new token needed.

#### MCP

- **FR-07.5** Taskly also exposes an MCP server, at `/mcp`, mounted in this
  same application rather than run as a second service (ADR-0012). It speaks
  only tools — no resources, no prompts, no sampling.
- **FR-07.6** A bot user's token authorises an MCP connection exactly as it
  authorises a REST request: resolved through the same code that builds a
  caller for the REST API, under the same scope and grants, with every
  tool's writes attributed to the bot user in the activity log (FR-10.2). A
  human session reaching `/mcp` is refused for what it is (`bot_only`), not
  for a permission a scope could have granted; an unknown, revoked, expired
  or deleted bot user's token is refused exactly as it is everywhere else
  (FR-08.14, FR-08.15, FR-08.20).
- **FR-07.7** Nothing about the caller is cached between calls: a scope
  edited between two calls is read again before the second, the same
  promise `GET /caller` makes (FR-07.4).
- **FR-07.8** A protocol session is bound to the token that opened it. The
  same session id presented with a different token is refused rather than
  served, so one agent's session cannot be continued as another's; one
  mounted server still serves any number of agents at once, because the
  caller comes from each call's own token rather than from anything the
  server was configured with.
- **FR-07.9** `whoami` is the first tool: read-only, and answering exactly
  what `GET /caller` answers (FR-07.4) — the actor, the owner, the scope's
  projects (the Inbox marked) with their open-task counts, exactly its
  grants, and the server's current date. The nine tools for working tasks
  themselves (`search_tasks`, `get_task`, `list_tags`, `create_task`,
  `update_task`, `complete_task`, `comment_task`, `delete_task`, and
  `whoami`) are spec #247's, and every one of them is built as of this
  entry.
- **FR-07.10** Every tool reads its arguments, reports its results and
  raises its refusals the same way:
  - **Ids.** A task is named by its full id or by the short prefix a
    compact line's own `id` prints (the first 8 hex characters of the full
    id, dashes dropped). An ambiguous prefix is refused with the candidates
    it matches, never resolved by guessing.
  - **Names.** A project or a tag is accepted by name, case-insensitively,
    as well as by id. Project names are not unique, so an ambiguous project
    name is refused with the matching ids; a tag name ambiguous only by
    letter case is refused the same way, since a tag's own name is
    otherwise unique to its owner (ADR-0003).
  - **Dates.** A date argument takes an ISO date, `today`, `tomorrow`, or a
    count of days ahead prefixed with `+` and suffixed with `d` (e.g.
    `+3d`), resolved against the server's own date — the caller's clock is
    not this installation's.
  - **Nulls.** An argument sent as JSON `null` is refused outright, never
    read as absent: "absent means leave alone, null means clear" is a
    distinction a model and a transport both lose, so a later tool's
    `clear` convention (naming the fields to empty) can mean something.
  - **Lists.** A tool that returns several tasks answers with compact
    lines — id, status, priority, due date, title, project, tags, subtask
    counts — never full records (`get_task`, FR-07.9's sibling tools, and
    the tools that write answer in full). The total the filters matched is
    always reported; a page that did not hold all of them says so and
    names one filter still free to narrow with.
  - **Refusals.** A tool reports a refusal as a tool error carrying the
    API's own code and one sentence saying what to do next — which grant to
    ask the owner for, or which project is outside the scope and what is
    inside it — never a bare status code. Authorisation is never
    reimplemented for this: every tool still goes through `app.api.access`,
    the same layer the REST API uses.
- **FR-07.11** `search_tasks` is the task list's own narrowing (F-06), read
  as one call: title text, project, status, assignee, tag, priority, a due
  date range, overdue-ness and parent task, combined so a task is listed
  only if it satisfies every filter set, ordered by the task list's own
  sorts in either direction. `assignee` takes `self`, `owner`, `any_bot`,
  `nobody` or `any` (`self`/`owner` resolved to ids server-side); `preset`
  offers `ready_for_me` (to do, on this bot user), `my_overdue` and
  `recently_filed`, each equivalent to the filters it stands for, and
  setting one of those same filters alongside a preset is refused rather
  than silently overridden. `open_only` (true by default) keeps `done` out
  of the answer regardless of `status`, matching the task list's own
  baseline (FR-06.8); setting it to `false` is the one way `search_tasks`
  reaches `done` work, which the task list itself never shows. The archive
  is never listed, whatever the bot's scope says (FR-05.13).
- **FR-07.12** `get_task` reads one task whole, in one call rather than
  three: the full record `GET /tasks/{id}` returns — title, description,
  status, priority, due date, project, tags, assignee, reporter,
  recurrence, when it was filed, and its subtask counts, a subtask's own
  project being its root task's (FR-02.4) and a task in Review a bot user
  handed over reporting the hand-over (ADR-0008) — plus, each only when
  asked for through its own argument so a caller that wants the task alone
  pays for the task alone: `include_subtasks` (the direct subtasks, as
  `search_tasks`'s own compact lines), `include_comments` (the task's
  comments oldest first, each with its author — "owner", or a bot user by
  name — and when it was written), and `include_attachments` (the task's
  attachments by name and size, never their bytes).
- **FR-07.13** `list_tags` is the owner's whole tag vocabulary (FR-01.26),
  narrowable by `q` (a substring of the name, ignoring case, matching
  anywhere in it rather than only at its start) and limited. Unlike every
  other tool here it is never narrowed by the caller's own scope: tags
  belong to the owner, not to a project (ADR-0003), so a bot user reads the
  same vocabulary whatever projects it can itself reach, and needs no
  permission to do it (`app.models.BotPermissions`'s own rule).
- **FR-07.14** `create_task` files a task, a subtask, or the first
  occurrence of a recurring series, with a title, a description, a due
  date, a priority, tags and an assignee in one call, through the same
  route (`POST /tasks`) and the same rules: a task left without a
  `project` lands in the Inbox, which has to be in the bot user's scope
  like any other project (FR-05.4); naming `parent_task_id` makes a
  subtask, which always takes its parent's project, and naming `project`
  alongside it is refused; a task starts in `backlog` unless `status`
  names another; `recurrence` (FR-01.13) needs a due date, a root task,
  and is refused on one created `done`. `assignee` takes `self` (this bot
  user), `owner` (the account's human), or a bot user's id (FR-01.7); a
  bot user not the account's own, or deleted, is refused (FR-08.21). The
  reporter is always this bot user, and no argument sets it (FR-01.29).
  `title` and `description` carry the same length limits the API itself
  enforces (255 and 2000 characters), declared in the tool's own argument
  schema so an over-long one is refused before the call reaches it at
  all.
- **FR-07.15** `update_task` changes a task through the same route (`PATCH
  /tasks/{id}`) and the same rules, annotated idempotent and returning the
  updated task in full. `title`, `description`, `priority`, `due_date`,
  `project`, `assignee`, `status` and `tags` can each be changed on their
  own, omitting a field leaves it alone, and `tags` replaces the task's
  tags wholesale, as the REST API has it. `status` here reaches only the
  open statuses (FR-01.4): moving a task to `done` is refused, naming
  `complete_task` (#257) as the tool that closes one, which is also where
  the open-subtasks question belongs; moving between open statuses never
  touches a task's subtasks. Moving the due date of the open occurrence of
  a recurring task needs `due_date_scope` (FR-01.17–FR-01.19) to say which
  of the series moves with it, refused without one and refused where there
  is no series to reschedule; reopening an earlier occurrence than the
  latest is refused, naming it (FR-01.16). `project` moves the task, by
  name or id, into or out of scope refused either way (FR-08.8); a subtask
  cannot be moved this way at all, since it follows the task at the top of
  its tree (FR-02.4). `assignee` reads exactly as `create_task`'s does
  (FR-01.7, FR-08.21); the reporter is reached by no argument here either
  (FR-01.29). `description`, `due_date`, `priority` and `assignee` are the
  only fields an explicit `clear` list can empty — naming a field there
  that was also sent a value is refused, and so, server-wide, is any
  argument sent as JSON `null` (FR-07.10's own rule): omission is the only
  way every other field here is left alone. This is also how a hand-over is
  done (ADR-0008): moving `status` to `review` and setting `assignee` to
  `owner` in the same call, with a comment (`comment_task`, #258) saying
  what was done — the tool's own description teaches the convention, since
  nothing in the product moves a task onto the owner because it entered
  Review, and there is no tool of its own for a hand-over.
- **FR-07.16** `complete_task` closes a task through the same route
  (`PATCH /tasks/{id}` with `status: done`) — its own tool rather than an
  argument to `update_task`, for the two things closing needs that no other
  status change does. Annotated consequential (destructive) rather than
  idempotent, so a client confirms it before it runs. A parent with open
  subtasks is refused until `subtasks` says `complete` (closes them too) or
  `leave_uncompleted` (leaves each in the status it had, FR-02.5–FR-02.7);
  unlike the REST API's own refusal, this one names the open subtasks by id
  and title, since nothing else about this call would have shown the
  subtree first. `subtasks` sent on a call that closes nothing — the task
  is already done — is refused instead; closing an already-done task
  otherwise changes nothing and says so (`already_done`), creating no
  occurrence. Closing an occurrence of a recurring task creates the next
  one (FR-01.14) and reports its id and due date, read back since
  `update_task`'s own return value never carried it; the due date comes
  from the series' own schedule (FR-01.15), not from when this call ran.
  `comment` records a note on the task as this bot user's, in the same
  call (FR-03.1, FR-08.10) — its own `add_comments` grant is checked, and
  refused by name, before anything closes, whether or not there turns out
  to be anything to close; the archive, the scope and a missing
  `update_tasks` grant are each refused the way every other tool here
  refuses them (FR-07.10). Returns the closed task in full, alongside
  `next_occurrence` when closing created one.
- **FR-07.17** `comment_task` adds a comment through the same route (`POST
  /tasks/{id}/comments/`) and the same rules: its own `add_comments` grant,
  checked without needing `update_tasks` at all, since reporting on a task
  is not changing it (FR-08.10). Its description states the one thing an
  agent needs to know before it writes: a bot user's comment is append-only,
  never editable or deletable by anyone afterwards, its owner included
  (FR-03.2, FR-08.10) — so it writes once, properly, rather than trying to
  fix a previous note with a second call. `body` is trimmed and refused
  blank, and the API's own length limit (10,000 characters) is declared in
  the tool's own argument schema, so an over-long one is refused before the
  call reaches the route at all. Annotated neither read-only nor
  destructive. Returns the comment as recorded, with its author.
- **FR-07.18** `delete_task` deletes a task through the same route (`DELETE
  /tasks/{id}`) and the same rules, annotated destructive so a client
  confirms it before it runs. A task with subtasks is refused until
  `delete_subtasks` confirms the whole subtree goes too (FR-01.11,
  FR-01.12); unlike the REST API's own refusal, this one names what would go
  down with it, by id and title — every live descendant, open or already
  done, since a delete cascades over all of them, not only the open ones a
  close would ask about (`complete_task`, FR-07.16). The delete is recorded
  as one event covering the whole subtree (FR-10.3), restorable only by the
  owner from their own activity log — this tool's description says plainly
  that the bot user which called it cannot undo it. The archive, the scope
  and a missing `delete_tasks` grant are each refused the way every other
  tool here refuses them (FR-07.10).
- **FR-07.19** `search_activity` is the activity log itself (F-10), read as
  one call rather than a page of raw entries an agent would have to sort
  "finished" out of by hand. Narrowed exactly the way `GET /activity-log/`
  already narrows it for a bot user (FR-10.6, ADR-0011) — by `kind`
  (`completed`, `created`, `changed`, `deleted`, `comments`, `tags`;
  FR-10.8), by `task_id` (a task's own history: the entries about it, its
  comments and files, and the batches that touched it, FR-10.3's own
  reasoning for logging a batch as one act), by `project` (a project's
  chronology, FR-10.11), by `actor` (`self`, `owner`, `any_bot`, or a bot
  user by name or id, refused by name if none matches), and by `since`/
  `until` (FR-10.12) — a date each, widened to the whole day it names so a
  closed period ("last month") is asked for by its two calendar dates. It
  invents no narrowing the endpoint does not have: it is built on
  `app.activity_log.read_activity`, the reader `GET /activity-log/` itself
  calls through to, so the scope narrowing, the all-or-nothing batch rule,
  and the tag exemption stay that one module's code; the withholding of
  `restorable` and the deletion id from a bot's own response is the route's
  own job of declaring two response shapes (ADR-0011). `order` (FR-10.10)
  and paging (`limit`, `offset`) work as they do there. Each result is one
  compact line — `at`, `actor` ("owner",
  or a bot user by name, the convention `get_task`'s own comment rows use),
  `what` (one short phrase, ported from the web UI's own
  `ActivityDescription.tsx`, there being no backend description of an entry
  before this), and `subject` (the task, project or tag it happened to, with
  its id, or, for a batch, the selection it acted on) — never inviting a
  restore this bot user cannot perform. `count` is every entry the filters
  matched, and a `truncated` answer names one filter (`narrow_with`) still
  free to narrow with. Refused by name without `read_activity` (FR-08.9); a
  task or project outside the scope is refused the way the API refuses it,
  never an empty history that would look like one with nothing in it.
- **FR-07.20** `list_completions` is finished work as a table, in one call:
  the question "what did I finish last month?" needs and a task alone
  cannot answer, since a task records `created_at` and a current status,
  never when it reached Done (ADR-0011). Takes a period with both bounds
  (`since` exclusive, `until` inclusive, both required, unlike
  `search_activity`'s own optional pair), and narrows by `project`, by
  `actor` and by `tag`, each read the same way `search_activity`'s own
  arguments are. Composed from the activity log's own narrowing
  (`app.api.access.activity_log_scope`) and the task read model
  (`app.models.Task`, `app.crud.get_task_project_ids`/`get_task_tags`) —
  no new REST endpoint — in one query over the period for the completion
  entries and one more for the tasks they name, never a call per task.
  Each row is one completion: `id`, `title`, `project`, `tags`,
  `priority`, `filed` (when the task was created), `closed` (when this
  completion happened), `days_to_close`, and `closed_by` ("owner", or a
  bot user by name). Two rules keep the count here from reading like one
  built by paging the log and fetching every task by hand:
  - **A batch is one entry, many rows.** Closing several tasks in one act
    writes a single entry naming the new status and every task it touched
    (FR-10.3); this tool expands it into one row per task named, the one
    place a count built from entries alone would undercount.
  - **A reopened task closes twice.** Completing a task, reopening it and
    completing it again writes two completion entries, and this tool
    answers with two rows — both real. The summary's `completions` (every
    row) and `distinct_tasks` (how many different tasks they are) are
    reported side by side so neither is mistaken for the other.

  A task deleted since it closed keeps its row, marked `deleted`, carrying
  only what its own completion entry recorded (its title, or "Untitled
  task" for one named only by a batch) and nulls for everything the task
  itself would otherwise answer — `project`, `tags`, `priority`, `filed`
  and `days_to_close` — rather than a current field a deletion since made
  stale, or a lead time guessed at. An occurrence of a recurring task is
  simply its own task (ADR-0001), so each occurrence's own completion is
  already its own row without this tool doing anything further to keep a
  series from collapsing. The `summary` alongside the rows always covers
  every completion the filters matched, not only the page `limit`
  returns: `completions`, `distinct_tasks`, `by_project` and `by_actor`
  (each a count per name, summing back to `completions`), and
  `median_days_to_close` (over the rows whose lead time is known). `count`
  is `completions` again; a `truncated` answer names one filter
  (`narrow_with`) still free to narrow with, so a partial count is never
  reported as the whole. Refused by name without `read_activity`
  (FR-08.9); nothing outside the scope is ever counted (ADR-0011).

  Eleven tools now complete the MCP surface spec #247 and #248 set out:
  `search_tasks`, `get_task`, `list_tags`, `create_task`, `update_task`,
  `complete_task`, `comment_task`, `delete_task`, `whoami`,
  `search_activity`, and `list_completions`.

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
  | Activity log | never | configurable (`read_activity`, off by default) | never | never |

  A human user holds every one of these grants by construction, not as a
  list kept in step with them by hand: there is no scope to narrow a human,
  so each grant above is simply true for one (see FR-07.4).

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

#### Scope: activity log

- **FR-08.22** With `read_activity`, a bot user reads its owner's activity
  log (see [F-10](#f-10-activity-log-event-feed)) narrowed to its scope:
  entries about the tasks, comments and attachments of the projects in
  scope; about the projects themselves; a task's deletion and restore,
  placed by the project the entry carries; and the owner's whole tag
  vocabulary (ADR-0003), which is unaffected by scope. Entries made by any
  actor — the owner, the bot user itself, or another of the owner's bot
  users — are included: the point is to read the owner's work, not only the
  bot's own. Anything touching an archived project is excluded whatever the
  scope lists (FR-05.13), and an entry recording one act over several tasks
  (FR-10.9) is included only when every task it names is in scope — never
  trimmed to the ones that are.
- **FR-08.23** A bot user's activity-log response omits `restorable` and the
  deletion id. Restoring deleted work (FR-10.4) stays a human-only action,
  unchanged by this grant.
- **FR-08.24** Narrowing a bot user's activity-log read to a task or project
  outside its reach — missing, not the owner's, archived, or outside the
  scope — is a 404, the same answer for all four, never an empty feed.

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
- **FR-09.2** The superuser can view the list of registered users. The list
  is a section of the superuser's own Settings, not a screen of its own, and
  the code of FR-12.16 is issued from the user's line there. Each line shows
  the account's name and email, how many passkeys it holds (said plainly when
  there are none) and when one of them last signed it in.
- **FR-09.3** The superuser's one other administrative function is issuing
  recovery codes to users who have lost every passkey
  (see [F-12](#f-12-sign-in)). There are no others for now.
- **FR-09.4** A person can register their own account; account creation does
  not require an invitation or the superuser's action. Registering is creating
  the account's first passkey (FR-12.2).
- **FR-09.5** The superuser also uses Taskly as a regular user, with their own
  tasks and projects.
- **FR-09.6** On an installation that has no superuser yet, the person who
  registers the e-mail address the installation names as its first superuser
  becomes it. Once a superuser exists, that address is an ordinary one.

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
- **FR-10.6** A bot user reads the activity log only with the `read_activity`
  grant, and then only its scope's entries (see FR-08.9, FR-08.22–FR-08.24).
  Without the grant, it is refused by name (see FR-08.9's permission
  refusal).
- **FR-10.7** A user sees only their own activity log. The superuser is not an
  exception: they see only their own log, not other users'.
- **FR-10.8** The log can be narrowed to one kind of change: Completed,
  Created, Changed, Deleted & restored, Comments & files, or Tags. The kinds
  do not overlap, so an entry answers to exactly one of them. Completing
  several tasks at once is one act and is logged as one entry (FR-10.9); that
  entry is Completed, not Changed. The narrowing is a visible control, lives
  in the URL, and combines with the narrowing to one actor (FR-10.2): one bot
  user, or the reader themselves.
  Neither narrowing ever widens the log past the reader's own entries
  (FR-10.7).
- **FR-10.9** One act over many tasks is one log entry naming what the act
  did, not one entry per task it touched.
- **FR-10.10** The log reads newest first, and can be turned to oldest
  first; the order lives in the URL beside the narrowings and the page, and
  the REST API's log accepts it.
- **FR-10.11** The log can be narrowed to one project's chronology: entries
  about the project itself, about a task in it, about a comment or file on
  such a task, and the deletion or restore of one of its tasks. The narrowing
  lives in the URL beside the others, the REST API's log accepts it
  (`project_id`), it combines with them, and it never widens the log past the
  reader's own entries (FR-10.7).
- **FR-10.12** The REST API's log also accepts `until`, the upper bound to
  `since`: entries up to and including that moment. A moment given without
  an offset is read as UTC, like `since`, and `until` combines with every
  other narrowing, so a closed period — "last month" — can be asked for in
  one request instead of paged until the dates run out.

### F-11. Webhooks

Taskly calls a bot user back when there is something for it to act on
(ADR-0009). A webhook belongs to a bot user and is set by its owner.

#### Configuration

- **FR-11.1** A bot user has two webhooks, each a URL: one for tasks that
  become ready for it (FR-11.4) and one for comments on tasks it is involved
  in (FR-11.6). Each is optional and empty until the owner sets it; a bot user
  with neither set receives nothing.
- **FR-11.2** Webhooks are set, changed and cleared by the owner in the bot
  user's settings in the web UI, like the rest of its configuration
  (FR-07.3). A bot user cannot read or change its own webhooks through the
  REST API.
- **FR-11.3** A webhook URL may use http or https. Addresses that resolve to
  loopback or private ranges are refused when the URL is set and again when a
  delivery is sent, unless the installation is configured to allow them. The
  refusal names the rule.

#### Events

- **FR-11.4** A task becomes **ready** for a bot user when it comes to be in
  To do with that bot user as its assignee: created so, assigned while in To
  do, or moved to To do while assigned. The task webhook is called once per
  task that becomes ready, whoever made the change — the user, another bot
  user, or a bulk action over many tasks, which is one event per task.
- **FR-11.5** A change made by the bot user itself never calls its own
  webhooks. A task leaving the ready state, a restore from the activity log
  and an unarchive are not events, even when the task they bring back is in
  To do and assigned to the bot user.
- **FR-11.6** A bot user is **involved** in a task when it is the task's
  assignee or reporter, or has commented on it. The comment webhook is called
  when anyone other than the bot user itself adds a comment to a task it is
  involved in. Editing or deleting a comment is not an event.
- **FR-11.7** Tasks in an archived project and deleted tasks produce no events
  for any bot user.

#### Delivery

- **FR-11.8** A delivery is an HTTP POST with a JSON body carrying the event
  type (`task.ready`, `comment.added` or `test`), a delivery id, the time of
  the event, the bot user's id, the task's id and title, and for a comment its
  id. Nothing else about the task or comment is sent; the bot user reads the
  rest through the REST API within its scope.
- **FR-11.9** Each bot user has one webhook secret, generated by Taskly when
  its first webhook is set and shown once. Signing needs the secret itself,
  so it is stored encrypted, not as a digest, under the installation's own
  `WEBHOOK_SECRET_KEY` setting rather than a key derived from `SECRET_KEY`:
  rotating `SECRET_KEY` leaves webhooks working, and changing
  `WEBHOOK_SECRET_KEY` makes stored secrets unreadable until each owner
  regenerates theirs (deliveries fail saying so). Every delivery carries a
  timestamp header and an HMAC-SHA256 signature of the timestamp and body
  under that secret. The owner can regenerate the secret; the new one is
  shown once and applies from the next delivery on.
- **FR-11.10** An event is recorded together with the change that caused it,
  and delivered after the change is committed: at once, then after 1, 5, 15,
  60 and 60 minutes if the receiver did not answer with a 2xx within ten
  seconds. After the last attempt the delivery is failed and no longer
  retried. Deliveries are not ordered relative to each other.
- **FR-11.11** The bot user's settings show, for each webhook, its last
  delivery: when it was attempted, whether it succeeded, and the response
  status or the error. A webhook is never disabled automatically, however
  many deliveries fail.
- **FR-11.12** The owner can send a test event to a webhook from the bot
  user's settings. It is sent at once, without retries, and the response
  status or error is shown in the interface.
- **FR-11.13** Deliveries continue whether or not the bot user holds a valid
  token. Deleting a bot user discards its undelivered events and ends its
  deliveries.
- **FR-11.14** Deliveries are not recorded in the activity log.

### F-12. Sign-in

#### Passkeys

- **FR-12.1** A human user signs in with a passkey (WebAuthn) and nothing
  else. There are no passwords, no password reset, and no e-mail is sent for
  signing in or recovering an account.
- **FR-12.2** Registering asks for an e-mail address and creates the account's
  first passkey in the same step. The e-mail is required and unique to one
  account, and it is not verified.
- **FR-12.3** Signing in asks for nothing: the browser offers the passkeys it
  holds for this installation, and offers them again in the e-mail field's
  autofill. Taskly never tells anyone who is not signed in which passkeys, or
  how many, an account has.
- **FR-12.4** A passkey is bound to the installation's hostname, taken from
  the installation's public address and nothing else. Changing that hostname
  makes every passkey unusable; the deployment guide says so.
- **FR-12.5** A passkey requires user verification — a biometric or a PIN on
  the device — both when it is created and every time it is used.
- **FR-12.6** A user holds one or more passkeys. Settings lists them, each
  with a name, when it was created and when it was last used. The name is
  given automatically from the browser and device that made it, and the user
  can rename it; a name is a label, so renaming asks for no confirmation.
- **FR-12.7** The user can add a passkey and remove one. Either takes a fresh
  confirmation with one of the account's passkeys at that moment; the session
  alone is not enough.
- **FR-12.8** The last passkey of an account cannot be removed.
- **FR-12.9** Removing a passkey does not end the sessions it opened; the
  interface says so where a passkey is removed (see FR-12.13).
- **FR-12.10** Each half of a passkey ceremony is tied to the other by a
  challenge that is accepted once and expires after five minutes.
- **FR-12.11** A sign-in opens the same kind of session as before, with the
  same lifetime. Bot users and their tokens are unaffected.
- **FR-12.12** In a browser without passkey support there is no way in. The
  sign-in screen says so plainly; there is no guest mode and no fallback.

#### Sign out everywhere

- **FR-12.13** The user can end every session of their account at once from
  Settings. Each session is refused from its next request on. No confirmation
  with a passkey is asked for this.
- **FR-12.14** Spending a recovery code signs the account out everywhere.

#### Recovery

- **FR-12.15** A user who has lost every passkey asks the superuser for a
  recovery code; there is no self-service recovery.
- **FR-12.16** The superuser issues a recovery code for a user from the list
  of users. Issuing one takes a fresh confirmation with the superuser's own
  passkey. A user has at most one live code; a new one replaces it. A code is
  shown once, kept only as a digest, and expires after 24 hours.
- **FR-12.17** The user enters their e-mail address and the code on the
  sign-in screen and creates a new passkey, which spends the code and signs
  them in. The passkeys the account already had stay; the user lands on the
  list of passkeys, with a prompt to remove any they do not recognise.
- **FR-12.18** A code is burned after five wrong tries. A wrong code, a spent
  one and an expired one are refused in the same words.
- **FR-12.19** The superuser cannot issue a code for their own account. Their
  code is printed by a command run on the server and spent the same way as
  any other.

## 5. Future ideas

Not requirements yet. Recorded so they are not lost.

- **Restore a deleted bot user.** Bring a deleted bot user back and issue it a
  new token.
- **Send existing PDFs to Paperless.** An action for a user who connected
  Paperless after attaching PDFs, to hand the ones kept in Taskly over at
  their own request (FR-04.12 moves nothing on its own).

## 6. Out of scope

- Collaboration between human users (shared projects, assigning tasks to other people, etc.).
- Superuser functions other than viewing the list of users and issuing
  recovery codes.
- Password sign-in, in any form, alongside or instead of passkeys.
- Verifying e-mail addresses, and sending any e-mail for signing in or
  recovering an account.
- A pairing code or QR flow of Taskly's own for adding a device; the
  browser's built-in cross-device passkey sign-in covers it.
- Sign-in events in the activity log.
- Restricting bot users by tags. Bot access is limited by projects only.
- Bot users creating, updating or deleting projects.
- Giving a bot user access to all projects at once.
- More than one token per bot user.
- Bot users editing or deleting comments.
- Bot users renaming or deleting tags.
- Webhooks set or read through the REST API, webhooks on a user rather
  than a bot user, events other than the two in FR-11.4 and FR-11.6, and
  disabling a webhook automatically after failed deliveries.
- Nested projects (projects are flat — see FR-05.5).
- Full-text search over descriptions and comments; the only search is the
  capture line's match on open tasks' titles (FR-06.14).
- Selecting several tasks in the interface and changing them in one act;
  the REST API's batch endpoint remains for bot users.
- Keeping a copy of a PDF in Taskly beside the one in Paperless, sending
  anything but PDFs to Paperless, serving Paperless's archived copy, and
  deleting anything from Paperless.

## 7. Open questions

Q-01 through Q-16, raised while drafting this document and while splitting it
into issues, have been resolved into the requirements above. There are no open
questions at the moment.
