---
name: Taskly
description: A neutral, instrument-grade task surface where one teal signal marks every action worth taking.
colors:
  signal-teal: "oklch(0.52 0.10687 182.4689)"
  signal-text-night: "oklch(0.7 0.10687 182.4689)"
  on-signal: "oklch(0.985 0 0)"
  ground: "oklch(0.97 0 0)"
  paper: "oklch(1 0 0)"
  panel: "oklch(0.985 0 0)"
  surface-quiet: "oklch(0.97 0 0)"
  ink: "oklch(0.145 0 0)"
  ink-strong: "oklch(0.205 0 0)"
  ink-muted: "oklch(0.52 0 0)"
  hairline: "oklch(0.922 0 0)"
  focus-ring: "oklch(0.708 0 0)"
  alert-red: "oklch(0.577 0.245 27.325)"
  alert-red-lifted: "oklch(0.704 0.191 22.216)"
  night-ground: "oklch(0.18 0 0)"
  night-panel: "oklch(0.23 0 0)"
  night-quiet: "oklch(0.29 0 0)"
  night-ink: "oklch(0.985 0 0)"
  night-ink-muted: "oklch(0.708 0 0)"
  night-hairline: "oklch(1 0 0 / 10%)"
  scrim: "oklch(0 0 0 / 50%)"
  night-scrim: "oklch(0 0 0 / 70%)"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', 'Noto Sans', Arial, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.333
    letterSpacing: "-0.025em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', 'Noto Sans', Arial, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "normal"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', 'Noto Sans', Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.4286
    letterSpacing: "normal"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', 'Noto Sans', Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.4286
    letterSpacing: "normal"
  micro:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', 'Noto Sans', Arial, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.333
    letterSpacing: "0.05em"
rounded:
  sm: "0.375rem"
  md: "0.5rem"
  lg: "0.625rem"
  xl: "0.875rem"
  pill: "9999px"
  check: "4px"
spacing:
  hair: "0.25rem"
  tight: "0.5rem"
  snug: "0.75rem"
  base: "1rem"
  section: "1.5rem"
  page: "2rem"
components:
  button-primary:
    backgroundColor: "{colors.signal-teal}"
    textColor: "{colors.on-signal}"
    rounded: "{rounded.md}"
    padding: "0.5rem 1rem"
    height: "2.25rem"
    typography: "{typography.label}"
  button-outline:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0.5rem 1rem"
    height: "2.25rem"
    typography: "{typography.label}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0.5rem 1rem"
    height: "2.25rem"
    typography: "{typography.label}"
  button-destructive:
    backgroundColor: "{colors.alert-red}"
    textColor: "{colors.on-signal}"
    rounded: "{rounded.md}"
    padding: "0.5rem 1rem"
    height: "2.25rem"
    typography: "{typography.label}"
  input:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0.25rem 0.75rem"
    height: "2.25rem"
    typography: "{typography.body}"
  badge-outline:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "0.125rem 0.5rem"
    typography: "{typography.micro}"
  badge-secondary:
    backgroundColor: "{colors.surface-quiet}"
    textColor: "{colors.ink-strong}"
    rounded: "{rounded.pill}"
    padding: "0.125rem 0.5rem"
    typography: "{typography.micro}"
  table-head:
    backgroundColor: "{colors.surface-quiet}"
    textColor: "{colors.ink-muted}"
    padding: "0 1rem"
    height: "2.75rem"
    typography: "{typography.micro}"
  table-cell:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    padding: "0.75rem 1rem"
    typography: "{typography.body}"
  sidebar-item-active:
    backgroundColor: "{colors.surface-quiet}"
    textColor: "{colors.ink-strong}"
    rounded: "{rounded.md}"
    padding: "0.5rem"
    height: "2rem"
    typography: "{typography.body}"
  dialog:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "1.5rem"
    width: "32rem"
---

# Design System: Taskly

## Overview

**Creative North Star: "The Quiet Control Room"**

Taskly is a room full of instruments, not a poster. A person and their bots
operate on the same tasks through the same records, and the interface's job is
to keep those records legible and never to compete with them. Every surface is
neutral grey or white; every control is a fixed-height, unshouting instrument;
and exactly one colour — Signal Teal — is allowed to glow. When something on
screen is teal, it is either the action to take, the place you are, or the field
you are in. Nothing else earns it.

The character is **precise, calm, and unobtrusive**. Density is moderate: the
page breathes at 24–32px between sections but stays tight inside a control, so
a table of forty tasks reads as one continuous instrument rather than forty
cards. Type is the system sans at four working sizes; there is no display face,
no decorative weight, no ornament. Hierarchy comes from weight and colour
temperature (ink versus muted ink), not from size jumps. The system is
dual-theme by construction: light and dark are two calibrations of the same
room, not two designs, and every token has a counterpart on the other side.
Each theme also declares its `color-scheme`, so native controls, date pickers
and scrollbars follow it rather than staying light.

