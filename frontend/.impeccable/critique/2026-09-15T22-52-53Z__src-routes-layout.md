---
target: frontend app (src/routes/_layout)
total_score: 22
max_score: 40
na_heuristics:
p0_count: 2
p1_count: 3
target_identity: "file:/Users/semaputnikov/Documents/Projects/taskly/frontend/src/routes/_layout"
timestamp: 2026-09-15T22-52-53Z
slug: src-routes-layout
---
Method: dual-agent (A: design review, isolated; B: detector + browser evidence, isolated). Browser evidence gathered twice by independent engines: headless Chromium (B) and the connected Chrome extension (A, on a second pass after the extension was set up). Dev database at review time: 21 tasks, 1 project, active bot users.

Surface: `frontend/src/routes/_layout`. Mode: Operate.

## Design Health Score — 22/40 · Acceptable

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of System Status | 2 | The `/archive` skeleton re-labels 2 of 6 column headers mid-load and the table jumps 228px upward. Task completion has no optimistic update: the checkbox disables, waits a round trip, and the row vanishes silently. |
| 2 | Match System / Real World | 3 | Domain vocabulary is excellent (bot user, scope, occurrence). The template's voice punches through: "Something went wrong!", "N/A", an unreachable "Someone else" in the log. |
| 3 | User Control and Freedom | 2 | Deleting a comment or an attachment is one click, no confirm, no undo. The delete-task dialog never mentions that deletion is reversible from the activity log. |
| 4 | Consistency and Standards | 2 | Three pagination vocabularies, four dialog widths, four date formats on one screen, `⋮` banned on tasks and shipped on projects, tags and bots. |
| 5 | Error Prevention | 2 | Delete sits 4px from close, and the close target is 16x16 against a 36x36 delete. The one-time token dialog dismisses on Esc with no guard. |
| 6 | Recognition Rather Than Recall | 3 | The active-filter chip row is the best thing in the product. Against it: column headers are not sortable and sort hides in a select at the far right. |
| 7 | Flexibility and Efficiency | 1 | The only global keyboard shortcut in the app is the sidebar toggle. No capture shortcut, no multi-select, no bulk actions, no column sorting. |
| 8 | Aesthetic and Minimalist Design | 2 | The Add Task dialog is taller than the viewport and cannot scroll; the mobile table hides 38% of every row. Minimalism failing at its job. |
| 9 | Error Recovery | 2 | Every failure is headed "Something went wrong!" with the real message demoted. Login enforces `min(8)` client-side, so a short legacy password never reaches the server. |
| 10 | Help and Documentation | 3 | Empty states carry real teaching. But `/bots`, whose entire purpose is a REST API, links to no docs, no base URL, no example request. |
| **Total** | | **22/40** | **Acceptable — significant improvements needed** |

## Design Specificity Verdict

Two products wearing one skin. The task surface is genuinely authored; everything else is shadcn admin boilerplate with Taskly copy pasted over it. Roughly 60% authored / 40% category default — and the 40% includes the primary capture action and the first screen a stranger meets.

Authored: the activity log inverts emphasis so an entry a *bot* wrote gets `font-medium` and your own is muted (`WhileYouWereAway.tsx:96-110`); the detail panel as the record's one address via `?task=<id>`, carried by the dashboard and the activity log alike; fields a subtask cannot own rendering as prose rather than disabled controls (`TaskProperties.tsx:218,264`).

Category default: the Add Task dialog is an eight-field CRUD modal described as "Fill in the form below to add a new task."; `/settings` and `/admin` are untouched template; five routes still title themselves "FastAPI Template" and four of the five are unauthenticated.

Deterministic scan: the detector covered all 133 files under `src` and returned exactly ONE finding, advisory — `design-system-font-size`, `text-[10px]` on the sidebar avatar (`User.tsx:74`), off the DESIGN.md type ramp. No false positives; nothing suppressed (no `.impeccable/config.json`, no `impeccable-disable` anywhere). Statically the code is near-spotless, which is why everything material below was only findable in pixels.

