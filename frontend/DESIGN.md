---
name: Taskly
description: A personal task tracker set as one continuous, well-set log that its owner and their bot users both write.
colors:
  page: "#ffffff"
  raised: "#ffffff"
  hover: "#f3f4f6"
  ink: "#0b0e11"
  ink-2: "#3d444d"
  ink-3: "#656d76"
  rule: "#e6e8eb"
  rule-strong: "#c9cdd2"
  late: "#cf222e"
  done: "#1a7f37"
  priority-p1: "#cf222e"
  priority-p2: "#8a5c00"
  priority-p3: "#0969da"
  scrim: "rgb(0 0 0 / 50%)"
  page-dark: "#0f1115"
  raised-dark: "#171a1f"
  hover-dark: "#1e2228"
  ink-dark: "#e9ecef"
  ink-2-dark: "#c4c9d0"
  ink-3-dark: "#8a8f98"
  rule-dark: "#23272d"
  rule-strong-dark: "#353a42"
  late-dark: "#f0616d"
  done-dark: "#3fb950"
  priority-p1-dark: "#f0616d"
  priority-p2-dark: "#e3a443"
  priority-p3-dark: "#6ea8ff"
  scrim-dark: "rgb(0 0 0 / 80%)"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", \"Noto Sans\", Arial, sans-serif"
    fontSize: "56px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.035em"
    fontFeature: "\"tnum\""
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", \"Noto Sans\", Arial, sans-serif"
    fontSize: "17px"
    fontWeight: 500
    lineHeight: 1
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", \"Noto Sans\", Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 500
    lineHeight: 1.375
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", \"Noto Sans\", Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
  wordmark:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", \"Noto Sans\", Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    letterSpacing: "-0.01em"
  section-heading:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", \"Noto Sans\", Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 600
  meta:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", \"Noto Sans\", Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.25
    fontFeature: "\"tnum\""
  mono:
    fontFamily: "ui-monospace, \"SF Mono\", Menlo, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 400
    fontFeature: "\"tnum\""
  key-cap:
    fontFamily: "ui-monospace, \"SF Mono\", Menlo, Consolas, monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: "16px"
rounded:
  mark: "2px"
  sm: "4px"
  md: "6px"
  lg: "8px"
  full: "9999px"
spacing:
  hairline-gap: "2px"
  meta: "4px"
  line: "10px"
  gutter: "12px"
  page-phone: "16px"
  group: "22px"
  nav-block: "26px"
  indent: "30px"
  lede: "32px"
  section: "36px"
  page-desk: "48px"
components:
  nav-item:
    textColor: "{colors.ink-2}"
    rounded: "{rounded.md}"
    padding: "0 8px"
    height: "30px"
  nav-item-hover:
    backgroundColor: "{colors.hover}"
    textColor: "{colors.ink}"
  nav-item-active:
    textColor: "{colors.ink}"
  nav-count:
    textColor: "{colors.ink-3}"
    typography: "{typography.mono}"
  capture-entry:
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 8px"
    height: "30px"
  key-cap:
    textColor: "{colors.ink-3}"
    typography: "{typography.key-cap}"
    rounded: "{rounded.sm}"
    padding: "0 5px"
  capture-line:
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    height: "40px"
  account-row:
    textColor: "{colors.ink-2}"
    typography: "{typography.meta}"
    rounded: "{rounded.md}"
    padding: "0 8px"
    height: "34px"
  avatar-initial:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.page}"
    rounded: "{rounded.full}"
    size: "20px"
  band-heading:
    textColor: "{colors.ink}"
    typography: "{typography.section-heading}"
    padding: "0 0 8px"
  band-heading-overdue:
    textColor: "{colors.late}"
    typography: "{typography.section-heading}"
  group-label:
    textColor: "{colors.ink-3}"
    typography: "{typography.meta}"
    padding: "0 0 4px 30px"
  task-line:
    textColor: "{colors.ink}"
    typography: "{typography.title}"
    padding: "10px 0"
  task-line-hover:
    backgroundColor: "{colors.hover}"
  meta-line:
    textColor: "{colors.ink-3}"
    typography: "{typography.meta}"
  status-mark:
    textColor: "{colors.ink}"
    size: "18px"
  log-line:
    textColor: "{colors.ink-3}"
    typography: "{typography.body}"
    padding: "8px 0"
  log-line-bot:
    textColor: "{colors.ink}"
  text-link:
    textColor: "{colors.ink-3}"
    typography: "{typography.meta}"
    rounded: "{rounded.sm}"
  close-it:
    textColor: "{colors.done}"
    typography: "{typography.meta}"
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.page}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    height: "36px"
  add-button-phone:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.page}"
    rounded: "{rounded.full}"
    size: "52px"