Depth is the one place the system is deliberately opinionated. Structure is
built from ground, hairlines, and tonal steps; a real shadow is reserved for
things that have genuinely left the page. See **Elevation & Depth** — it carries
the rule the rest of the system defers to.

**Key Characteristics:**
- One accent, used sparingly: teal marks action, location, and focus — nothing else.
- Neutral achromatic base (chroma 0) for every surface, border, and text tone.
- Fixed control height of 36px (2.25rem) across buttons, inputs, and selects.
- Tables are the primary content form; cards are not part of the shipped vocabulary.
- 10px base radius, stepping to 6px for small controls and full-round for badges.
- Light and dark are mirrored calibrations, never independent designs.

## Colors

An achromatic grey field with a single chromatic voice: every surface, border,
and text tone sits at chroma 0, so the teal accent and the red alert are the
only saturated things a screen can contain.

### Primary
- **Signal Teal** — the sole accent. It marks the primary button (including the
  app-wide Add Task action in the sidebar), the checked state of a task
  checkbox, the brand mark, text links, and the text-selection highlight. Note
  that the active navigation item does *not* take it: location is marked with
  Surface Quiet, and the `sidebar-primary` token is defined but unused. As a
  fill it has one value in both themes, dark enough that On Signal on it reads
  at 4.9:1: it once lifted in dark mode to keep its weight against the dark
  ground, and that took its own label down to 2.9:1.
- **Signal Text** (`--link`, `text-link`) — the teal as *text*: links and the
  completed state. In light it is Signal Teal itself (4.7:1 on Ground, 5.1:1
  on Paper). In dark it lifts to `signal-text-night` (7.4:1 on Night Ground,
  6.6:1 on Night Panel), because here the teal is what is laid on the dark
  ground, not what carries a label. A link never uses `text-primary`.
- **On Signal** — the near-white laid on top of teal and red fills. Never pure
  white; it stays one step below paper so a teal button does not vibrate.

