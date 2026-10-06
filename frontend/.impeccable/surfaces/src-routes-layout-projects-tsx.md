---
version: 1
slug: "src-routes-layout-projects-tsx"
primary_target: "src/routes/_layout/projects.tsx"
related_targets: ["src/routes/_layout/tags.tsx","src/routes/_layout/settings.tsx","src/routes/login.tsx","src/components/Projects/ProjectPanel.tsx","src/components/Tags/TagPanel.tsx"]
---

# Surface brief: Projects, Tags, Settings and sign-in (redesign slice 5)

Scope: the Projects route (`src/routes/_layout/projects.tsx`) and the project column, Tags and
the tag column, Settings (with Users for the superuser and the Paperless connection), and the
sign-in, sign-up and recovery screens. Visitor mode: **Operate**. The direction contract is
inherited from the dashboard brief (`src-routes-layout-index-tsx.md`, seed 018cd79f); this brief
adds only the surface strategy for these screens. It is the last slice of the redesign.

## Audience, job, action

- Projects: see what each project holds and reach its tasks in one click; file a task into it;
  archive, unarchive, delete.
- Tags: fold tags that look alike, rename, reach the tasks a tag is on.
- Settings: who I am, what signs me in, where my PDFs go, and (as the superuser) who else is
  on this installation and how to hand them a recovery code.
- Sign-in: one action, nothing to type; recovery when every passkey is gone.

## Decisions taken in discovery (2026-10-06)

- **One click to a project's tasks**: on the Projects page the open count at the right of each
  line is a link into the task list narrowed to the project; the column repeats it as "Open the
  list →" and shows the first open tasks with a capture line into the project.
- **Archive merges into Projects**: archived projects are a quiet section at the end of the
  Projects page, with their kept tasks reachable the same way; the Archive route and the
  navigation entry go, the old address lands on Projects.
- **Tags as lines** with a "Look alike" group row at the top (Merge into, Keep apart), the task
  count as a link, and a column with the tasks, a one-step merge and Delete with the number of
  tasks it will touch.
- **Settings as one document**: Profile (name, email, appearance, which leaves the account
  menu), Passkeys (rename, remove), Sessions (sign out everywhere), Paperless, Users (superuser
  only; the Admin route goes), Account (delete).
- **Paperless in full** (F-04): the connection in Settings, PDFs kept in Paperless from then on,
  "kept in Paperless" on the task's files with the way back to the document.
- **Sign-in screens** in the world: wordmark, one heading, one sentence, one filled action; the
  recovery screen shows the code in mono and the tries left; "Self-hosted at <host>" at the foot.
- **Every page column uses the shared 820px measure** that centres while no record is open and
  sits beside the record column when one is (PR #204); Projects, Tags and Settings adopt it.

## First viewports

- Projects (desktop): "Projects" with "+ New project", a counts sentence, lines with the open
  count at the right, "Archived" beneath; the column opens beside as for a task.
- Settings: centred column, sections in the order above.
- Sign-in: a centred 420px card-less column on the page ground, nothing else on screen.

## Unresolved

- Whether a project's column should offer closing tasks inline; decided in build (same as bots).
- Whether the superuser's Users section should list each user's bot users; not now.

References: `.impeccable/mocks/changelog-projects.html`, `changelog-tags.html`,
`changelog-settings.html`, `changelog-signin.html`, the approved mocks and the critique reference
at the finish review.