---

# Design System: Taskly

## Overview

**Creative North Star: "The Changelog"**

Taskly is read the way a project's history is read: one continuous, well-set log on a white page. There are no boxes, no panels and no bezels around the work. Hairline rules and whitespace carry structure; weight and indent carry hierarchy; and every line that records a change names who wrote it, because a person and their bot users act on the same tasks. The register is calm and dense in the way a good release note is dense: everything on the page is a fact, set at a size it can be read at.

The world is near-monochrome by conviction. Ink and two greys do the reading; two strengths of hairline do the dividing. Colour is held back for state that asks the reader to act (a red for what is late or most urgent, a green for what is done or can be closed) and for the two lower priority hues, which only ever colour a status mark. Nothing coloured marks where the reader is: location is said by weight. Controls are text first: a frameless capture line with a hairline beneath it, text links as actions, a small outlined key cap for the shortcut.

The brand is the wordmark "Taskly", set in the interface's own face. The craft bar is Linear. The category's card grids, chip-filled sidebars and coloured location accents were looked at and rejected: Mission Console and Card Box were turned down after mocks for carrying too many frames and too much chrome.

**Transition note.** Redesign slice 1 shipped the shell (navigation, top bar, capture entry, phone Add button), the day page, the task line and the status marks. The task list, the record panels and capture panel, Bots, Activity, settings and the auth screens are not yet redesigned: they still use the stock component kit, and read as the same world only because its semantic colour names (background, foreground, primary, muted, accent, border, input, ring, destructive) are mapped onto this palette. Their framed inputs, outline buttons with a faint shadow, pill badges and table chrome are inherited, not designed, and are not precedent for new surfaces.

**Key Characteristics:**
- One page, one ground: sections are groups under a hairline heading, never framed containers.
- Ink plus two greys for all reading; colour only for state that asks for action.
- The current screen is marked by weight (600), never by a fill or a colour.
- Every log line leads with its actor; bot users' lines are news (ink), the reader's own are reminders (muted).
- The platform UI sans at 15px; monospace only for times, counts, ids and key caps.
- Six stroked status marks, told apart by shape; priority is the mark's colour.

## Colors

A white page with near-black ink, two greys and two hairlines, and four action colours that appear only where something is late, urgent, done or closeable. Every value is written as six-digit hex in `src/index.css` and every text/ground pair is checked to clear 4.5:1 in both themes by `src/theme.test.ts`. Dark values carry the `-dark` suffix here; they live under `.dark` in the stylesheet and mirror the light calibration.

### Primary
- **Ink** (light `ink`, dark `ink-dark`): all primary reading — titles, the day number, headings, bot users' log lines — and also the primary action's fill (the phone Add button, primary buttons), the focus outline and the text link. 19.4:1 on the light page, 15.9:1 on the dark page.

### Secondary
- **Overdue Red** (`late`, `late-dark`): the Overdue band's heading, a missed due day in the meta line (set a weight up), a P1 status mark, and destructive fills. P1 shares it on purpose: urgent and late both ask for action now.
- **Done Green** (`done`, `done-dark`): the filled Done check and the "Close it" action on a Review hand-off. The palette's only green.

### Tertiary
- **Priority Amber** (`priority-p2`, `priority-p2-dark`): a P2 status mark, and nothing else.
- **Priority Blue** (`priority-p3`, `priority-p3-dark`): a P3 status mark, and nothing else. It is never a link colour.

