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
  record-title:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", \"Noto Sans\", Arial, sans-serif"
    fontSize: "22px"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.015em"
  record-line:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", \"Noto Sans\", Arial, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
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
  tab-label:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", \"Noto Sans\", Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 500
rounded:
  mark: "2px"
  sm: "4px"
  md: "6px"
  lg: "8px"
  sheet: "12px"
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
  record-gutter: "36px"
  record-column: "560px"
  property-label: "96px"
  notice-max: "420px"
  page-column: "820px"
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
  capture-line-phone:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    height: "52px"
  capture-create-phone:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.page}"
    rounded: "{rounded.full}"
    size: "32px"
  capture-match:
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    padding: "8px 14px"
  capture-match-selected:
    backgroundColor: "{colors.hover}"
  filter-button:
    textColor: "{colors.ink-3}"
    typography: "{typography.record-line}"
    rounded: "{rounded.md}"
    padding: "0 6px"
    height: "28px"
  filter-button-set:
    textColor: "{colors.ink}"
  filter-button-hover:
    backgroundColor: "{colors.hover}"
    textColor: "{colors.ink}"
  sheet-row:
    textColor: "{colors.ink-2}"
    typography: "{typography.body}"
    padding: "0 16px"
    height: "44px"
  sheet-row-selected:
    textColor: "{colors.ink}"
  assignee-fact:
    textColor: "{colors.ink-3}"
    typography: "{typography.meta}"
    width: "128px"
  assignee-fact-handover:
    textColor: "{colors.ink-2}"
  pager-button:
    textColor: "{colors.ink-3}"
    typography: "{typography.meta}"
  record-column:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    width: "{spacing.record-column}"
    padding: "0 36px"
  record-bar:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink-3}"
    typography: "{typography.meta}"
    height: "52px"
  record-bar-button:
    textColor: "{colors.ink-3}"
    rounded: "{rounded.md}"
    size: "28px"
  record-bar-button-hover:
    backgroundColor: "{colors.hover}"
    textColor: "{colors.ink}"
  record-title:
    textColor: "{colors.ink}"
    typography: "{typography.record-title}"
    padding: "4px 8px"
  property-label:
    textColor: "{colors.ink-3}"
    typography: "{typography.meta}"
    width: "{spacing.property-label}"
    height: "30px"
  property-value:
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 8px"
    height: "30px"
  property-value-hover:
    backgroundColor: "{colors.hover}"
  record-section-heading:
    textColor: "{colors.ink}"
    typography: "{typography.section-heading}"
    padding: "0 0 8px"
  activity-event:
    textColor: "{colors.ink-3}"
    typography: "{typography.record-line}"
    padding: "9px 0"
  activity-time:
    textColor: "{colors.ink-3}"
    typography: "{typography.mono}"
    width: "68px"
  notice:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    typography: "{typography.record-line}"
    rounded: "{rounded.lg}"
    padding: "8px 40px 8px 14px"
    width: "{spacing.notice-max}"
  notice-action:
    textColor: "{colors.ink}"
    typography: "{typography.record-line}"
  notice-close:
    textColor: "{colors.ink-3}"
    rounded: "{rounded.md}"
    size: "24px"
  notice-close-hover:
    backgroundColor: "{colors.hover}"
    textColor: "{colors.ink}"
  top-bar:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    height: "44px"
  tab-bar:
    backgroundColor: "{colors.page}"
    height: "56px"
  tab-item:
    textColor: "{colors.ink-3}"
    typography: "{typography.tab-label}"
  tab-item-current:
    textColor: "{colors.ink}"
  tab-add:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.page}"
    rounded: "{rounded.full}"
    size: "40px"
  account-button-phone:
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    size: "44px"
  capture-sheet:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sheet}"
    padding: "10px 16px 0"
  filter-button-coarse:
    textColor: "{colors.ink-3}"
    typography: "{typography.record-line}"
    rounded: "{rounded.md}"
    padding: "0 6px"
    height: "44px"
  bot-plate:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.page}"
    rounded: "{rounded.md}"
    size: "26px"
  bot-plate-off:
    backgroundColor: "{colors.rule-strong}"
    textColor: "{colors.ink-2}"
  bot-line:
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    padding: "10px 0"
  bot-line-meta:
    textColor: "{colors.ink-3}"
    typography: "{typography.meta}"
  webhook-url:
    textColor: "{colors.ink}"
    typography: "{typography.mono}"
---

# Design System: Taskly

## Overview

**Creative North Star: "The Changelog"**

Taskly is read the way a project's history is read: one continuous, well-set log on a white page. There are no boxes, no panels and no bezels around the work. Hairline rules and whitespace carry structure; weight and indent carry hierarchy; and every line that records a change names who wrote it, because a person and their bot users act on the same tasks. The register is calm and dense in the way a good release note is dense: everything on the page is a fact, set at a size it can be read at.

The world is near-monochrome by conviction. Ink and two greys do the reading; two strengths of hairline do the dividing. Colour is held back for state that asks the reader to act (a red for what is late or most urgent, a green for what is done or can be closed) and for the two lower priority hues, which only ever colour a status mark and the Priority row of a task's property list. Nothing coloured marks where the reader is: location is said by weight. Controls are text first: a frameless capture line with a hairline beneath it, text links as actions, a small outlined key cap for the shortcut.

The brand is the wordmark "Taskly", set in the interface's own face. The craft bar is Linear. The category's card grids, chip-filled sidebars and coloured location accents were looked at and rejected: Mission Console and Card Box were turned down after mocks for carrying too many frames and too much chrome.

**Transition note.** Redesign slice 1 shipped the shell (navigation, top bar), the day page, the task line and the status marks. Slice 2 shipped the record column the shell holds for every record, the task panel and its capture draft, the capture line's create-at-once behaviour, and the notices at the top. Slice 3 shipped the task list (the Tasks page: its filter row, order menu, pager and empty states), the capture line's match search and the assignee on the task line. Slice 4 shipped the Bots page and the bot user's column (its token, scope, webhooks, the one-time secret reveal, its work and its log), the Activity page as day groups of lines, the phone navigation (a tab bar of five, an account menu in the top bar, and a capture sheet raised by the add control, which replaced the capture line pinned to the bottom), and the filter row as one shared piece used by the Tasks and Activity pages. The Projects, Tags, Archive and Admin screens, settings and the auth screens are not yet redesigned: they still use the stock component kit (`DataTable` remains only on the archive, Projects, Tags and Admin; the Bots and Activity tables are gone), and read as the same world only because its semantic colour names (background, foreground, primary, muted, accent, border, input, ring, destructive) are mapped onto this palette. Their framed inputs, outline buttons with a faint shadow, pill badges and table chrome are inherited, not designed, and are not precedent for new surfaces. The same is true of a few pieces inside the redesigned screens: the dialogs (the webhook confirmations, the secret reveal, Restore's confirmation), the webhook URL field and its ghost buttons, and the Create and issue token button are the inherited kit set on this palette.

**Key Characteristics:**
- One page, one ground: sections are groups under a hairline heading, never framed containers.
- Ink plus two greys for all reading; colour only for state that asks for action.
- The current screen is marked by weight (600), never by a fill or a colour.
- Every log line leads with its actor; bot users' lines are news (ink), the reader's own are reminders (muted).
- The platform UI sans at 15px; monospace only for times, counts, ids, URLs, secrets and key caps.
- Six stroked status marks, told apart by shape; priority is the mark's colour, and the Priority row's.
- A record opens in a column beside the page, not over it: no scrim, no focus trap, the page stays live.
- A list is lines only, and its filters are quiet text on one hairline: a set one is said in ink, never hidden behind a closed control.
- On a phone the thumb's controls come to the bottom: a tab bar of five, a capture sheet raised by its add control, and menus as sheets with 44px rows.
- A bot user is read in words, as a line and as a column: its token, its reach and its webhooks are sentences and plain state, never badges.

