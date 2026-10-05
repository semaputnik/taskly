---
version: 1
slug: "src-components-tasks-taskdetail-tsx"
primary_target: "src/components/Tasks/TaskDetail.tsx"
related_targets: ["src/components/Tasks/NewTask.tsx","src/components/Dashboard/CaptureLine.tsx","src/components/Records/RecordPanel.tsx","src/components/Tasks/TaskProperties.tsx","src/components/Tasks/TaskComments.tsx","src/components/Tasks/TaskAttachments.tsx","src/routes/_layout.tsx"]
---

# Surface brief: the task panel and capture (redesign slice 2)

Scope: the task panel (`src/components/Tasks/TaskDetail.tsx` and what it composes), the capture
draft (`NewTask.tsx`), the capture line on the day page, and the record column the shell holds
for every record. Visitor mode: **Operate**. The direction contract is inherited from the
dashboard brief (`src-routes-layout-index-tsx.md`, seed 018cd79f); this brief adds only the
surface strategy for the panel and capture.

## Audience, job, action

- The owner opens a task from a list to read what it is, change one thing, add a subtask, a
  file or a comment, and see what a bot user did to it. They open many in a row.
- Primary actions: change a property in place; close the task; add a subtask inline; comment.
- Proof on screen: the task's own record (properties, description, subtasks with progress,
  files with where they are kept) and its own history, comments and events in one chronology.
- Constraints: F-01, F-02, F-03, F-04, FR-10; the Stay-Put Rule (a record opens over the
  current screen, URL `?task=` unchanged); ADR-0005 for the full draft; WCAG 2.2 AA both themes.

## Decisions taken in discovery (2026-10-05, evening)

- **Capture line creates at once.** Enter in "Add a task…" creates the task with that title in
  Backlog, in the Inbox or in the project the list is narrowed to, as one request; a notice says
  so with Open and Undo. The `c` key and the phone's floating button still open the full draft
  (ADR-0005), which is the same panel in draft mode. ADR-0005 gets an amendment note.
- **Notices sit at the top of the screen**, centred on desktop and full-width on a phone, for
  every notice the app raises; there is one place for them.
- **The panel is a right column, not a sheet.** No scrim; the page beside it stays live and the
  open line is tinted. Escape and the close control close it; a next/previous control in the
  panel's bar walks the list the task was opened from. On a phone the column takes the screen.
- **One continuous document, no tabs**: title with the status mark as the closing control, a
  quiet property list, Description, Subtasks, Files, Activity, then Delete task at the foot.
- **Priority is coloured in the property list** too: a flag and the label in P1 red, P2 amber,
  P3 blue, P4 ink, the same rule as the status mark.
- **Subtasks are captured inline**: a field at the end of the list; Enter creates the subtask
  there with defaults (Backlog, the parent's project) and keeps the field for the next one.
- **Activity is one chronology**: the task's own log events as muted one-liners and comments
  with author and body, oldest first, day separators, the composer at the end (⌘/Ctrl Enter
  posts). Own comments edit and delete with Undo; bot users' comments are read-only. Needs a
  log filter by task in the API.
- Project, tag and bot panels keep their current content inside the new column until their
  own slice.

## First viewport of the panel (desktop)

A 560px column with a hairline on its left, sticky, scrolling on its own. A 52px bar: project
name, "opened by you, 24 Sept", next/previous and close at the right. The title at 22px/600
beside a 22px status mark. The property list: 96px label column in ink-3, values as 30px text
buttons that tint on hover and show a chevron; Created read-only with its author. Then the
four sections under 13px/600 headings with hairlines, counts in mono, the section's action at
the heading's right or as a line at the end. On a phone the same, full width, 16px gutters.

## Unresolved

- Whether a bot user's handed-over task (Review) shows its "Close it" also in the panel's bar;
  decided in the build if cheap, else the task list slice.
- Attachment upload progress and failure states beyond a notice.

Reference: `.impeccable/mocks/changelog-task-panel.html`, the approved mock, the critique
reference at the finish review.