### Neutral
- **Page** (`page`, `page-dark`): the only surface. A sheet is the page itself, held by a hairline.
- **Raised** (`raised`, `raised-dark`): the ground of a popover, menu or dialog. In light it equals the page (the layer lifts by its shadow); in dark it is one step up so it separates without a frame.
- **Hover** (`hover`, `hover-dark`): a hovered navigation item or line, an open menu trigger, and the quiet fill of a secondary control.
- **Ink 2** (`ink-2`, `ink-2-dark`): secondary text — navigation items at rest, the weekday and month beside the day number, the account name, the "nothing here" sentences, the actor in a hand-off line.
- **Ink 3** (`ink-3`, `ink-3-dark`): tertiary text — the meta line, counts, times, group labels, the lede around its emphasised figures, the reader's own log lines, placeholders, key caps. Still clears 4.8:1 on hover in light, 4.9:1 in dark.
- **Rule** (`rule`, `rule-dark`): the hairline between task lines and between log lines.
- **Rule Strong** (`rule-strong`, `rule-strong-dark`): the hairline under a band heading and under the capture line, a key cap's outline, a field's border, the underline of a link inside a sentence. Structure, not text, so neither rule carries a contrast floor.
- **Scrim** (`scrim`, `scrim-dark`): what a modal layer lays over the page; 50% black in light, 80% in dark.

### Named Rules

**The Action-Only Colour Rule.** Colour exists only for state that asks for action: red for overdue and P1, green for done and close, amber and blue only for P2 and P3 status marks. No accent marks location, selection, hover or brand; `theme.test.ts` asserts that no accent hue returns. If a new element wants colour, it must name the action the colour asks for.

**The Priority Hue Rule.** Priority is carried only as the colour of an open task's status mark. P4 and no priority have no hue and stay ink. A closed task's mark is Done Green whatever its priority was.

**The Mirrored Theme Rule.** Every token exists in both themes and every text/ground pair is checked in both. No colour is introduced in one theme alone, and a changed value is not done until `src/theme.test.ts` passes.

## Typography

**Display Font:** the platform UI sans (-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, Noto Sans, Arial, sans-serif)
**Body Font:** the same platform UI sans
**Label/Mono Font:** ui-monospace (SF Mono, Menlo, Consolas, monospace)

**Character:** One face, the one the reader's own system speaks in, so the app reads like a native tool rather than a branded site. Hierarchy comes from size steps and weight, not from a second family; monospace appears only where figures need to line up.

### Hierarchy
- **Display** (700, 56px, line-height 1, -0.035em, tabular figures): the day of the month on the day page. One per screen.
- **Headline** (500, 17px): the weekday, month and year beside the day number, in Ink 2.
- **Title** (500, 15px, line-height 1.375): a task's title in its line; struck through in Ink 3 once done.
- **Body** (400, 15px, line-height 1.45): the default for all text: the lede sentence, log lines, the capture field, empty-state sentences.
- **Section heading** (600, 13px): band headings (Overdue, Due today, In my hands, Changes), each with a mono count beside it and, where useful, a right-aligned Ink 3 note ("assigned to you", the window of the log).
- **Meta** (400 or 500, 13px, line-height 1.25, tabular figures): the meta line, group labels (500, Ink 3), the hand-off line, "N more" links, the account row.
- **Mono** (400, 12px, tabular figures): counts in the navigation and headings, times in the log.
- **Key cap** (400, 11px mono, 16px line): the outlined `C`.
- **Wordmark** (600, 15px, -0.01em): "Taskly" at the head of the navigation and in the phone top bar; 36px on the auth screens.

### Named Rules

**The Mono-Means-Figures Rule.** Monospace is set only for times, counts, ids and key caps. A word in mono is a defect.

**The Weight-Not-Case Rule.** Headings and labels are sentence case and step down by size and weight. No uppercase, no letter-spaced labels, no eyebrow above a heading.

## Layout

The shell is a two-column grid at `md` (768px) and up: a 200px navigation column, sticky to the viewport height, then the work. **No rule divides the navigation from the work; whitespace does.** The navigation column is padded 28px top and left and 20px right; within it, the wordmark, the Add a task entry, the screen list and the account row are spaced 26px apart, and the account row is pushed to the foot. Navigation items are 30px tall, 2px apart.

The main area is padded 48px left and right and 36px on top at desk width; the day page is a single column held to a maximum of 820px. Its rhythm: the capture line, then 36px; the day heading, 6px; the lede, 32px; then bands, each followed by 36px. Inside My work, status groups sit 22px apart, and their labels and "more" links are indented 30px so they align with the task title past its 18px mark and 12px gap. A task line is 10px top and bottom with a 4px gap to its meta line. A log line is 8px top and bottom on a grid of an 8ch time column, a 128px actor column and the sentence; on a phone the sentence drops under the time and actor.