Browser overlay: 7-11 findings per view. Several are DESIGN.md-sanctioned false positives (`cramped-padding` on the table container, `nested-cards` on `thead.bg-muted/50` and the dashboard band headers, `text-overflow` on the truncating sidebar name). `low-contrast` and `skipped-heading` are sanctioned nowhere.

## Overall Impression

A well-considered system with unusually good documentation that breaks exactly where nobody measured it. The console is spotless: zero errors, zero React warnings, zero failed requests across seven routes in two themes and two viewports. No horizontal overflow anywhere. And yet the system's only accent colour fails WCAG, its most-used dialog does not fit a laptop screen, and its signature table hides a third of every row on a phone. The single biggest opportunity: stop treating the desktop mouse as the only scene — three of the five priority issues dissolve with that assumption.

## What's Working

1. **The active-filter chip row, and specifically where its count comes from.** `TaskFilters.tsx:155-202` builds one array of `{label, clear}` objects and derives the button badge from `chips.length`. The count *cannot* disagree with what is on screen, because it is not computed from schema keys. Each chip's `clear` is a change, not a key, which is why dropping "Overdue" correctly restores completion too.
2. **Edit-in-place with per-field saves and Escape-to-revert.** `TaskProperties.tsx:76-145` — `EditableText` re-syncs from the server *unless the reader currently holds the value* (`if (!editing) setDraft(value)`). That one condition makes the pattern safe in a product where a bot can edit the same record while you are typing in it.
3. **Reserved trailing columns on the dashboard — confirmed in pixels.** Priority badges sit at identical x in the Overdue and Due-today groups, on desktop and at 390px, and the 80px "days late" column stays reserved and empty rather than collapsing. Nothing shifts between bands.

## Priority Issues

### [P0] The Add Task dialog is taller than the screen it ships on, and cannot scroll
At a 666px viewport the dialog measures 756-784px. The title "Add Task" sits at `top: -20..-34px`, entirely off-screen; the first visible line is "Fill in the form below to add a new task." The Save button measured `bottom: 700px` — below the fold. `overflow-y: visible`, `max-height: none`, `scrollHeight === clientHeight`: the dialog cannot scroll, and `body { overflow: hidden }` means the page cannot either. A programmatic `scrollBy(0,500)` moves it 0px. Verified on screenshot.
**Why it matters:** fixed 756px height clips on any usable height below ~760px — 1440x900, 1280x800, 1366x768, i.e. essentially every laptop. This is the product's most frequent action and it physically does not fit the device it is used on.
**Fix:** reduce default capture to one field (title + submit) with everything else behind a "More options" disclosure in the same dialog; global shortcut to open; `max-h-[calc(100dvh-4rem)]` + `overflow-y-auto` on the content as a backstop; relabel "Save" to "Add task"; make Description a Textarea to match the panel.
**Command:** `/impeccable distill`

### [P0] Deleting a comment or an attachment takes one click, with no confirmation and no undo
`TaskComments.tsx:146-155` and `TaskAttachments.tsx:120-129` fire `deleteMutation.mutate(...)` straight from a ghost Trash2 icon.
**Why it matters:** these are the two data types in Taskly with no soft-delete and no restore path. The delete icon sits 4px from Download on attachment rows; at 390px those are two 36px targets one careless tap apart. The product confirms revoking a token, which is recoverable, and does not confirm this, which is not.
**Fix:** for attachments, the same Dialog used by DeleteTag/DeleteBotUser, naming the filename. For comments, optimistic removal plus a 6-second sonner toast with Undo. Separate Download from Delete.
**Command:** `/impeccable harden`

### [P1] Signal Teal — the system's only accent — fails WCAG AA in both themes
Measured independently by both engines, numbers agree: light `rgb(0,148,133)` under `oklch(0.985)` 14px/500 = **3.61:1**; dark `rgb(39,164,149)` = **2.95:1**. Needs 4.5. This is the only contrast failure in dark mode and one of two in light. It affects every primary button in the product.
**Why it matters:** the mechanism is a direct consequence of a Named Rule. The Mirrored Theme Rule lifts the teal in dark "so it keeps the same apparent weight", but the label stays pinned at `oklch(0.985)`. Lifting the fill while holding the text drives contrast DOWN, 3.61 -> 2.95. The rule optimises the fill against the page and ignores the text on top of it. This is a design-system defect, not an implementation one — DESIGN.md must change too.
**Fix:** darken the fill (~`oklch(0.52)` light, `oklch(0.55)` dark reaches 4.5:1 against near-white), or keep the fill and let On Signal go to pure white, which the doc currently forbids. Also: the light-theme page subtitle is 4.35:1 and appears on every route.
**Command:** `/impeccable colorize`