### Tertiary
- **Alert Red** — destructive intent, and one status: the delete/revoke/archive
  confirmation button, invalid field borders and rings, error text — and
  *overdue*, the one state a task tracker is right to raise its voice about (the
  dashboard's overdue band and its days-late counts). It is no other status and
  never decorates. In dark mode it shifts to
  `alert-red-lifted`, which is lighter and noticeably less saturated, because
  full-chroma red on a dark ground reads as an emergency rather than a warning.

### Neutral
- **Ground** — the surface the work area rests on, and nothing else. Every
  sheet laid on it is lighter. It shares its value with Surface Quiet by
  design: the system reuses an existing step rather than inventing a grey for
  one job.
- **Paper** — the fill of every sheet and floating surface in light mode:
  tables, filter bars, settings panels, dialogs, popovers, dropdowns, outline
  buttons, and the active tab pill. If a thing sits *on* the page rather than
  *being* the page, it is Paper.
- **Panel** — the sidebar's fill in light mode. Between Ground and Paper, so
  the navigation column reads as chrome rather than as either.
- **Surface Quiet** — the workhorse recessive fill: table headers, tab bars,
  hovered rows, hovered menu items, the active sidebar item, secondary buttons
  and badges, skeleton blocks.
- **Ink** — body text, headings, table cell content. Near-black, not black.
- **Ink Strong** — the text laid on Surface Quiet fills (secondary buttons,
  active sidebar item), slightly lighter than Ink so the filled chip does not
  read heavier than plain text.
- **Ink Muted** — supporting text: page subtitles, column headers, empty-state
  copy, project and due-date cells, placeholder text, footer, inactive icons.
  Roughly half the working text on any screen is this tone by design, so it
  clears AA everywhere it is laid: 5.1:1 on Ground and Surface Quiet, 5.5:1 on
  Paper; in dark, 7.3:1 on Night Ground and 5.4:1 on Night Quiet.
- **Hairline** — every border and input stroke in light mode. It is the primary
  structural device of the whole system.
- **Focus Ring** — the neutral ring colour, rendered as a 3px halo at 50% alpha.
- **Night Ground / Night Panel / Night Quiet / Night Ink / Night Ink Muted /
  Night Hairline** — the dark calibration. Night Ink is the same value as On
  Signal, and the dark hairline is a 10% white overlay rather than a solid grey
  so it survives on top of differently-lit panels. Night Ground sits at 0.18,
  deliberately off the near-black floor: below it no scrim can visibly darken
  the page (see the Scrim Rule).
- **Scrim / Night Scrim** — the veil a modal layer lays over the page: 50% black
  in light, 70% in dark.

### Named Rules

**The One Signal Rule.** Teal appears at most a few times per screen and always
answers one of three questions: *what do I press*, *where am I*, or *what am I
typing in*. A teal fill that answers none of those is decoration and must be
removed. Status, category, priority, and tag are communicated with neutrals and
shape — never by spending the accent.

**The Chroma Zero Rule.** Every structural token — surface, border, text,
skeleton, divider — has chroma exactly `0`. There are no warm greys and no cool
greys. If a neutral in this system carries chroma, it is a bug, not a mood.

**The Mirrored Theme Rule.** No colour may be introduced in one theme without
its counterpart in the other, and the two are tuned for equal apparent weight
rather than equal numeric lightness.

A colour is never defined alone. Every colour token records what is laid on it
or what it is laid on, and the contrast that pair yields — 4.5:1 at least for
text — in the token's comment in `index.css`. A recalibration re-checks *both*
sides of every pair it touches: lifting the teal fill for weight on a dark
ground once lowered its own label to 2.9:1, because only the ground was checked.
Where one value cannot serve as both a fill and a text colour, the two become
two tokens (Signal Teal and Signal Text), not a compromise.

## Typography

**Display Font:** none — the system stack carries every role.
**Body Font:** the platform UI sans (`-apple-system, BlinkMacSystemFont,
'Segoe UI', Roboto, 'Helvetica Neue', 'Noto Sans', Arial, sans-serif`).
**Label/Mono Font:** none distinct.

**Character:** the interface speaks in the operating system's own voice. Using
the native UI face is the typographic expression of the North Star — a control
room does not brand its gauges. Personality comes from the weight ladder and
from one micro-typographic move (the uppercase table header), not from the
letterforms.

### Hierarchy
- **Display** (700, 1.5rem / 24px, line-height 1.333, tracking `-0.025em`): the
  single page title at the top of each route — "Tasks", "User Settings". Exactly
  one per screen, always paired with a muted subtitle line beneath it.
- **Title** (600, 1.125rem / 18px, line-height 1): dialog titles. The tight
  line-height is intentional: a dialog title is a label for the dialog, not a
  paragraph opening.
- **Body** (400, 0.875rem / 14px, line-height 1.4286): the default for
  everything — table cells, menu items, descriptions, helper text. Inputs render
  at 1rem below the `md` breakpoint and drop to 0.875rem above it, so mobile
  browsers do not zoom on focus.
- **Label** (500, 0.875rem / 14px): form labels, button text, sidebar items,
  emphasised table content such as a task title. Medium weight is the system's
  way of saying "this is interactive or this is the subject".
- **Micro** (600, 0.75rem / 12px, tracking `0.05em`, uppercase): reserved for
  table column headers. Also the size — though not the case or tracking — of
  badges, filter labels, and the user's email in the sidebar.

### Named Rules

**The Uppercase-Header Rule.** Uppercase with letter-spacing belongs to one job:
labelling a band of rows. That covers table column headers and the group headers
inside a list sheet — the dashboard's "Overdue" and "Due today" bands, and the
"While you were away" band over its log. Both sit on the same `muted/50` fill,
because they are the same device. It is the system's one micro-typographic
signature and it holds only while nothing else borrows it: page headings,
buttons, tabs, and badges are all sentence case.

**The Two-Weight Rule.** Text is 400 or 500 in the body of the interface; 600
and 700 are reserved for the four headline roles above. A third weight inside a
table row or a form is noise.

## Layout

The app is a fixed left sidebar plus a content column. The sidebar is 16rem
(256px) wide, collapses to a 3rem (48px) icon rail whose state persists in a
cookie for a week, and becomes an 18rem off-canvas sheet below the `md`
breakpoint (768px). Content sits under a sticky 4rem (64px) header that holds
only the sidebar trigger, and is padded 1.5rem on small screens and 2rem from
`md` up. The content itself is capped at `max-w-7xl` (80rem / 1280px) and
centred, so on a wide display the table stops growing rather than stretching to
the window.

Vertical rhythm inside a route is a single value: 1.5rem (24px) between the page
header, the filter bar, the table, and any footer block. Inside a control the
rhythm tightens to 0.75rem and 0.5rem; inside a dialog it is 1rem between fields
and 1.5rem of padding around them. The spacing scale is Tailwind's 0.25rem base,
and in practice the system uses six steps: 4, 8, 12, 16, 24, 32px.

Tables are full-bleed within the content column and scroll horizontally inside
their own bordered container rather than widening the page. Filter bars wrap
(`flex-wrap`, 0.75rem gap) instead of scrolling or collapsing into a menu, so
every active filter stays visible at every width. The authentication routes use
a different model entirely: a two-column split at `lg` (1024px) with the brand
mark centred in a muted left panel and a `max-w-xs` (20rem) form column on the
right, collapsing to the form column alone below that.

### Named Rules

**The 24-and-Done Rule.** Sections within a route are separated by 24px. Not 20,
not 28, and not a second value introduced for one screen. If two blocks need to
feel more related than that, nest them in a bordered container instead of
shrinking the gap.

## Elevation & Depth

Depth is built in three tiers — **ground, hairline, float** — and the tier is
decided by one question: *has this thing left the page?*

**Ground** is the recessive plane the content sits on. **Hairline** is how
in-page structure is drawn: a 1px border plus a tonal step is what separates a
table from the page, a filter bar from the table, a sidebar from the content,
and a table header from its rows. In-page surfaces are flat — they carry no
shadow at all, because a shadow on something that has not moved is a lie about
the space. **Float** is reserved for the layers that genuinely sit above the
page: dialogs, sheets, dropdowns, popovers, selects, and toasts. Those get a
real, soft, wide shadow, and the modal ones get the scrim underneath so the
page visibly recedes.

The `shadow-xs` present on inputs, checkboxes, and outline buttons is not a
fourth tier — it is a sub-pixel seat that keeps a control from looking pasted
onto its background. Treat it as part of the hairline tier.

**The token split this depends on.** `--background` is the ground and `--card`
is the sheet, and they are never interchangeable. Anything that should read as
laid *on* the page takes `bg-card` — a table container, a filter bar, a settings
panel, a dialog, an outline button. Only the page itself takes `bg-background`.
Before this split both were pure white in light mode, so every sheet was white
on white and held together by its border alone; the tone step is what makes the
hairline tier legible.

### Shadow Vocabulary
- **Seat** (`box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05)`): inputs, checkboxes,
  outline and secondary buttons. Sub-perceptual; keeps a control seated.
- **Raised** (`box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)`):
  the active tab pill, and the sidebar in floating variants. The only in-page
  use of a visible shadow, and it marks a selected state, not a container.
- **Menu** (`box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)`):
  dropdown menus, select popovers.
- **Float** (`box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)`):
  dialogs and sheets — the top layer of the app.

### Named Rules

**The Left-the-Page Rule.** A shadow is permitted only on an element that has
left the page plane: dialog, sheet, popover, dropdown, select, toast. Tables,
filter bars, headers, sidebars, and content containers are flat and are separated
by a hairline and a tonal step. A card-with-shadow is not a Taskly surface.

**The Scrim Rule.** Anything modal brings the scrim (`bg-scrim`) with it. A
floating layer that traps focus must visibly demote what it covers, and
"visibly" is measured: the page ground has to fall at least 0.06 in OKLab
lightness under the veil. A fixed alpha does not guarantee that — 50% black
moved the old near-black dark ground by 0.03 — so the dark theme uses a denser
veil over a raised ground (0.063), and light keeps 50% (0.39).

## Shapes

Corners are consistently soft but never pill-round, except where roundness
carries meaning. The base radius is 0.625rem (10px) and the system steps down
from it: 0.875rem (14px) for the largest containers, 0.625rem for dialogs, table
containers, tab bars, and menus, 0.5rem (8px) for buttons, inputs, selects, and
sidebar items, 0.375rem (6px) for the smallest chips, and a hard 4px for the
task checkbox — small enough that rounding would read as a radio button.

Badges are the one fully-round form (`9999px`). That is a semantic choice: a
pill means *a value attached to a record* — a tag, a priority, a recurrence rule
— while a rounded rectangle means *a control you can press*. Avatars are the
only circles.

Borders are uniformly 1px, drawn in `hairline` (light) or a 10% white overlay
(dark), and they are the dominant form-giving device: the app has many more
borders than it has fills. Nothing in the system uses a border thicker than 1px;
emphasis is achieved by changing the border's colour to `signal-teal` or
`alert-red`, never its width.

### Named Rules

**The Round-Check Rule.** A round check is completion, and completion only: it
is the one place the product toggles a record's own state from a list, and it
sits beside the thing it is about. A square check selects a row for a batch.
The two live in the same row and must never be confused, which is why they are
different shapes rather than two identical boxes in different columns.

**The Pill-Means-Data Rule.** Fully-round is reserved for badges — values
attached to a record. If it is pressable and pill-shaped, it is miscommunicating.

**The One-Pixel Rule.** Every border in the system is 1px. Emphasis changes
colour, never weight.

## Components

### Buttons
- **Shape:** softly rounded (0.5rem / 8px), fixed 2.25rem (36px) height at
  default size, with 2rem (32px) small and 2.5rem (40px) large variants and
  square icon-only versions at each height.
- **Primary:** Signal Teal fill with On Signal text, 0.5rem × 1rem padding,
  0.875rem/500 label. Padding tightens to 0.75rem horizontally when the button
  contains an icon, so an icon+label button does not read wider than its
  neighbours.
- **Hover / Focus:** hover drops the fill to 90% opacity — the only hover move
  the primary button makes; there is no lift, no scale, no shadow change. Focus
  is a 3px ring in `focus-ring` at 50% alpha plus a border in the same colour,
  applied on `:focus-visible` only. All transitions are 150ms
  `cubic-bezier(0.4, 0, 0.2, 1)`.
- **Outline:** paper fill, hairline border, seat shadow; hovers to Surface Quiet.
  This is the default for anything that is not the page's single main action —
  pagination, sort direction, the theme toggle.
- **Secondary:** Surface Quiet fill, no border, hovers to 80% opacity.
- **Ghost:** no fill or border until hover, where it takes Surface Quiet. Used
  for in-row actions, menu triggers, and "Clear filters".
- **Destructive:** Alert Red fill with white text; in dark mode the fill drops to
  60% opacity so it sits back into the panel.
- **Link:** teal text, underline on hover with a 4px offset.
- **Loading:** a spinning `Loader2` replaces nothing — it is prepended at 1.25rem
  and the button disables itself. The label never changes to "Loading…"; the
  button keeps saying what it does.
- Every button and `role="button"` in the app carries `cursor: pointer`.

### Chips (Badges)
- **Style:** fully round, 0.125rem × 0.5rem padding, 0.75rem/500 text, inline SVG
  icons at 0.75rem.
- **Secondary** (Surface Quiet fill, no border) is the tag chip.
- **Outline** (transparent fill, hairline border, ink text) is the metadata chip:
  priority, recurrence rule. Outline reads lighter than secondary, which is
  correct — a priority is a property, a tag is an assignment.
- **Default** (teal fill) exists in the API but is not used in the product
  surface, and should not be: see The One Signal Rule.

### Cards / Containers
The system does not use a card vocabulary. `Card` exists as an unused primitive
in `components/ui`; the shipped containers are the **table container** and the
**filter bar**.
- **Table container:** 0.625rem (10px) radius, 1px hairline border, no shadow,
  horizontal overflow contained inside it.
- **Filter bar:** 0.5rem (8px) radius, 1px hairline border, 0.75rem padding,
  wrapping flex row with 0.75rem gaps and bottom-aligned controls.
- **Internal padding:** 0.75rem for the filter bar, 1rem horizontally in table
  cells, 1.5rem in dialogs.

### Tables
The signature component of the system.
- **Header:** Surface Quiet fill at 50% alpha, 2.75rem (44px) tall, 1rem
  horizontal padding, `micro` type — 0.75rem, 600, uppercase, `0.05em` tracking,
  in Ink Muted. Header rows do not respond to hover.
- **Rows:** 1px hairline bottom border, dropped on the last row; hover fills with
  Surface Quiet at 50% alpha, transitioning colour only. Cells are 0.75rem ×
  1rem, `whitespace-nowrap`, vertically centred. A row that opens a record is a
  control: it takes focus, answers Enter and Space, shows the focus ring, and
  carries an accessible name saying what it opens ("Open Kitchen rebuild"). It
  stays a `row` for assistive technology — a button's role would take the
  table's structure away from the readers who depend on it.
- **No action column.** A row carries no menu and no buttons: it opens the
  record, and everything the record can do lives in its panel.
- **Content conventions:** the subject column is 500 weight; every supporting
  column is Ink Muted; a completed task's title takes `line-through` plus Ink
  Muted; absent values ("No due date", "No tags") are italic Ink Muted rather
  than blank, so an empty cell is never ambiguous with a failed render.
- **Hierarchy:** none. A row carries a small `CornerDownRight` glyph when it is
  a subtask, and nothing more. Indentation would claim a parent–child link to
  the row above, which sorting, filtering, or a parent outside the result set
  can all make false. Real hierarchy lives in the task's detail panel, where
  the parent is named and the children are listed.
- **Empty state:** an icon, a title, one line of Ink Muted copy capped at 24rem,
  and where there is one, the way out. It fills the table body rather than
  sitting in a cell, so the sheet keeps its header and its height.
- **Loading:** the table draws its own skeleton from the same column
  definition it will render, so the two can never disagree and the page does
  not jump when the rows land. Its row count is what is expected, not a fixed
  five.
- **Paging and sorting belong to the server.** The page and the order ride in
  the URL, the request carries them, and the footer prints the count the API
  returned — the number of rows that match, not the size of the window that was
  fetched. A table that pages an array it was handed can only page what it was
  handed, and reports that window as the total.
- **Sorting lives on the column header.** A sortable header is a button inside
  its `th`: it toggles the field, the same header again reverses it, the
  direction shows as an arrow, and the `th` carries `aria-sort`. Sorting is not
  a filter and is never cleared with them.
- **Selection is the first column**, a square check with a select-the-page
  control in the header. A selection outlives paging within one filter set and
  is dropped when the filters change; when a whole page is selected and more
  match, the surface says so and offers to extend — the two are different acts
  and the difference is stated, never implied.
- **Batch actions appear only with a selection**, as a bar above the table
  stating the count, offering only what applies, and carrying its own clear
  control. A destructive batch keeps a confirmation naming the count.
- **Footer:** the matching count, and the page position when there is more than
  one page, with Previous and Next. Counts are Ink at 500 weight, their
  surrounding words Ink Muted — the numbers are what you are scanning for.
- **Narrow screens:** the table scrolls sideways as a named region the keyboard
  can reach, with edge shadows and, below `md`, a line in words saying the row
  continues. A table that appears to end at the screen edge is the one thing
  this must not be.

### Inputs / Fields
- **Style:** transparent fill, 1px hairline border, 0.5rem (8px) radius, 2.25rem
  (36px) tall, 0.25rem × 0.75rem padding, seat shadow. In dark mode the fill
  becomes `night-quiet` at 30% so the field is legible against the panel.
- **Focus:** the border moves to `focus-ring` and a 3px ring at 50% alpha appears
  around it; only `color` and `box-shadow` transition, so nothing reflows.
- **Error:** driven by `aria-invalid` — the border turns Alert Red and the ring
  becomes red at 20% (40% in dark). The message renders beneath the field at
  0.75rem in Alert Red. Validation runs on blur, not on every keystroke.
- **Disabled:** 50% opacity and `not-allowed` cursor.
- **Labels:** 0.875rem/500, 0.5rem above the field. Filter labels are the
  exception at 0.75rem in Ink Muted — they annotate a control rather than name a
  required field.

### Navigation
- **Sidebar:** `panel` fill, 1px right border, 16rem wide, and the app's only
  chrome — the work area has no header of its own above `md`. The header row
  carries the account control with Activity and the collapse toggle beside it,
  then the full-width Add Task action; the nav list follows; the footer row
  pairs the appearance control with Settings. Destinations live in the list and
  utilities flank the two wide controls, so neither repeats the other.
- **One centre line:** every icon in the rail — avatar, utility, Add Task,
  nav, appearance — is centred 1.5rem from the sidebar's left edge in both
  states. Collapsing changes what is visible, never where the column sits. Any
  new sidebar control has to land on that axis.
- **Items:** 0.875rem body type with a 1rem lucide icon, 0.5rem radius, 2rem
  tall. Default is plain on the panel; hover takes Surface Quiet; the active item
  takes Surface Quiet with Ink Strong text. Active is determined by exact path
  match.
- **Collapsed:** the rail shows icons only and every item grows a tooltip — the
  collapsed state never costs the user a label.
- **Mobile:** below `md` the sidebar becomes an 18rem sheet, and tapping any item
  closes it.
- **Account block:** the first thing in the sidebar. A 1.75rem avatar with
  initials on a fixed zinc fill, the user's name at 0.875rem/500 truncating
  beside it, and a `ChevronDown` affordance. It opens a dropdown that repeats
  the block at full size with the email beneath — the menu confirms whose
  account it is acting on. Collapsed to the icon rail it keeps the avatar alone,
  so the rail still answers "whose account is this".

### Dialogs
The system's only heavy surface. It confirms, and it edits the records that
have no panel of their own; it never creates a task, which is what capture is
for.
- Centred, `max-w-lg` (32rem) capped at `calc(100% - 2rem)`, 0.625rem radius,
  1.5rem padding, 1rem gaps, float shadow over the scrim.
- Enter and exit both animate: fade plus a 95%→100% zoom over 200ms.
- A close affordance sits at 0.75rem from the top-right at 70% opacity,
  reaching full opacity on hover — a 32px target, 44px on a touch pointer.
- Escape and a click outside dismiss a dialog, with one exception: a dialog
  whose dismissal cannot be taken back — the one-time token reveal — has no
  close affordance, ignores both, and closes only once the reader confirms
  what they are leaving behind.
- Title at 1.125rem/600, description beneath in 0.875rem Ink Muted. Footer
  actions align right on desktop and reverse into a stack on mobile, so the
  primary action is thumb-nearest on a phone and rightmost on a desktop.

### List sheet
The dashboard's form, and the pattern for any short list that is a preview
rather than a table.
- One bordered `bg-card` sheet holding several groups. Each group opens with a
  `muted/50` band carrying its name in `micro` type and its count in Ink Muted
  tabular figures; the rows follow, separated by hairlines, the last one losing
  its rule.
- Rows reserve their trailing columns whether or not a group fills them, so the
  priority badge does not move from one group to the next.
- A sheet never grows past about five rows per group. Past that it ends in a
  full-width "N more" row that hands off to the filtered table, because the
  table is where long lists belong.
- The empty state lives *inside* a band rather than replacing it, so the sheet
  keeps its label when it has nothing to show.

### Detail panel
A record's one address, opened by clicking its row — the same surface for every
record type the product has: tasks, projects, tags and bot users. A right-hand
`Sheet` at `max-w-xl` over the standard scrim, scrolling as one column:
- **Header:** the breadcrumb that locates it (the record's type, and the
  project and parent where there are any), the completion control, and the
  record's name at 1.25rem/600 — as the control that renames it, where it can
  be renamed. Bordered off from the body.
- **Properties:** a label column of Ink Muted text with a 1rem icon, and the
  value beside it, baseline-aligned. The column is `8rem` from `md` and
  proportional below it, so a phone does not spend a third of its width on
  labels. Rows are separated by hairlines and
  every value starts on the same line, whatever its type — text, badge, chip
  row. An unset value reads *Not set* in italic Ink Muted, never blank. The
  record's own history belongs here too: when it was created is a property, not
  a footnote.
- **The corner is for dismissal only.** Close sits alone in the top-right, a
  32px target under a mouse and 44px under a thumb, like every dismiss control
  in the product. The corner of a sheet is muscle memory for *dismiss*, so
  nothing that destroys is ever placed beside it.
- **Delete sits at the foot**, below everything else, as one labelled control
  — "Delete task", not a bare icon — separated by a hairline.
- **A record that cannot be read says so at once.** A skeleton stands only
  while a request is on its way. A record the API refuses — deleted, not the
  reader's — reads "could not be opened", identically for both, with Close; a
  request the server did not answer reads "could not be loaded", with Try
  again beside Close, said after the first failed attempt even while retries
  carry on behind it. A refusal is never retried.
- **Description** in its own banded section, so an empty one is visibly empty
  rather than merged into the properties above.
- **Tabs** for the collections that hang off the record: comments, subtasks,
  files for a task; activity and assigned tasks for a bot user. Each tab's
  request waits until that tab is the one on screen, and each collection shows
  a bounded preview that ends in a row handing off to the surface built for the
  long version, filtered to this record — the same move the dashboard's list
  sheet makes.

**The One Address Rule.** A record has exactly one place to be read and acted
on: its panel. Rows carry no menu of their own, and there is no edit screen —
the panel *is* the editor. Reading something must never mean opening four
dialogs in turn, and changing a field must never mean opening a form that
restates the record you are already looking at.

**No overflow menu.** There is no `⋮` anywhere in the product. A menu is what a
surface reaches for when it has not decided where its actions belong, and every
action here has a home: a field is changed in the field, a subtask is added
from the Subtasks tab beneath the subtasks, and delete — the one act with no
field — is a single labelled control at the panel's foot, with no menu to
open first and nothing beside it that a hand reaches for to dismiss.

**State is said, not timestamped.** A record's health is written the way an
operator would say it: "Working", "No token — this bot user cannot reach the
API", "Silent since 9 days ago". An exact moment follows in Ink Muted where it
is worth having, but it never stands alone — a bare timestamp answers a
question nobody asked, and an empty one is indistinguishable from a failed
render. A list of agents carries the same reading, in weight and words rather
than in a colour: teal is for action, location and focus, and nothing else.

**Edit in place, save per field.** Every property is its own control, and each
one saves alone: a select the moment it changes, text when focus leaves it. The
request carries only the field that moved. There is no Save button, so there is
nothing to forget to press and nothing to discard; Escape returns a text field
to its stored value. Success is silent — the value on screen is the receipt —
and only a failure raises a toast.

**Controls rest flat, except where nothing can hover.** A property list rendered
as seven bordered inputs reads as a form to fill in; this is a record to read
that happens to be editable. Each control drops its border and shadow at rest
and takes `bg-accent` on hover, with the focus ring on `:focus-visible` as
everywhere else. Fields the record cannot own — a subtask's project and
schedule, which follow its parent; the Inbox's name, which is fixed — render as
Ink Muted prose saying so, not as a disabled control.

Hover is a pointer's affordance and a thumb has none, so under
`@media (pointer: coarse)` the affordance stops being conditional: every
editable control (`.record-control`) keeps a quiet border and fill at rest, and
a read-only value carries neither. On a touch screen what can be changed is
visible without trying it.

**The Real Address Rule.** The open panel lives in the URL — `?task=<id>`,
`?project=<id>`, `?tag_id=<id>`, `?bot=<id>` — so it can be linked to and Back
closes it. One record is open at a time: opening any of them clears the rest
rather than stacking sheets. Every reference to a record anywhere in
the product — an activity entry, a dashboard row, a breadcrumb — links to that
record, never to the list it lives in. Dropping the reader on an unfiltered
table and leaving them to find the thing again is a broken link that happens to
return 200. The panel fetches by id rather than reading the loaded table, so a
link still opens a record the current filters exclude.

**The Stay-Put Rule.** Opening a record never moves the reader to another
screen. The panel and its parameter belong to the app shell rather than to any
one screen, so the dashboard, the activity log and the project list all open a
task over themselves — a link out of a long log must not cost the reader their
place in it. Links between records therefore target the current route, not a
fixed one.

**Capture is the panel.** A task is created in the same surface it is read in,
one step earlier: the panel opens in a new-record state with one field — the
title — focused, and the project the task will land in named beside it. There
is no create form, because a form would be a second model of a record the panel
already edits, and the reader would have to learn both.

- **Nothing is written until a title is committed.** Opening capture sends no
  request: an empty record would reach the activity log, the REST API a bot
  user reads, and the list, for the cost of an accidental keystroke. Enter
  commits; the modifier chord commits and holds capture open for the next
  thought, so a burst of them costs one gesture each.
- **Escape before the commit cancels silently** — no request, no record, no
  toast. After it, the task exists and dismissal only closes the panel:
  deleting is the control at the panel's foot, never a side effect of leaving.
- **The rest of the record waits for the record.** The new-record state carries
  the title and the destination project, and the properties appear the moment
  there is something to hang them on. Controls that quietly buffer their values
  would be a form with its Save button hidden.
- **One key opens capture from anywhere** in the authenticated app. It stands
  down while a field is being typed into or a dialog, panel or menu is open, so
  it never eats a keystroke meant for something else.

**Keep view state out of the query.** The open panel is view state, not a
filter, so it must be stripped before the search object becomes an API query.
Leaving it in puts it in the query key, and opening a record silently refetches
the list behind the panel and flashes the whole page back to its skeleton.

### Filters
- Closed by default behind a single **Filters** button carrying a count. A
  screen of controls that almost all read "any" is noise, and the shape of the
  bar should not change with how many filters the feature happens to have.
- **Active filters are never hidden.** Each one shows as a removable chip in
  the reader's own words — "Priority: P1", "Not completed" — on a bordered row
  under the bar, with **Clear all** beside them. The count on the button is
  derived from those chips, so it can never disagree with what is on screen.
- One or two filters that are asked for daily may stay out on the bar as
  toggles; sorting stays out too, because it is not a filter and clearing the
  filters must not disturb it.
- Expanded, filters lay out on a labelled grid — 4 columns from `lg`, 2 from
  `sm` — not a wrapping row, so controls line up instead of reflowing into
  ragged groups.

### Empty states
An empty list has two causes and they are never given the same words.
- **Nothing exists yet:** name what the screen is for in one sentence, then
  offer the action that fills it. This is the only documentation most people
  will read about a feature, so it says what the thing *is* — "a bot user lets
  an AI agent work on your tasks through the REST API, only in the projects you
  name" — not "get started".
- **A filter excluded everything:** say so, and offer the undo. Never explain
  the feature here; the reader already has data and knows what the screen does.
- The table decides neither. It takes the state from the caller, because only
  the caller knows which of the two it is.

### Toasts
Popover-coloured, using the system radius, with a dedicated icon per severity
(check-circle, info, triangle-alert, octagon-x, spinner). Severity is carried by
the icon and the copy — the toast body itself does not change colour.

## Do's and Don'ts

### Do:
- **Do** spend Signal Teal on only three things: the primary action, the current
  location, and the focused field. See The One Signal Rule.
- **Do** keep every structural neutral at chroma `0`.
- **Do** separate in-page surfaces with a 1px hairline and a tonal step, and
  reserve shadows for layers that have left the page. See The Left-the-Page Rule.
- **Do** give every bordered container on the page `bg-card`. A bordered box
  left transparent inherits the ground and reads as an outline drawn on
  nothing.
- **Do** hold controls to the 36px height ladder (32 / 36 / 40) so a row of
  mixed buttons, inputs, and selects aligns without adjustment.
- **Do** use 24px between the sections of a route. See The 24-and-Done Rule.
- **Do** render an absent value as italic Ink Muted prose ("No due date"), never
  as an empty cell or an em dash.
- **Do** ship every loading state as a structural skeleton that matches the shape
  of the content it replaces — real column headers, realistic block widths.
- **Do** pair each page title with a one-line Ink Muted subtitle that says what
  the screen is for.
- **Do** define both theme values whenever a colour is added, tuned for equal
  apparent weight rather than equal lightness.
- **Do** give collapsed navigation items tooltips so the icon rail never costs a
  label.

### Don't:
- **Don't** introduce a second accent hue. Status, priority, and category are
  communicated with neutrals and shape.
- **Don't** put a shadow on a table, filter bar, header, sidebar, or content
  container.
- **Don't** reach for the `Card` component. The shipped container vocabulary is
  the bordered table and the bordered filter bar.
- **Don't** use uppercase with letter-spacing for anything but a header over a
  band of rows. See The Uppercase-Header Rule.
- **Don't** use a border wider than 1px. Emphasis changes the border's colour.
  See The One-Pixel Rule.
- **Don't** make a pressable control fully round — pills mean data, not actions.
  See The Pill-Means-Data Rule.
- **Don't** animate hover with lift, scale, or shadow. State changes are colour
  and ring only, at 150ms.
- **Don't** add a font. The system stack carries every role, and that is the
  point of the North Star.
- **Don't** reintroduce the FastAPI artwork in `public/assets/images`. The mark
  is now Taskly's own — the completion check on a Signal Teal tile, drawn inline
  in `Logo.tsx` so it follows the theme's primary token — and it appears on the
  authentication screens only; the app shell leads with the account, not the
  brand.
- **Don't** swap `:focus-visible` for `:focus`. Focus rings appear for keyboard
  navigation, not on every mouse click.