Below `md` the navigation becomes a 56px sticky top bar holding the wordmark and a 44px menu button, which opens the same list in a 264px sheet from the left. The main area is padded 16px at the sides and 20px on top, with 112px clear at the foot so the last line can always be scrolled out from under the floating Add button, which sits 16px from the right and bottom edges (plus the safe-area inset).

Time is shown in the browser's locale on purpose: the log's clock and the day heading follow the reader's own conventions.

### Named Rules

**The No-Frame Rule.** A section is a heading over a hairline and the lines under it. It is never a bordered or filled container, and nothing on the day page sits in a card.

## Elevation & Depth

The page is flat. Lines sit on the page and are separated by hairlines; a hovered line is a tonal step, not a lift. Shadows belong only to what has left the page plane: menus, selects and popovers take a soft medium shadow, dialogs and sheets a deeper one, and the phone Add button floats on its own shadow because it sits over scrolling content. The navigation sheet on a phone is the one sheet with no shadow: it opens over a scrim, which already demotes the page.

### Shadow Vocabulary
- **Floating layer** (`box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)`): menus, selects, popovers.
- **Modal layer** (`box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)`): dialogs and the record sheets.
- **Thumb button** (`box-shadow: 0 6px 16px rgb(0 0 0 / 0.18)`): the phone Add button.

### Named Rules

**The Left-the-Page Rule.** A shadow is permitted only on an element that has left the page plane. Lines, bands, headings, the navigation and the capture line are flat.

**The Scrim Rule.** Anything modal brings the scrim with it, and the page ground must fall at least 0.06 in OKLab lightness under it: 50% black does this in light (0.40), and dark needs 80% (0.076).

## Shapes

Corners are small and quiet: 6px on navigation items, menu triggers and buttons, 4px on key caps and on the focus clearance of text links, 8px as the base radius of the inherited kit. Two things are fully round: the initial avatar and the phone Add button. The project marker in a meta line is an 8px square with a 2px corner, a neutral at 55% of the meta colour. Every border is 1px.

The status marks are the system's signature geometry: drawn on an 18-unit grid with a 1.5 stroke in the current colour.

### Named Rules

**The Six-Mark Rule.** A task's status is one of six 18px stroked marks, told apart by shape alone so they read in greyscale: a dashed ring for Backlog, a solid ring for To do, a half-filled ring for In progress, a dot in a ring for Review, an eye for Waiting, and a filled check for Done. Status is the shape and priority is the colour: an open task's mark takes P1 red, P2 amber or P3 blue, otherwise ink; Done is always the green fill with its check cut out in the page colour; a mark standing for a status alone, as in a menu, is ink. A mark always travels with its label, or with an accessible name stating status and priority. In the task line the mark is itself the control that closes the task.

## Components

### Buttons
- **Shape:** gently rounded (6px).
- **Primary:** ink fill with page-coloured text (19.4:1 light, 15.9:1 dark), 36px tall, 16px side padding.
- **Text actions first:** most actions in this world are not buttons but text links — "N more →", "Restore", "Close it" — at 13px, underlined on hover, with a 3px soft ring on keyboard focus. A link inside a sentence is ink and underlined at rest in Rule Strong, its underline turning full ink on hover; colour never carries a link alone.
- **Close it:** Done Green, 500 weight, inline in the hand-off line; the one coloured action, because closing is the action it asks for.
- **Phone Add button:** a 52px round ink button with a 22px plus, bottom-right, floating on the thumb shadow; hidden at `md` and up, and covered by an open panel's scrim.

### Inputs / Fields
- **Capture line:** frameless and 40px tall: a 16px plus in Ink 3, the field in 15px ink with an Ink 3 placeholder ("Add a task…"), and the `C` key cap at the right end. A 1px Rule Strong hairline sits beneath it and turns ink while the field has focus. The key cap is dropped on coarse pointers, which have no keyboard. Enter creates the task at once and raises a notice with Open and Undo (ADR-0005, amended); the `c` key opens the full draft.
- **Key cap:** 11px mono in a 1px Rule Strong outline, 4px corners, 5px side padding.
- Framed inputs elsewhere are the inherited kit (see the transition note).