### [P1] The delete control is 4px from close, and the two targets are inverted by risk
Measured on the open panel, identical in both themes and viewports: Delete task 36x36 centred (1386,24); Close X **16x16** centred (1416,24). Edge-to-edge gap exactly 4 CSS px.
**Why it matters:** the source read understated this. The close target is below the WCAG 2.2 AA 24x24 minimum and far below the 44px touch guideline, while the irreversible control beside it is more than five times its area. The safe, frequent action got the small target. On open, Radix focuses close, drawing a ring 4px from delete.
**Fix:** move Delete out of the close corner — bottom of the properties section, or the far left of the header row. Raise the close target to at least 24x24, 44 on mobile. Add to the dialog: "Deleted tasks are recorded in your activity log and can be restored from there."
**Command:** `/impeccable layout`

### [P1] The Tasks table — "the signature component of the system" — fails at both ends
*Mobile:* at 500px the table is `clientWidth 450` / `scrollWidth 721` — 271px, 38% of every row, off-screen. Tags and Priority are entirely hidden and the header is clipped mid-word ("DUE" without "DATE"). No fade, no shadow, no arrow, no visible scrollbar: the table appears simply to end. Verified on screenshot.
*Code:* `tasks.tsx:39` requests `limit: 100` and paginates that window client-side while the footer prints `data.length` as the total. At 340 tasks a user sees "of 100" and ten pages. Sorting is server-side, so it sorts the first 100 rows the server returned and the most overdue task may never appear. Latent today — the dev DB holds 21 tasks and the footer honestly reads "of 21" — but the defect is real.
**Why it matters:** the dashboard handles 390px gracefully while the table degrades into a horizontal strip with no affordance. On a phone the dashboard is currently the better task surface and the Tasks page is close to unusable.
**Fix:** server-side pagination as `/activity` already does — `page` in the search schema, `skip`/`limit` through, render the real `count` the API already returns, delete the client-side `rowPaginationFeature`. On mobile either a card row layout below `md` or an explicit scroll affordance.
**Command:** `/impeccable adapt`

## Persona Red Flags

**Alex (impatient power user).** No capture shortcut; the only global binding is the sidebar toggle. `Cmd+Enter` is unbound; plain Enter works unless focus is in `TagsField`, which swallows it (`TagsField.tsx:68-72`). Clicking the "Due date" column header does nothing — headers are not sortable; sort lives in a `w-36` select at the far right, and the direction button is `disabled` until a sort is chosen, so it leaves the tab order and is undiscoverable. No multi-select or bulk edit anywhere: reprioritising four tasks is four panel opens.

**Sam (screen reader / keyboard-only).** No skip link — every page entry means tabbing past the account trigger, Activity, the collapse toggle, Add Task and 6-7 nav items. Table rows are not keyboard-operable: `DataTable.tsx:99-112` puts `onClick` on a bare `<tr>` with no `tabIndex`, no `role="button"`, no `onKeyDown`, so the primary interaction of the primary screen is mouse-only. Filter changes are announced to nobody — zero matches for `aria-live` or `role="status"` in the codebase. On mobile `/tasks` there are zero visible links at all. The account menu nests a `DropdownMenuItem` (`role="menuitem"`) inside an `<a>`.

**Casey (mobile, one-handed).** The detail panel covers 100% of the viewport and its only exit is a 16x16 target — the Stay-Put Rule's guarantee is desktop-only. Every property control renders flat and takes its affordance from hover, which does not exist on touch: Status, Project, Due date, Priority, Assignee, Tags, Repeat and Created all look like identical label/value rows, with nothing distinguishing the four editable selects from the two read-only values. The mobile header is a 56px band holding one 20px icon and nothing else — no product name, no page name. The property grid keeps a fixed 128px label column, 26% of the panel at 500px and 33% at 390.