## Colors

A white page with near-black ink, two greys and two hairlines, and four action colours that appear only where something is late, urgent, done or closeable. Every value is written as six-digit hex in `src/index.css` and every text/ground pair is checked to clear 4.5:1 in both themes by `src/theme.test.ts`. Dark values carry the `-dark` suffix here; they live under `.dark` in the stylesheet and mirror the light calibration.

### Primary
- **Ink** (light `ink`, dark `ink-dark`): all primary reading — titles, the day number, headings, bot users' log lines — and also the primary action's fill (primary buttons, the add control's disc in a phone's tab bar, the round Create button in the capture sheet, a sheet's Done), the focus outline and the text link. 19.4:1 on the light page, 15.9:1 on the dark page.

### Secondary
- **Overdue Red** (`late`, `late-dark`): the Overdue band's heading, a missed due day in the meta line (set a weight up), a P1 status mark, the flag and label of a P1 Priority row, an error notice's icon, a bot user's expired token, its "last delivery failed" and a failed webhook delivery, a webhook field's refusal, and destructive fills. P1 shares it on purpose: urgent and late both ask for action now.
- **Done Green** (`done`, `done-dark`): the filled Done check and the "Close it" action on a Review hand-off. A success notice's icon. The palette's only green.

### Tertiary
- **Priority Amber** (`priority-p2`, `priority-p2-dark`): a P2 status mark and the flag and label of a P2 Priority row, and nothing else.
- **Priority Blue** (`priority-p3`, `priority-p3-dark`): a P3 status mark and the flag and label of a P3 Priority row, and nothing else. It is never a link colour.

### Neutral
- **Page** (`page`, `page-dark`): the only surface. A sheet is the page itself, held by a hairline.
- **Raised** (`raised`, `raised-dark`): the ground of a popover, menu or dialog. In light it equals the page (the layer lifts by its shadow); in dark it is one step up so it separates without a frame.
- **Hover** (`hover`, `hover-dark`): a hovered navigation item or line, a hovered filter button, the highlighted match in the capture line's popup, the line open in the record column (as the row tint), a hovered property value, a hovered bar or notice control, an open menu trigger, and the quiet fill of a secondary control.
- **Ink 2** (`ink-2`, `ink-2-dark`): secondary text — navigation items at rest, the weekday and month beside the day number, the account name, the "nothing here" sentences, the actor in a hand-off line, the "bot user → you" assignee of a Review hand-over in the meta line, the unchosen rows of a sheet.
- **Ink 3** (`ink-3`, `ink-3-dark`): tertiary text — the meta line, counts, times, group labels, the lede around its emphasised figures, the reader's own log lines, placeholders, key caps. Still clears 4.8:1 on hover in light, 4.9:1 in dark.
- **Rule** (`rule`, `rule-dark`): the hairline between task lines, between log lines, and between the subtask, file and activity lines of a record.
- **Rule Strong** (`rule-strong`, `rule-strong-dark`): the hairline under a band heading and under the capture line, the top edge of a phone's tab bar, a sheet's grabber, the dashed outline of a read-only permission, the record column's left edge, a notice's border, the hairline above a record's property list and under each of its section headings, a key cap's outline, a field's border, the underline of a link inside a sentence. Structure, not text, so neither rule carries a contrast floor.
- **Scrim** (`scrim`, `scrim-dark`): what a modal layer lays over the page; 50% black in light, 80% in dark.

### Named Rules

**The Action-Only Colour Rule.** Colour exists only for state that asks for action: red for overdue and P1, green for done and close, amber and blue only for P2 and P3 status marks and Priority rows; the one place green and red mark severity is the icon of a notice, and only the icon. No accent marks location, selection, hover or brand; `theme.test.ts` asserts that no accent hue returns. If a new element wants colour, it must name the action the colour asks for.

**The Priority Hue Rule.** Priority hue lives on two things only: an open task's status mark, and the flag and label of the Priority row in a task's property list (the choices in that row's menu carry their flag in the same hue, so the colour is learnt where it is set). P1 is Overdue Red, P2 Priority Amber, P3 Priority Blue: the same values and the same contrast as on the mark, red 5.4 / 4.9, amber 5.8 / 5.3 and blue 5.2 / 4.7 on the light page / hover, and in dark red 6.0 / 5.0, amber 8.7 / 7.3 and blue 7.8 / 6.6. In the row the label is set at 500 beside a filled 14px flag. P4 is the flag and label in ink; no priority is the words "No priority" in Ink 3 with no flag. A closed task's mark is Done Green whatever its priority was. Nowhere else: not a pill, not a line, not a column.

**The Mirrored Theme Rule.** Every token exists in both themes and every text/ground pair is checked in both. No colour is introduced in one theme alone, and a changed value is not done until `src/theme.test.ts` passes.

## Typography

**Display Font:** the platform UI sans (-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, Noto Sans, Arial, sans-serif)
**Body Font:** the same platform UI sans
**Label/Mono Font:** ui-monospace (SF Mono, Menlo, Consolas, monospace)

**Character:** One face, the one the reader's own system speaks in, so the app reads like a native tool rather than a branded site. Hierarchy comes from size steps and weight, not from a second family; monospace appears only where figures, addresses and secrets need to line up or be copied.

### Hierarchy
- **Display** (700, 56px, line-height 1, -0.035em, tabular figures): the day of the month on the day page. One per screen.
- **Headline** (500, 17px): the weekday, month and year beside the day number, in Ink 2.
- **Title** (500, 15px, line-height 1.375): a task's title in its line; struck through in Ink 3 once done.
- **Body** (400, 15px, line-height 1.45): the default for all text: the lede sentence, log lines, the capture field, empty-state sentences.
- **Section heading** (600, 13px): band headings (Overdue, Due today, In my hands, Changes), the group headings of the Bots page (Bot users, Deleted) and of the Activity page (a day's name), and a record's section headings (Description, Subtasks, Files, Activity, and a bot user's Projects, Permissions, Webhooks, On its plate), each with a mono count beside it and, where useful, a right-aligned Ink 3 note ("assigned to you", the window of the log).
- **Meta** (400 or 500, 13px, line-height 1.25, tabular figures): the meta line, group labels (500, Ink 3), the hand-off line, "N more" links, the account row.
- **Record title** (600, 22px, line-height 1.25, -0.015em): a task's title at the head of its panel, wrapping rather than scrolling.
- **Record line** (400, 13.5px): an event one-liner in a record's activity, and the text of a notice and its actions (500). Day separators, the small fact at the right of a subtask line and the Edit and Delete actions under a comment are 12.5px.
- **Mono** (400, 12px, tabular figures): counts in the navigation and headings, times in the log and in a record's activity, the "3 of 12" in the column bar; a webhook's URL (12.5px) and a secret or token in its reveal (12px, 16px on a phone).
- **Key cap** (400, 11px mono, 16px line): the outlined `C`, and the outlined `⌘ Enter` or `Ctrl Enter` under a comment.
- **Tab label** (500, 11px, 600 for the current tab): the word under each icon in a phone's tab bar.
- **Wordmark** (600, 15px, -0.01em): "Taskly" at the head of the navigation and in the phone top bar; 36px on the auth screens.

### Named Rules

**The Mono-Means-Figures Rule.** Monospace is set only for what a reader compares character by character or copies: times, counts, key caps, and ids, URLs and secrets. A word, a name or a sentence in mono is a defect.

**The Weight-Not-Case Rule.** Headings and labels are sentence case and step down by size and weight. No uppercase, no letter-spaced labels, no eyebrow above a heading.

## Layout

The shell is a two-column grid at `md` (768px) and up: a 200px navigation column, sticky to the viewport height, then the work. **No rule divides the navigation from the work; whitespace does.** The navigation column is padded 28px top and left and 20px right; within it, the wordmark, the screen list and the account row are spaced 26px apart, and the account row is pushed to the foot. Navigation items are 30px tall, 2px apart.

The main area is padded 48px left and right and 36px on top at desk width; the day page and the Tasks page are each a single column held to a maximum of 820px (`page-column`). Its rhythm: the capture line, then 36px; the day heading, 6px; the lede, 32px; then bands, each followed by 36px. Inside My work, status groups sit 22px apart, and their labels and "more" links are indented 30px so they align with the task title past its 18px mark and 12px gap. A task line is 10px top and bottom with a 4px gap to its meta line. A log line on the day page is 8px top and bottom on a grid of an 8ch time column, a 128px actor column and the sentence; on a phone the sentence drops under the time and actor.

Below `md` the navigation becomes two bars. A 44px sticky top bar (the page ground over a Rule hairline) holds the wordmark and, at the right, the account control. A 56px tab bar is fixed to the foot of the screen, with the home-indicator inset below it (see Navigation). The main area is padded 16px at the sides and 20px on top, with 80px clear at the foot, plus the inset (96px from `md` up), so the last line can always be scrolled out from under the tab bar.

**The Tasks page.** Its rhythm: the capture line (28px below it; only from `md` up, a phone's page has none), the "Tasks" heading (22px/600, -0.015em, 4px beneath), the counts sentence (20px beneath), the filter row over a Rule Strong hairline (10px under the buttons), then the lines, then the pager line 14px under the last. Lines run to the column's edges, divided by Rule, the last without one; an empty state is a sentence block on a Rule hairline with 32px above and below.

**The Activity page.** One column held to 820px: the "Activity" heading (22px/600, -0.015em, 4px beneath), the counts sentence (20px beneath), the filter row, the day groups, then the pager line 14px under the last line, 18px between its count and its buttons. A day group opens 22px above its heading, which sits 6px over its Rule Strong hairline; a line is 9px top and bottom.

**The Bots page.** One column held to 760px: the "Bots" heading (22px/600) with "+ New bot user" at the right of the same line, baseline-aligned (the heading row sits 4px above what follows), the counts sentence (24px beneath), then the "Bot users" group and, 28px below it, the "Deleted" group, each a heading with a mono count over a Rule Strong hairline and then lines. A bot line is 10px top and bottom on a grid of a 26px plate, the text and the last-use column, 12px apart.

**The record column.** A record opens in a third track of the shell grid (200px navigation, the work, then the column), which is no width at all while empty. From 1200px the column is 560px wide with a 1px Rule Strong hairline on its left, sticky to the full viewport height and scrolling on its own, and the work beside it narrows its side padding from 48px to 32px. Below 1200px, where there is no room for the navigation, a 560px column and a page that can still be read, the column is fixed over the whole screen. Its side gutter is 36px beside the page and 16px on a phone (`record-gutter`; the class is `gutter` in `RecordPanel.tsx`, not the 12px `gutter` spacing token above), and the bar, the title, the property list and every section start on that one edge. The bar is 52px tall from 1200px and 56px below it. Inside, the rhythm is: bar; title row (8px above, 18px below); property list (a hairline above, 10px, rows 2px apart, 14px below); then sections, each 18px below the one above and 4px under its last line; delete at the foot. Controls grow to 44px under a coarse pointer, and rows with them.

Time is shown in the browser's locale on purpose: the log's clock and the day heading follow the reader's own conventions.

### Named Rules

**The No-Frame Rule.** A section is a heading over a hairline and the lines under it. It is never a bordered or filled container, and nothing on the day page or in a record's column sits in a card.

## Elevation & Depth

The page is flat. Lines sit on the page and are separated by hairlines; a hovered line is a tonal step, not a lift. Shadows belong only to what has left the page plane: menus, selects and popovers take a soft medium shadow, dialogs a deeper one, and a notice a long soft one for the height it has gained. A phone's tab bar casts none: it is held by a Rule Strong hairline across its top, and the main area keeps clear of it. The sheets of a phone (the capture sheet and the filter sheets) cast none either (`shadow-none`): they rise over a scrim, which already demotes the page, on the page ground with a hairline at the top. Nor does the record column: beside the page it is a hairline-edged part of the shell, and below 1200px it covers the whole screen, so there is no page left for it to lift from.

### Shadow Vocabulary
- **Floating layer** (`box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)`): menus, selects, popovers, the phone account menu, and the capture line's matches popup off a phone.
- **Modal layer** (`box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)`): dialogs, the secret reveal among them.
- **Notice** (light `box-shadow: 0 10px 24px -8px rgb(0 0 0 / 0.25), 0 2px 6px rgb(0 0 0 / 0.08)`; dark `box-shadow: 0 10px 24px -8px rgb(0 0 0 / 0.7), 0 2px 6px rgb(0 0 0 / 0.4)`): a notice at the top of the screen, which has a page ground and no scrim. These three are the whole vocabulary; the dark notice shadow is denser because a dark ground has less to lose.

### Named Rules

**The Left-the-Page Rule.** A shadow is permitted only on an element that has left the page plane. Lines, bands, headings, the navigation, the tab bar, the filter row and the capture line are flat; the bottom sheets of a phone rise on the scrim and carry no shadow.

**The Scrim Rule.** Anything modal brings the scrim with it (the record column and a notice are not modal and bring none), and the page ground must fall at least 0.06 in OKLab lightness under it: 50% black does this in light (0.40), and dark needs 80% (0.076).

## Shapes

Corners are small and quiet: 6px on navigation items, menu triggers and buttons, 4px on key caps and on the focus clearance of text links, 8px as the base radius of the inherited kit and the corner of a notice, 6px on the record column's bar controls and property values. Four things are fully round: the initial avatar, the 40px add disc of the tab bar, the 32px Create button in the capture sheet, and the × that drops a set filter. A bottom sheet has 12px corners at the top only (the capture sheet and the filter sheets alike), with a 36px by 4px Rule Strong grabber at the top of the capture sheet. A bot user's plate is a 26px square with 6px corners (28px at the head of its column); a permission that no setting is behind is drawn as a 16px box with 4px corners and a dashed Rule Strong outline. The project marker in a meta line is an 8px square with a 2px corner, a neutral at 55% of the meta colour. Every border is 1px.

The status marks are the system's signature geometry: drawn on an 18-unit grid with a 1.5 stroke in the current colour.

### Named Rules

**The Six-Mark Rule.** A task's status is one of six 18px stroked marks, told apart by shape alone so they read in greyscale: a dashed ring for Backlog, a solid ring for To do, a half-filled ring for In progress, a dot in a ring for Review, an eye for Waiting, and a filled check for Done. Status is the shape and priority is the colour: an open task's mark takes P1 red, P2 amber or P3 blue, otherwise ink; Done is always the green fill with its check cut out in the page colour; a mark standing for a status alone, as in a menu, is ink. A mark always travels with its label, or with an accessible name stating status and priority. In the task line the mark is itself the control that closes the task.

## Components

### Buttons
- **Shape:** gently rounded (6px).
- **Primary:** ink fill with page-coloured text (19.4:1 light, 15.9:1 dark), 36px tall, 16px side padding.
- **Text actions first:** most actions in this world are not buttons but text links — "N more →", "Restore", "Close it" — at 13px, underlined on hover, with a 3px soft ring on keyboard focus. A link inside a sentence is ink and underlined at rest in Rule Strong, its underline turning full ink on hover; colour never carries a link alone.
- **Webhook actions:** "Set a URL", "Send a test", "Change" and "Clear" are flat text buttons at 13px/500 in Ink 2, turning ink on hover (Clear turns Overdue Red), 32px tall and 44px under a coarse pointer; "Regenerate secret" sits at the Webhooks heading in 13px Ink 3. They are the inherited ghost button set to this size.
- **Close it:** Done Green, 500 weight, inline in the hand-off line; the one coloured action, because closing is the action it asks for.
- **Add (phone):** the middle cell of the tab bar: a 40px round ink disc with a page-coloured plus (22px, 2 stroke), in a target as tall as the bar. It is the one way a phone starts a task from any screen, and it raises the capture sheet.
- **Create (phone):** inside the capture sheet's line, once a title is typed: a 32px round ink disc with an up arrow, in a 44px target. It does not take focus from the field, so the keyboard stays up.
- **Done (sheet):** a full-width 44px ink button at the foot of a sheet that is used more than once (More filters).
- **Pager:** on the Tasks page "Previous" and "Next" (on the Activity page "Newer" and "Older" with an arrow each, the words following the order) as 13px Ink 3 text links, turning ink on hover and focus, at 40% opacity and inert at the ends. Under a coarse pointer each grows to a 44px-tall target (14px vertical and 8px side padding, pulled back by a negative margin so nothing on the line moves).

### Inputs / Fields
- **Capture line:** frameless and 40px tall: a 16px plus in Ink 3, the field in 15px ink with an Ink 3 placeholder ("Add a task…"), and the `C` key cap at the right end. A 1px Rule Strong hairline sits beneath it and turns ink while the field has focus. The key cap is dropped on coarse pointers, which have no keyboard. A phone's pages carry no line; its capture sheet carries it (see Capture line). Enter creates the task at once and raises a notice with Open and Undo (ADR-0005, amended); the `c` key opens the full draft.
- **Key cap:** 11px mono in a 1px Rule Strong outline, 4px corners, 5px side padding.
- **Webhook URL field:** the inherited framed input, 36px tall, its text in mono (12.5px; 16px on a phone, where a smaller field is zoomed), placeholder "https://". A refusal is said under the field in 12.5px Overdue Red as an alert, the field marked invalid and described by it, and what was typed is kept for correcting.
- Framed inputs elsewhere are the inherited kit (see the transition note).

### Navigation
- **Style:** a plain text list. The wordmark, then the screens — Today, Tasks, Projects, Tags, Bots, Activity, Archive, and Admin for a superuser — each with its count in 12px mono Ink 3 where a count means something.
- **States:** at rest Ink 2; hover is the Hover fill with ink text; **the current screen is ink at 600 weight and nothing else**. Keyboard focus is a 2px ink outline 2px clear of the item, on every item.
- **Account row:** at the foot, 34px: a 20px round ink avatar with the initial in page colour (11px, 600), the name in 13px Ink 2 (the full name, or the email's local part when there is none, so the column never cuts an address mid-domain), and a chevron; it opens the account menu (appearance, log out). Beside it a 30px settings glyph in Ink 3 links to Settings.
- **Phone tab bar:** below `md` the list is replaced by a `nav` named Main, fixed to the foot: 56px plus the home-indicator inset, on the page ground over a Rule Strong hairline. Five equal cells: Today, Tasks, the add control, Bots, Activity. A tab is a 22px stroked icon (1.6 stroke) over its word at 11px/500 in Ink 3, 3px apart; the current tab is ink at 600, stated to a screen reader as the current page, and marked by weight and ink alone, never a fill. Today is current only on the day page itself; Tasks stays current on every address under it. Focus is the navigation's ink outline drawn inward (4px inside the cell) so the cell does not clip it. The middle cell is the add control: a button named "Add a task" that says it opens a dialog and whether it is open, wearing the 40px ink disc. The bar is hidden while a record's full-screen column covers the phone. Projects, Tags, Archive, Settings and Admin are not tabs; they are behind the account control.
- **Phone account control:** at the right of the 44px top bar (pulled 8px past the gutter), a 44px target holding a 26px ink disc with the initial (12px/600, page colour), named "Account"; open or hovered it takes the Hover fill. It opens a menu on the Floating layer, right-aligned, at least 224px wide, rows at least 44px tall: the name at 500 with the email beneath it in muted 12px when there is a name; Projects, Tags, Archive, Settings, and Admin for a superuser (each a link); Appearance with Light, Dark and System as radio items; and Log out.

### Task line
The line every slice reuses. The 18px status mark (also the close control), then the title at 15px/500 that opens the task (only the title opens it, never the whole line), and beneath it a 13px Ink 3 meta line: subtask progress as `2/5` with a small tree glyph, the due day, recurrence and tags, each a 13px glyph and its value, then whose task it is (below), with the project at the far right as a neutral square and its name, which truncates first (at most half the line, 64px at least). A missed due day is Overdue Red at 500; today is ink at 500; other days stay quiet. A line with neither facts nor a project is one line tall; where the project is known, as on the Tasks page always, it is two. Lines are divided by a Rule hairline, the last without one; hover lays a Hover tint that fades out toward the right. Tags have a glyph, never a pill.

**The assignee.** Whose the task is, said in words alone, with no glyph: "you" for the reader, the bot user's name for a task a bot user holds, and nothing when it is unassigned. A task the reader holds in Review because a bot user handed it over reads "bot user → you" (the bot user's real name, then an arrow and "you"), the one fact set in Ink 2 instead of Ink 3 because it asks something of the reader. It sits after due day, recurrence and tags and before the project. A screen reader hears "Assigned to:" or, for a hand-over, "Handed over by:" before it. Below 640px the name is capped at 128px (256px from `sm`) and truncates before the arrow and before the project; the arrow and "you" never truncate. A deleted bot user is still named. A subtask under its root in the Tasks page's tree is indented 30px (20px more per level below) with a small corner branch in Rule Strong in place of the subtask glyph; outside a tree a subtask line carries the glyph.

### Day page
The capture line; the day heading (56px day number, 17px weekday and month beside it); one Ink 3 sentence of real counts with its figures in ink at 500; then the Overdue band (heading in Overdue Red) and the Due today band, each showing up to five lines and ending in an "N more →" link; the rest of the week as a single link. When nothing is overdue or due, the page says so in a sentence instead of drawing an empty band.

### In my hands
The reader's own work, grouped In progress, Review, To do, Waiting, each group under a 13px/500 Ink 3 label indented to the title column. A task handed over in Review carries a hand-off line under its meta: the bot user's name in Ink 2 at 500, when it finished, and "Close it" in green — inline, no dialog.

### Changes
Log lines, newest first: time (12px mono Ink 3) / actor / sentence, the verb lower-cased so it follows its actor. A line a bot user wrote is ink, the actor at 500, because it is news; a line the reader wrote is Ink 3, because it is a reminder. "Restore" sits inline after a deletion it undoes, as an underlined ink link, and asks nothing first. The Activity page is the long version of this log (see Activity page).

### Tasks page
The whole of the reader's open work as one view of lines, paged and ordered by the server. From the top: the capture line; the "Tasks" heading (22px/600); one sentence of counts; the filter row; the lines; the pager line. It is one column held to 820px, with no table, no selection and no bulk controls: a change to many tasks at once is a bot user's, through the REST API.
- **Counts sentence:** Ink 3 at body size, 20px under the heading. The lead, "N open.", is ink at 500; after it, in Ink 3, come "N in Backlog", "N on bot users" ("1 on a bot user") and "N overdue", joined by commas and ended with a full stop, a zero left out. With nothing open it is "Nothing is open." alone. The figures are the whole of the reader's open work, not what the filters have narrowed it to, and the sentence waits for all four counts (a skeleton of its height) so it never changes length under the filters; if one cannot be had it is left out and the list speaks for itself.
- **Lines:** only task lines, 25 to a page, newest filed first with each subtask drawn under its root task (indented, with a branch mark). Choosing an order makes the list flat: every task at its own place. Loading is skeleton lines of the same two-line shape. The list is a real list, named "Tasks". The open line is tinted (the open line tint).
- **Pager line:** 14px under the last line, 13px Ink 3: "N tasks" ("1 task"), with " · page 2 of 4" only past one page, announced politely as it changes, and Previous and Next at the right, 14px apart. Absent when there are no tasks. Any change to the filters returns to page one, and a page that no longer exists is left for the last one.
- **Empty states:** a sentence block on a Rule hairline, 32px above and below, a title at 500 and one Ink 3 sentence under it, at most a readable line wide. Four are told apart: "No tasks match these filters" (with a "clear them all" link), "Nothing left open" (everything is done; the finished work is in the activity log, linked), "No tasks yet" (how to begin: type in the Add a task line, or let a bot user file them; with a link to set one up), and the failed fetch, "The tasks could not be loaded", with "Nothing is lost. Try again" (the retry as an underlined ink text button). The failed fetch is an alert, never mistaken for an empty account.

### Filter row
Shared: `Common/FilterRow.tsx` holds the pieces (`Filter`, `ChoiceFilter`, `PickSheet`, `SheetOption`, and `OrderMenu`), and the Tasks page and the Activity page build their rows from them, so a filter, a phone sheet and an order menu behave alike on both. One line of quiet text buttons over a Rule Strong hairline (10px beneath), 13.5px, wrapping onto a second line when it must, in a `fieldset` named Filters. On the Tasks page Project, Assignee and Status always show; Priority, Tag and Time follow on a wide screen; "Created by" appears only while a link has set it. On the Activity page there are two: the kind of change and the actor. The order menu is at the far right of both.
- **A filter at rest:** an Ink 3 text button, 28px tall (44px under a coarse pointer), 6px corners, with its "Any …" name ("Any project", "Anyone", "Any status"; on the log "Anything that happened", "By anyone") and a 10px chevron. Hover and an open menu lay the Hover fill and ink text. Focus is the navigation's own 2px ink outline, 2px clear.
- **A filter that is set:** its value replaces the "Any …" text, in ink at 500, with an × beside it (a 14px round control that drops the filter, with its hit area grown past the mark by 14px under a coarse pointer). The text button and the × are one pill, and the Hover fill covers both. A set filter is always on the row: a list cannot be narrowed by a control that is not seen.
- **Clear:** a text button after the filters, only while any is set. It drops every filter and leaves the order alone. Filters combine with AND, and each lives in the URL.
- **Order menu (shared):** at the right, a button saying the order in force with a chevron, named "Order: …". On a wide screen it opens a radio menu aligned to its right edge (the Floating layer); on a phone, a sheet titled "Order". It acts on selection, not on a change of the group's value, so choosing the order in force again still reaches the page. The Tasks page offers Newest first, Due date, Priority and Filed, and choosing the one in force reverses it ("Newest first", "Due soonest first", "Priority, P1 first", "Filed, oldest first" and their reverses); its row says "Choose again to reverse" in 12px Ink 3. The Activity page offers Newest first and Oldest first, with no reversing hint.
- **Wide screens:** each filter opens a menu of radio items with "any" first (the Floating layer); on the Tasks page Time is a 256px popover holding an Overdue check and Due from and Due to day fields. Done is not a choice there: the list holds open work.
- **Phone:** each menu is a bottom sheet instead (`PickSheet`), rising on the scrim, 12px corners at the top, no shadow, the page ground, at most 85% of the viewport, with its title at 15px/500 and rows 44px tall (`SheetOption`, 15px; the chosen one in ink at 500 with a check, the rest Ink 2; "any" first), and the safe-area inset below. Choosing a row closes the sheet. The Tasks row keeps Project, Assignee and Status, and a **More** button; behind it one sheet, "More filters", folds Priority, Tag (or "No tags yet") and Time, each under a 12.5px Ink 3 heading, closed by a full-width 44px ink Done. A set folded filter stays on the row in ink with its ×, and tapping it opens that same sheet. The Activity row has nothing to fold.

### Activity page
The whole log as lines under day groups, paged by the server (50 a page) and ordered by the reader. It shows only the reader's own account. From the top: the "Activity" heading (22px/600), one sentence of counts, the filter row, the day groups, the pager line.
- **Counts sentence:** Ink 3 at body size. The lead, "Every change in your account, newest first." ("oldest first" once turned around), is ink at 500; after it, "N entries, M of them by your bot users." ("all by your bot users", "none of them by your bot users", "by one of your bot users"), or "Nothing has happened yet." It counts the whole log whatever the filters say; a count that cannot be had is left out.
- **Filters:** the kind (Completed, Created, Changed, Deleted & restored, Comments & files, Tags) and the actor (You, each live bot user, and each deleted one with "deleted" after its name in Ink 3). A set actor reads "By you" or "By <name>". Clear drops both and leaves the order alone. Any change returns to page one.
- **Day group:** a heading at 13px/600 over a Rule Strong hairline, with the mono count of the lines on this page; the day is named as a record's activity names it ("Today", "Yesterday", then the date).
- **Line:** 9px top and bottom over a Rule hairline, on a grid of a 4.25rem time column, a 136px actor column, the sentence, and Restore at the right, 12px apart. The time is 12px mono Ink 3, tabular and never wrapping, with the full date and time on hover. The sentence follows its actor, so its verb is lower-cased. On a phone the grid is two columns: time and actor on the first line, the sentence and Restore beneath, under the actor.
- **Whose line:** a bot user's line is ink (the actor's name at 500 and the sentence), because it is news; the reader's own is Ink 3 with "You" as the actor, because it is a reminder. The actor is named in words, with no glyph and no badge; a screen reader hears ", bot user" after it. A bot user's name is a link that opens its column beside the log (The Stay-Put Rule).
- **Struck names:** the name of a task, project or tag that is gone is Ink 3 and struck through, still said and no longer a link; a deleted bot user's name as the actor is struck through and stays a link to its read-only column.
- **Restore:** here it asks first. It is the same underlined ink text button, but it opens a dialog ("Restore task" or "Restore project") that says what comes back with it, such as the subtasks or tasks deleted along with it, and that comments and attachments come back too, with Cancel and Restore.
- **Pager line:** 14px under the last line, 13px Ink 3: "N entries" ("1 entry"), with " · page 2 of 4" only past one page, announced politely, and at the right "← Newer" and "Older →", 14px apart; the words follow the order rather than the direction, so with the oldest first the pair reads "← Older" and "Newer →". The buttons are hidden when there is one page, at 40% opacity and inert at the ends, 44px targets under a coarse pointer.
- **Empty and failed:** an empty log is one Ink 3 sentence on a Rule hairline, 32px above and below, in the words of what it was narrowed to ("Nothing has been completed yet.", "This bot user has not changed anything yet.", "You have not changed anything yet."). A failed fetch is an alert, "The activity could not be loaded" with "Nothing is lost. Try again". Loading is a skeleton day heading and six skeleton lines of the same grid.

### Bots page
The bot users as lines, and the sentence of counts above them. From the top: the "Bots" heading (22px/600) with "+ New bot user" at its right, the counts sentence, the "Bot users" group, then a "Deleted" group.
- **New bot user:** a text link at 13.5px/500 in Ink 2, turning ink and underlined on hover, a plus in front of the words, a thumb-sized target under a coarse pointer. It opens the draft in the record column.
- **Counts sentence:** Ink 3 at body size. The lead, "N bot users." ("1 bot user."), is ink at 500; after it "N working", "N without a token" and "N with an expired token", joined by commas, then "They made N changes this week." ("It made no changes this week." for one). The changes half is left out when the log cannot be counted. With none live it says "No bot users right now. Deleted ones are kept below."
- **Groups:** each a 13px/600 heading over a Rule Strong hairline with a mono count, then the lines, the list named for its group. "Deleted" is quiet: a bot user that was deleted is kept so that what it did still names it, and it sits 28px below the live ones.
- **Empty and loading:** "No bot users yet" at 500, then one Ink 3 sentence saying what a bot user is for, on a Rule hairline with 32px above and below. Loading is a skeleton sentence and three skeleton lines of the line's shape; the page is drawn once every request has come.

### Bot line
A bot user as a line, with no table behind it and no card around it. A grid of a 26px plate, the text, and a last-use column, 12px apart, 10px top and bottom, divided by a Rule hairline, the last without one; hover and the open line take the row tint.
- **Plate:** two letters on a 26px square with 6px corners (the first letters of the name's first two words, else the name's first two letters), 11px/600, decorative: ink with page-coloured letters while the token works, a Rule Strong fill with Ink 2 letters when it does not, so a list says which are alive before a word is read.
- **Name:** at 500, and it is the link that opens the column (only the name, as only a task's title opens a task), underlined on hover, truncating; Ink 3 for a deleted bot user.
- **Meta line:** 13px Ink 3, 4px under the name, wrapping, its items 12px apart. First the token as a 7px dot and a word: a filled dot and "Working" in Ink 2 at 500 while it works, a hollow Ink 3 ring and "No token", "Revoked" or "Expired" otherwise. Then, in words, the projects it reaches by name ("no projects"; "(archived)" after an archived one), what it may do as verbs ("reads, updates, comments", or "no permissions"), and the webhooks set ("task webhook set", "comment webhook set", "both webhooks set", nothing when neither). Only when the last delivery of either webhook failed, "last delivery failed" follows in Overdue Red at 500. A screen reader hears "Projects:" and "Permissions:" before their words.
- **Last use:** "used 3 hours ago", "used just now", "used yesterday" or "never used", 13px Ink 3, at the right and never wrapping from `sm` up; on a phone, where a column would take a third of the line, it is the last item of the meta line instead.
- **Deleted:** in the Deleted group the line has no dot, projects or permissions: "deleted 12 Sept" and "still named on 3 tasks and in the log" ("still named in the log" for none). The name is Ink 3; there is no last-use column.
- **Colour carried by the build:** the token dot and the word "Working" are Done Green, as are "Working" in the column's Token row and the verdict "Delivered" on a webhook. That is a use of the colour outside done and close, so it stands outside The Action-Only Colour Rule and is not precedent for new surfaces.

### Bot user's column
A bot user opens in the record column as one document, with no tabs: the name in place, a property list, then sections under hairline headings, as a task's column reads. Every change saves as it is made and there is no Save, except in the draft, which has one Create.
- **Bar and head:** the bar says "Bot user · created 24.09.2026" ("Bot user · Deleted · created …" once deleted; "New bot user · Not saved yet" for a draft). Under it a 28px plate and the name as a 22px/600 flat field, saved on Enter or leaving it; a deleted bot user's name is plain text.
- **Deleted bot user:** read-only. A sentence in Ink 3 under the name says deleting cannot be undone, its token stopped at once, it takes no new tasks, and what it did and was assigned still names it. It has no Token row, no Projects or Permissions sections and no Delete foot; Webhooks, On its plate and Activity remain.
- **Property list:** Token, Last used and Reach. Token says its state in words with the action beside it: "Working" (Done Green at 500) with "expires 12 Oct" or "never expires" in Ink 2; "Expired" (Overdue Red at 500) or "Revoked" (ink at 500) with "its requests are refused"; "No token" with "it cannot reach the API"; then Revoke or Issue token, each behind its own dialog. Last used is "3 hours ago" with the full date and time, or "Never used". Reach is one sentence of projects and verbs, "Website relaunch · reads, updates".
- **Projects:** a section with the count "2 of 5": checkboxes in as many columns as fit at 200px each, 16px apart, each row 30px tall (44px coarse). A project made later is never added by itself; an archived project is offered only while it is already in the scope, marked "(archived)", so it can be taken out. A hint at 12.5px in Ink 3 says a bot user reaches only the projects ticked here and never an archived one; with none to offer it says "No projects to grant yet".
- **Permissions:** the same grid, one checkbox per grant with a 12px Ink 3 note, then the rows no setting is behind, read-only in Ink 3 and drawn with a dashed 16px box, so the list reads as the whole of it. Ticking saves at once; a refused save puts the box back and a notice says why.
- **On its plate:** a section with a count of the open tasks assigned to it, up to five as task lines (highest priority first, each with the project), then "All its tasks →" to the Tasks page narrowed to it. Empty, it says no open tasks are assigned and how to assign one.
- **Activity:** a section with a count and up to five of its latest lines under a 12.5px Ink 3 day name, each a 4.25rem mono time column and a 14px Ink 2 sentence, 8px top and bottom over a Rule hairline, then "Everything it did →" to the Activity page narrowed to it. Both sections say a failed fetch as an alert sentence with Try again, and load as three skeleton bars.
- **Draft:** the same column before the bot user exists. The plate follows the name as it is typed and stays grey until there is one; the name field says "Name the bot user". The Token row holds the optional expiry, a day field named "Expires on" (not before today) with a 12.5px hint that it works until revoked when left empty. Projects and Permissions are as above, with reading tasks ticked to start. The foot is pinned to the column's bottom on the page ground over a Rule Strong hairline: "Its token is shown once, right after." at 12px Ink 3 and the primary button "Create and issue token" (44px coarse); Enter in the name does the same. The bot user and its token are made in one step and the secret reveal opens over the column; should issuing fail, the bot user stands and a notice says why.
- **Delete:** the column's destructive text button at its foot, as for any record.

### Webhooks
A section of a bot user's column, "Webhooks", with "Regenerate secret" at the right of its heading while a secret exists and the bot user is live. Two rows, "Task ready" and "Comment", each a 96px label column (13px Ink 3) and its content, 10px top and bottom over a Rule hairline.
- **URL:** set in mono at 12.5px in ink, breaking anywhere so a long address never widens the column. Unset, the row says "Not set ·" and, in Ink 3, what that means for the bot user.
- **Last delivery:** under a set URL, 12.5px Ink 3, announced politely because a test changes it under the reader's eyes: a verdict word at 500, "Delivered" in Done Green, "Failed" or "Failed, retrying" in Overdue Red, then the facts joined by " · ": "test" when the event was one, when ("today 07:41", "yesterday 18:02", else the day), what came back (the server's words or the status, "in 120 ms", "under 1 ms" or "in 1.2 s"), and, while retrying, "attempt 2" and "next try today 07:56". Before any, "No delivery yet".
- **Actions:** below, as flat text: "Set a URL" when unset; "Send a test" (which says "Sending…" while it is on its way), "Change" and "Clear" when set. Change and Set a URL open the URL field in place with Save and Cancel; Escape forgets the edit and leaves the column open. A refusal is answered in the field (see Inputs / Fields), a failure to reach the server in a notice.
- **Confirmation:** Clear and Regenerate secret each ask first in a dialog that says what is lost before the button: Clear that waiting deliveries are discarded and, when it is the last webhook, the secret too; Regenerate that a receiver still checking the old secret will refuse the next deliveries. Cancel and the action ("Clear webhook" in the destructive fill, "Regenerate").
- **Foot sentence:** 12.5px Ink 3: the first URL set makes the secret, which signs every delivery and is shown once; once set, that every delivery is signed with it; for a deleted bot user, that webhooks were cleared and nothing is sent. A deleted bot user's section is read-only, with no actions.

### Secret reveal
The one place a value that can never be read again is on screen: a bot user's token, and a webhook secret. Both share one dialog (`SecretDialog`), held above the panels so that a refetch cannot take it away. It is a dialog on the Modal layer with the scrim, 512px at most, and has no corner control.
- **Content:** the title ("Token for <name>", "Webhook secret for <name>"), a sentence on what it is for, an alert in the destructive variant ("Copy the token now. It won't be shown again, and it cannot be retrieved later."), the value in a read-only mono field (12px; 16px on a phone) that selects its text on focus, beside a Copy button that reads Copied, and for a token one line on when it expires or "It works until you revoke it." Then a checkbox, "I have stored this token somewhere safe", and Done, which stays disabled until it is ticked.
- **A second step:** if the value was never copied, Done first swaps the foot for a destructive alert (the token cannot be shown again and the bot user needs a new one; for a secret, you would have to regenerate it) with "Back to the token" and "Close without copying".

**The Shown-Once Rule.** A value that cannot be read back is shown in a dialog that Escape and a click outside leave open; while the box is unticked a muted line says it stays open until the value is stored. Leaving takes an explicit word that it is stored and, if it was never copied, a second deliberate step.

### Record column
A task, project, tag or bot user opens in a column beside the page, not a sheet over it (The Stay-Put Rule). It is an `aside` named for the record, on the page ground with a Rule Strong hairline at its left. The page beside it stays live, with **no scrim and no focus trap**, so a reader can open the next line without closing anything. Opening puts focus on the column itself, not on its first field, and Tab starts from there; closing returns focus to the line that opened it, unless the reader has put it somewhere of their own. Escape closes it (a field on the page beside it keeps its own Escape); ↓ and ↑ walk the list it was opened from when focus is not in a text field, a select or an open menu. Geometry is in Layout: 560px from 1200px, the whole screen below it.

- **Bar:** 52px (56px below 1200px), sticky, on the page ground. At the left, the record's context in 13px Ink 3, truncating: for a task, the project in Ink 2 at 500, the parent task as a text link after a chevron when there is one, then "opened by you, 24.09.2026" or by the bot user that filed it; for a draft, "New task · Not saved yet". At the right, never moving: "3 of 12" in 12px mono Ink 3, previous and next (chevrons), and close. Each control is a 28px square (44px coarse) with a 6px corner in Ink 3, tinted Hover with ink on hover, with a 3px soft ring on focus; at the end of the list a walking control drops to 40% opacity and says so without taking focus away.
- **Title row:** the status mark at 22px, which is the control that closes the task, then the title at 22px/600 in a field that wraps and is flat until reached for; Enter saves it. A draft has no mark.
- **Delete:** the one destructive control, a text button saying its word, at the foot of the column under a Rule Strong hairline, as far from the close control as the column allows.
- **Failure and loading:** a missing or unavailable record says so in a sentence with Try again and Close; loading is three grey skeleton bars.

### Property list
The record read, and editable. A Rule Strong hairline above, rows 2px apart, each a grid of a label column (96px; 88px on a phone) and the value, 16px apart. The label is 13px Ink 3 and is the `label` of its value, 30px tall (44px coarse), so a single-line row is centred; a value that wraps keeps its label on the first line. Rows, in order: Status (a record only, its mark in the priority hue), Project, Due, Priority, Assignee, Tags, Repeat, and Created (read-only, with its reporter).
- **Value:** a text button, 30px tall (44px coarse), 15px, flat at rest: no border, no fill, no shadow. Hover lays the Hover tint; focus draws a ring-coloured border. The `quiet` margin (-8px) pulls the text onto the label column's edge, so the tint reaches past the text and the text does not move. Its 12px chevron shows only on hover, focus or while open, and always, at 60% opacity, under a coarse pointer, which has no hover.
- **`ghost` and `quiet`:** `ghost` is a text field that is flat until reached for (description, title, repeat interval); `quiet` is the same for a select's trigger. Both carry `record-control`, which under a coarse pointer gives an editable value a Rule Strong border and a faint Hover fill so it is told from a read-only value. A read-only value never carries it and is said in words in Ink 3, never drawn as a disabled control.
- **Priority row:** the flag and label in the priority's hue (The Priority Hue Rule).
- **Draft:** the same rows without Status and Created, held until the task is created.

### Record section
`RecordSection`: a named region at the column's gutter, 18px below the one above. Its heading is 13px/600 over a Rule Strong hairline, with a 12px mono Ink 3 count after it and, at the right, the section's own action as a 13px Ink 3 text link that turns ink and underlined on hover. The task's sections are:
- **Description:** the description as a flat 15px Ink 2 field, "Add a description".
- **Subtasks:** the count is done over total (`2/5`). One line per child, 36px at least: an 18px mark that closes it, its title that opens it at 14px/500 (struck through and Ink 3 once done), and one quiet 12.5px fact at the right, the due day in Overdue Red when missed, else the bot user it is with. The list ends with an empty ring and "Add a subtask…": Enter creates the child there and keeps the field.
- **Files:** a count, "Attach a file" as the action, one hairline-divided line per file.
- **Activity:** the chronology below.

Lines in a section are divided by Rule, never boxed.

### Activity chronology
One chronology in a record, oldest first, with the composer at its end. Days are separated by a 12.5px Ink 3 line, not a rule. Each moment is a row of a 4.25rem time column (12px mono Ink 3, tabular) and the content, 12px apart, 9px above and below, divided by a Rule hairline.
- **Event:** a muted one-liner at 13.5px Ink 3 that starts with the actor (Ink 2, 500), the verb after it.
- **Comment:** the author on a line of their own (a bot user's name as a link with "bot user" beside it at 12px, or "You" in Ink 3), then the body at 15px Ink 2. The reader's own comment shows Edit and Delete at 12.5px below it, only on hover or keyboard focus within the row and always under a coarse pointer; a bot user's comment has neither. Editing is a 6px-cornered field with Save and Cancel as text; ⌘ or Ctrl Enter saves.
- **Composer:** frameless, under a Rule Strong hairline that takes the focus colour on focus: a "Write a comment…" field, then a line with the key cap `⌘ Enter` or `Ctrl Enter` and "to post" at the left (dropped on coarse pointers) and "Comment" as an ink 500 text action at the right. The draft is kept per task.
- "Show earlier activity" is a text link above the first day; an empty history is one sentence.

### Open line tint
`row-tint`: the Hover ground as a left-to-right gradient that fades out over the last 15% of the row (`linear-gradient(to right, var(--hover), transparent 85%)`). One utility for a hovered task line, a hovered bot line, and the line that is open in the record column, so the reader sees which line the column belongs to without any colour or mark and a list line and a table row cannot drift apart. A task line and a bot line take it on hover and when open; a row of the inherited table (Projects, Tags, Admin and Archive) takes the plain muted fill on hover and, as `row-tint`, when open.

### Capture line
The frameless line is the whole of quick capture: a 16px plus (1.5 stroke) in Ink 3, the field (15px ink), and the `C` key cap (dropped on coarse pointers), 40px tall over a Rule Strong hairline that turns ink on focus. The placeholder says where the task goes: "Add a task…", and "Add a task to <project>…" on a page narrowed to a project; Enter writes the task at once into that project, else the Inbox, and raises a notice; the line empties for the next thought. From `md` up the day page and the Tasks page both carry it at their head (`PageCaptureLine` mounts it only off a phone); a phone's pages have none, and its capture sheet carries the same line. The full draft opens in the record column from the `c` key, or from "More options…" in the capture sheet: the title row, the property rows, a Description section, and a foot pinned to the column's bottom with "Create task" (the ordinary primary button) and the chord that creates and starts another.

- **The capture sheet (below 768px):** the tab bar's add control raises a bottom sheet from any screen, over the scrim: the page ground with a hairline at its top, 12px corners at the top only, no shadow (`shadow-none`), 16px side padding and 10px above, a 36px by 4px Rule Strong grabber at the top, and the home-indicator inset below unless a keyboard covers it. It is a dialog named "Add a task". It follows the visual viewport: `useVisualViewport` writes `--kb-inset` (how far the seen bottom sits above the layout bottom, the keyboard's height while one is up) and `--vv-height` (the seen height) onto the sheet's own element and nowhere else, so the sheet sits at `bottom: var(--kb-inset)` and is no taller than what is seen, riding above the browser's bar and the keyboard. It is followed for as long as the sheet is in the page, its closing animation included, so it never drops to the bottom edge while a keyboard is still going down.
- **In the sheet:** the line is 52px tall with no hairline beneath, its field 16px (iOS zooms the page in to any smaller one), and the round Create button appears inside it once a title is typed. Matches stand in the flow above the line rather than floating, up to the seen height less 9.5rem and scrolling inside that, each match a row at least 44px tall over a Rule hairline, with no key hints. A foot line under it, at least 44px, says what Return will do in 12px Ink 3 ("Return creates “title” in <project>", or "Goes to <project>" while empty) and, at the right, "More options…" as a 13.5px/500 ink text button, underlined on hover, in a 44px target: it carries the typed title over to the full draft, empties the sheet and closes it.
- **Keys and focus:** Return creates; a tap on a match opens that task. Escape closes the matches first when they are open, and then the sheet; a tap outside closes it too. Either keeps what was typed, since the sheet is mounted once and holds the words while it is closed. Having made a task or opened a match, the sheet closes by itself, since its scrim would hold the notice's Open and Undo out of reach. Closing returns focus to the add control, named in code because a tap does not focus a button on iOS. A phone turned to a wide screen loses the control, and the sheet closes.
- **Matches:** from two characters (the trimmed text), after a 200ms pause, the line offers the open tasks whose title contains the text, up to eight. Off a phone they are a popup under the line: the page ground, a Rule Strong hairline, 8px corners, the Floating layer shadow. The first line is a 12.5px Ink 3 heading ("Open tasks matching “text”", or "No open task has “text” in its title"). Each match is the task line in miniature: the status mark, the title at 500 with the matched text in bold, and the project in 12.5px Ink 3 (at the right on a wide screen, after the title in the sheet). The popup's footer, under a Rule hairline, says "↵ creates “title” in <project>" and, with key caps, "↑ ↓ then ↵ opens a match" (a coarse pointer reads "Return creates…" and "Tap a match to open it"). The popup opens toward the side with room, decided as it appears, never between keystrokes.
- **Semantics and keys:** the field is a combobox over a listbox, so a screen reader hears the count of matches and which is chosen. Typing goes on; Enter still creates. ↓ and ↑ walk the matches (passing through the line itself, where Enter creates again), the highlighted match takes the Hover ground, and Enter then opens it in the record column. Escape closes the popup and keeps the text, and the record column does not hear it; the popup stays closed until the text changes.

### Notices
A notice is a line of the log that has left the page: the page ground with a Rule Strong hairline, an 8px corner, the Notice shadow, and text actions. There is one Toaster for the whole app, so every notice, including those raised from a record column (which is no modal and leaves them in reach), appears in one place.
- **Position and size:** top-centre, 12px below the top edge plus the safe-area inset; 420px at most, and on a phone the full width between 16px gutters.
- **Content:** 13.5px ink text with a 16px icon. **Severity is the icon's colour only**: Done Green for success, Overdue Red for error, otherwise the notice's own ink; never a filled ground.
- **Actions:** text, not buttons: ink, 13.5px/500, underlined on hover ("Open", "Undo"); 44px tall under a coarse pointer.
- **Close:** a quiet 24px control inside the notice at its right (Ink 3, Hover tint, 44px coarse), never sonner's chip hanging off the corner.

### Shell behaviour

**The Stay-Put Rule.** Opening a record never moves the reader to another screen. The panel's address belongs to the shell, so every screen opens a task beside itself, and capture starts from any of them.

## Do's and Don'ts

### Do:
- **Do** separate groups with a hairline and whitespace: Rule between lines, Rule Strong under a heading, 36px between sections.
- **Do** mark the current place by weight (ink, 600), and only by weight.
- **Do** lead every activity line with its actor, and set bot users' lines in ink and the reader's own in Ink 3.
- **Do** make actions text first: a text link, an inline "Close it", a frameless capture line with its `C` key cap.
- **Do** use the six status marks at 18px for status (22px as the title row's closing control), with priority as their colour (The Six-Mark Rule).
- **Do** keep a record's controls flat at rest, tint them Hover on reach, grow them to 44px under a coarse pointer, and start every edge of the column on the one gutter (36px, 16px on a phone).
- **Do** open records in the column beside the page with no scrim and no focus trap, and raise every notice at the top with text actions and severity as the icon's colour.
- **Do** show the line that is open with the `row-tint` ground, in lists and tables alike.
- **Do** use monospace only for times, counts, key caps, ids, URLs and secrets, with tabular figures, and never for a word.
- **Do** check every new text/ground pair in both themes in `src/theme.test.ts` before shipping.
- **Do** say an empty state in one sentence instead of drawing an empty container, and say a failed fetch as its own state with a retry, never as an empty one.
- **Do** keep a list to lines only: Rule between them, no table, no selection, filters as quiet text on one Rule Strong hairline, and a set filter said in ink with its ×, always on the row.
- **Do** move a thumb's controls to the bottom on a phone: the tab bar and the capture sheet, the sheet following the visual viewport, and menus as bottom sheets with 44px rows.
- **Do** say whose a task is in words in the meta line, after due day, recurrence and tags and before the project, with the hand-over in Ink 2.
- **Do** say a bot user's state in words on its line and in its column (token, reach, webhooks), and answer a refused address in the field it concerns.
- **Do** say what is lost before the button of an irreversible step, and show a value that cannot be read back once, in a dialog that Escape and an outside click leave open.
- **Do** grow a text control's target under a coarse pointer without moving anything on the line, as the pager and the × do.

### Don't:
- **Don't** colour location, selection, brand or decoration; colour is for overdue, P1, done, close, the P2/P3 marks, the Priority row, and the icon of a success or error notice only.
- **Don't** put a section, band or list on a card, a filled panel or a bordered box.
- **Don't** draw a rule between the navigation and the work.
- **Don't** set tags or a project as pills in a task line.
- **Don't** use uppercase, letter-spaced labels or eyebrows above headings.
- **Don't** give a shadow to anything that sits on the page, the record column included.
- **Don't** show priority in colour as a pill, a line or a column: its hue is the status mark's and the Priority row's.
- **Don't** fill a notice with severity colour, or hang its close control off the corner.
- **Don't** let colour alone carry a link; inside a sentence it is underlined at rest.
- **Don't** add a floating button or a navigation entry for a new task: the `c` key opens the full draft on a keyboard, and on a phone the one add control in the tab bar raises the capture sheet.
- **Don't** set a word, a name or a sentence in monospace: URLs, secrets and ids are the addresses a reader copies, not text to be read.
- **Don't** hide a set filter behind a closed control or a fold: it stays on the row.
- **Don't** take the inherited kit's framed inputs, outline buttons or pill badges on not-yet-redesigned screens as precedent for new surfaces.