### Navigation
- **Style:** a plain text list. The wordmark, then the "Add a task" entry (ink, a 16px Ink 3 plus, the `C` key cap at the right), then the screens — Today, Tasks, Projects, Tags, Bots, Activity, Archive, and Admin for a superuser — each with its count in 12px mono Ink 3 where a count means something.
- **States:** at rest Ink 2; hover is the Hover fill with ink text; **the current screen is ink at 600 weight and nothing else**. Keyboard focus is a 2px ink outline 2px clear of the item, on every item.
- **Account row:** at the foot, 34px: a 20px round ink avatar with the initial in page colour (11px, 600), the name in 13px Ink 2 (the full name, or the email's local part when there is none, so the column never cuts an address mid-domain), and a chevron; it opens the account menu (appearance, log out). Beside it a 30px settings glyph in Ink 3 links to Settings.
- **Phone:** the same list in a sheet from the left behind a 56px top bar with the wordmark and a menu button.

### Task line
The line every slice reuses. The 18px status mark (also the close control), then the title at 15px/500 that opens the task (only the title opens it, never the whole line), and beneath it a 13px Ink 3 meta line: subtask progress as `2/5` with a small tree glyph, the due day, recurrence and tags, each a 13px glyph and its value, with the project at the far right as a neutral square and its name, which truncates first. A missed due day is Overdue Red at 500; today is ink at 500; other days stay quiet. A line with nothing in its meta is one line tall. Lines are divided by a Rule hairline, the last without one; hover lays a Hover tint that fades out toward the right. Tags have a glyph, never a pill.

### Day page
The capture line; the day heading (56px day number, 17px weekday and month beside it); one Ink 3 sentence of real counts with its figures in ink at 500; then the Overdue band (heading in Overdue Red) and the Due today band, each showing up to five lines and ending in an "N more →" link; the rest of the week as a single link. When nothing is overdue or due, the page says so in a sentence instead of drawing an empty band.

### In my hands
The reader's own work, grouped In progress, Review, To do, Waiting, each group under a 13px/500 Ink 3 label indented to the title column. A task handed over in Review carries a hand-off line under its meta: the bot user's name in Ink 2 at 500, when it finished, and "Close it" in green — inline, no dialog.

### Changes
Log lines, newest first: time (12px mono Ink 3) / actor / sentence, the verb lower-cased so it follows its actor. A line a bot user wrote is ink, the actor at 500, because it is news; a line the reader wrote is Ink 3, because it is a reminder. "Restore" sits inline after a deletion it undoes, as an underlined ink link, and asks nothing first.

### Shell behaviour

**The Stay-Put Rule.** Opening a record never moves the reader to another screen. The panel's address belongs to the shell, so every screen opens a task over itself, and capture starts from any of them.

## Do's and Don'ts

### Do:
- **Do** separate groups with a hairline and whitespace: Rule between lines, Rule Strong under a heading, 36px between sections.
- **Do** mark the current place by weight (ink, 600), and only by weight.
- **Do** lead every activity line with its actor, and set bot users' lines in ink and the reader's own in Ink 3.
- **Do** make actions text first: a text link, an inline "Close it", a frameless capture line with its `C` key cap.
- **Do** use the six status marks at 18px for status, with priority as their colour (The Six-Mark Rule).
- **Do** use monospace only for times, counts, ids and key caps, with tabular figures.
- **Do** check every new text/ground pair in both themes in `src/theme.test.ts` before shipping.
- **Do** say an empty state in one sentence instead of drawing an empty container.

### Don't:
- **Don't** colour location, selection, brand or decoration; colour is for overdue, P1, done, close, and the P2/P3 marks only.
- **Don't** put a section, band or list on a card, a filled panel or a bordered box.
- **Don't** draw a rule between the navigation and the work.
- **Don't** set tags or a project as pills in a task line.
- **Don't** use uppercase, letter-spaced labels or eyebrows above headings.
- **Don't** give a shadow to anything that sits on the page.
- **Don't** let colour alone carry a link; inside a sentence it is underlined at rest.
- **Don't** take the inherited kit's framed inputs, outline buttons or pill badges on not-yet-redesigned screens as precedent for new surfaces.
