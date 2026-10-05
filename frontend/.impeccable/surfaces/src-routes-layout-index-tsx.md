---
version: 1
slug: "src-routes-layout-index-tsx"
primary_target: "src/routes/_layout/index.tsx"
related_targets: ["src/routes/_layout.tsx","src/components/Sidebar/AppSidebar.tsx","src/components/Tasks/CompactTaskRow.tsx","src/components/Tasks/status.tsx","src/index.css"]
---

# Surface brief: the app shell and the dashboard (redesign slice 1)

Scope: the authenticated app shell (`src/routes/_layout.tsx`, the sidebar, capture) and the
dashboard route (`src/routes/_layout/index.tsx`), with the task row and status glyphs that every
later slice reuses. Visitor mode: **Operate**. This brief carries the direction contract for the
whole redesign; later slices (task panel and capture, task list, Bots and Activity, the rest)
inherit it and add only their own surface strategy.

## Audience, job, action

- The owner, at a desk or on a phone, usually in the morning: what needs me now, what is in my
  hands, what did my agents do while I was away.
- Primary action: write a task down in one step from any screen (the capture line, the `c` key,
  the phone's floating button). Secondary: close a task, close or reopen what an agent handed over.
- Proof on screen: real counts (overdue, due today, changes), real task lines, real activity lines
  naming their actor. No invented figures.
- Constraints: FR-06.7 (My work: assigned to me, grouped In progress, Review, To do, Waiting),
  FR-06.11 (date bands take every open status except Waiting), six statuses (FR-01.4), WCAG 2.2 AA
  in both themes, URL contracts unchanged (`?task=`, filters), PRODUCT.md voice.

## Decisions taken in discovery (2026-10-05)

- Brand: only the name *Taskly* is kept; the old logo and the teal accent are retired.
- Scene: a roomy personal tracker, tens of tasks, phone equal to desktop.
- Specs land with the redesign: statuses Backlog and Review plus My work in slice 1; webhooks in
  the Bots slice; passkeys in the sign-in slice.
- Rejected after mocks: Mission Console and Card Box (too many frames and chrome); eliminated
  with them: Terminal Wayfinding, The Ledger, The Review Queue and the round-1 catalog challengers.
- Craft bar named by the user: Linear.
- Status marks agreed on the mock: Backlog dashed ring, To do solid ring, In progress half-filled
  ring, Review dot in a ring, Waiting a monochrome eye, Done a filled green check. Priority is the
  mark's colour (P1 red, P2 amber, P3 blue, otherwise ink).
- Review hand-off offers only "Close it"; there is no send-back action yet.
- The navigation opens with an "Add a task" entry and its `C` key cap above the screens (issue
  #135, written by the user), so every screen has a pointer entry to capture; on the day page it
  sits beside the capture line.
- Project is a neutral square marker plus name at the right end of the meta line; tags sit in the
  meta line with a tag glyph, no pills; subtask progress is `2/5` with a small tree glyph.

## Direction contract

THESIS: The whole app is one continuous, well-set log. No boxes, no panels, no bezels: hairline
rules and whitespace carry structure, weight and indent carry hierarchy, and every line names
who wrote it. It refuses the category's card grid and the sidebar-of-chips.

OWN-WORLD: White page (near-black page in dark), near-black ink, two greys for secondary text,
hairlines at two strengths. The platform UI sans at 15px body with 13px meta; monospace only for
times and counts. Colour exists only for state that asks for action: red for overdue, green for
done and close; nothing else is coloured, and no accent marks location. Status is a 18px stroked
glyph; priority is its colour. Controls are text first: a frameless capture line with a hairline
underneath, text links as actions, a small outlined key cap for the shortcut. The navigation is a
plain text list with counts, the account row at its foot with an initial avatar and a settings
glyph.

STORY: The owner reads today as a page: the date, one sentence of what needs them, then Overdue,
Due today, In my hands grouped by status, then the agents' changes with the author first. They
act inline: tick a ring, close a review, restore a deletion, type a task at the top.

FIRST VIEWPORT: Left, a 200px text navigation. Main column max 820px: the capture line on top;
the day number at 56px with the weekday and month beside it; one muted sentence of counts; the
Overdue group (red heading) and Due today, each a list of task lines (glyph, title, meta line);
In my hands with its four status groups; the Changes log beneath. On a phone the navigation
collapses to a top bar with a menu, the capture line stays first, the floating button sits
bottom-right.

FORM: The Changelog (git log and release notes as the record), candidate 2 of the round-2
grounded list, chosen by the user on the safer-register re-roll; seed key 018cd79f.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the
verdict, DESIGN.md, and every shipping raster carrying its provenance.

## Memorable moment

The Review hand-off: an agent's finished work appears in the owner's hands with the agent named
and one green "Close it" beside it, inline, no dialog.

## Unresolved

- Whether the capture line creates a titled task immediately (then opens its panel) or opens the
  capture panel as today; decided in slice 2 with the task panel.
- Dark theme exact values; mirrored from the light calibration at build, contrast-checked.
- The brand mark: a wordmark only until a mark is designed inside this world.

Reference: `.impeccable/mocks/changelog-dashboard.html` is the static mock the user approved,
the critique reference at the finish review.