## Minor Observations

- The Scrim Rule collapses in dark mode. `--background` dark resolves to `#0a0a0a`; a `rgb(0 0 0 / 0.5)` scrim yields `#050505`. Page-vs-scrimmed contrast is **1.03:1** dark against 3.91:1 light. A floating layer that traps focus does not visibly demote what it covers.
- `color-scheme` is never declared (`html` and `body` both compute `normal`, no meta tag), so native controls stay light in dark mode: the date input's calendar indicator paints dark-on-dark and the native picker opens white. One line on `:root`.
- Four date formats on screen at once: `2026-09-11` (table cell), `11.09.2026` (native input), `15 Sept 2026, 22:55` (Created), `15/09/2026, 22:55:59` (comment). Plus `dd.mm.yyyy` placeholders in the filter bar directly above a column of ISO dates.
- Activity references are real anchors implementing the Real Address Rule, but render as bold foreground text with no colour and no persistent underline — the underline appears only on hover, which does not exist on touch. Implemented and then hidden.
- Subtasks DO visually indent: the `CornerDownRight` glyph plus `gap-2` pushes the title ~28px right of a root task's. DESIGN.md says a subtask carries only a glyph and no indentation; the rule and the rendering disagree.
- The filter bar's 390px wrap is ragged because `ml-auto` survives the wrap: Filters+Overdue left-aligned, the sort cluster pushed right, rows starting 105px apart. One-line fix, not a re-layout.
- Recurrence constraint disagrees with itself: `recurrence.tsx:174` allows `min={1}` for "every N days"; `TaskProperties.tsx:295` enforces `min={2}` for the same field.
- A typed comment draft is silently discarded when switching tabs in the panel — Radix unmounts inactive `TabsContent` and the draft lives in component state.
- `bg-green-500` status dots on `/admin` (second accent hue); `N/A` on `/settings` in a bordered card the system says it does not have; a teal checked checkbox on a read-only `/archive` row — accent spent on something that cannot be pressed.
- The mobile off-canvas sidebar is 288px = 58% of viewport with the correct 50% scrim, and still carries the collapse toggle, which has no function below `md`.
- The `enabled` prop on `TaskComments`/`TaskAttachments` is never passed by `TaskDetail` — the lazy loading it implements is actually delivered by Radix unmounting, so the prop is dead code documenting a mechanism the app does not use.
- Sole detector finding: `text-[10px]` in `User.tsx:74`.

### Retracted during verification
- No lingering-overlay / dead-click bug exists. An early measurement showed the sheet overlay still mounted after Escape; a clean repeat showed it correctly removed, the URL dropping `?task=`, and the sidebar clickable. The first reading was an automation artifact.
- The Left-the-Page Rule holds in pixels: `[data-slot=table-container]` computes `box-shadow: none` and the sheet gets the exact documented Float shadow.
- Dark mode is CLEANER than light on contrast, not worse: muted text at `oklch(0.708)` clears 4.5:1 comfortably and the red overdue text hits 5.74-6.21:1. Dark has one contrast failure app-wide; light has two.

## Questions to Consider

1. If the panel is the record's one address and every field edits in place, why does creating a record use a completely different interaction model? What would it cost to make Add Task create a titled task immediately and open its panel — so creation and editing are the same act, the modal disappears, and the eight-field form is deleted rather than redesigned?
2. The product's defining fact is that bots and humans touch the same records — so why can you not see, anywhere, what a bot is doing right now? What would the Bots page look like as an operations console for your agents rather than a credentials table?
3. DESIGN.md bans the `⋮` on tasks and ships it on projects, tags and bots — which half is wrong? If the One Address Rule is right, projects and tags deserve panels and three menus should be deleted. If the menus are fine, the rule is a special case dressed up as a principle.
4. What is the Tasks table actually for, given the dashboard already answers "what needs me now"? If its job is bulk triage it needs multi-select and bulk edit; if it is search and reference it needs server-side paging, sortable headers and a text query. It has none of those.
5. The Mirrored Theme Rule made the primary button unreadable — how many other rules in DESIGN.md optimise one variable without checking the second? Should a contrast budget become a mandatory part of defining any token?
