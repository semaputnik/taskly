---
version: 1
slug: "src-routes-layout-bots-tsx"
primary_target: "src/routes/_layout/bots.tsx"
related_targets: ["src/routes/_layout/activity.tsx","src/routes/_layout.tsx","src/components/Bots/BotPanel.tsx","src/components/Sidebar/AppSidebar.tsx"]
---

# Surface brief: Bots, Activity and the phone navigation (redesign slice 4)

Scope: the Bots route (`src/routes/_layout/bots.tsx`) and the bot user's column, the Activity
route, the webhooks a bot user's column shows (F-11), and the shell's navigation on a phone.
Visitor mode: **Operate**. The direction contract is inherited from the dashboard brief
(`src-routes-layout-index-tsx.md`, seed 018cd79f); this brief adds only the surface strategy for
these screens.

## Audience, job, action

- Setting up a bot user: name it, tick the projects it reaches and what it may do, issue its
  token once, set the URLs it is called back on, send a test. Later: see whether it is working,
  what it is on, what it did, and why a delivery failed.
- Reading the log: what happened, by whom, narrowed to a kind of change or one bot user, and
  restoring what was deleted.
- On a phone: reach every main screen and capture with the thumb.

## Decisions taken in discovery (2026-10-06)

- **Phone navigation at the bottom**: a tab bar with Today, Tasks, a central + and Bots,
  Activity. Projects, Tags, Archive, Settings, appearance and sign-out sit behind the avatar in
  the top bar. The + on any page raises a capture sheet above the keyboard carrying the same
  line and its search; "More options…" in the sheet opens the full draft. The capture line is no
  longer pinned to the bottom of the day page and the task list on a phone (FR-06.15 amended);
  there is no floating button. Desktop navigation is unchanged.
- **Bots as lines**: monogram plate, name, token state as a green dot ("Working") or a hollow
  one ("No token"), projects and permissions in words, webhook state, last use at the right;
  deleted bot users in their own quiet section. A new bot user is a draft in the column, like
  a task; creating it issues the token, shown once.
- **The bot user's column** as one document: Token (state, expiry, Issue or Revoke), Last used,
  Reach in one sentence; sections Projects (checkboxes), Permissions (checkboxes, with "always"
  and "never" rows drawn dashed for what cannot change), Webhooks, On its plate (its open
  tasks), Activity (what it did), Delete bot user at the foot. No tabs.
- **Webhooks in full in this slice**: the F-11 backend (outbox, retries, signature, private
  address refusal, test event, last delivery) and the section in the column: each of the two
  webhooks with its URL in mono, the last delivery (when, status or error), Send a test, Change,
  Clear; Regenerate secret at the heading, the secret shown once.
- **Activity page**: heading and a counts sentence, filters as one text row (kind of change,
  actor), an order menu (newest or oldest first, the API gains the order), day groups with a
  count, lines with time, actor, sentence, Restore at the right, own lines muted, deleted names
  struck; the pager says the page and offers Older or Newer.

## First viewports

- Bots (desktop): "Bots" with "+ New bot user" at the right, the counts sentence, "Bot users"
  heading over the lines, "Deleted" below; the column opens beside as for a task.
- Activity (desktop): heading, sentence, filter row, "Today" group first.
- Phone: the top bar holds the wordmark and the avatar; the tab bar is 56px above the
  browser's own bar; the capture sheet rises over a dimmed page above the keyboard.

## Unresolved

- Whether the bot column's "On its plate" should offer closing a task inline; decided in build.
- Whether a failed last delivery should also be surfaced on the day page's Changes; not now.

References: `.impeccable/mocks/changelog-bots.html`, `changelog-activity.html` and
`changelog-phone-nav.html` (iPhone 16 in Safari), the approved mocks and the critique reference
at the finish review.
