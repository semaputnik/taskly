import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

/**
 * A task in a project with a bot user that has worked on it: it moved the
 * task, then commented. Everything up to the panel happens over the API, as an
 * integration would do it.
 */
async function taskWithBotWork(page: Page) {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Website relaunch" })
  const task = await api.create("/tasks/", {
    title: "Fix the stylesheet",
    project_id: project.id,
  })
  const bot = await api.create("/bot-users/", {
    name: "inbox-triage",
    scope: {
      project_ids: [project.id],
      permissions: {
        read_tasks: true,
        update_tasks: true,
        add_comments: true,
      },
    },
  })
  const { token } = await (await api.post(`/bot-users/${bot.id}/token`)).json()
  const asBot = { Authorization: `Bearer ${token}` }
  const moved = await page.request.patch(`${api.url}/tasks/${task.id}`, {
    headers: asBot,
    data: { status: "in_progress" },
  })
  expect(moved.ok()).toBe(true)
  const commented = await page.request.post(
    `${api.url}/tasks/${task.id}/comments/`,
    { headers: asBot, data: { body: "Two pages still use the old sheet" } },
  )
  expect(commented.ok()).toBe(true)
  return { api, task }
}

const open = async (page: Page, taskId: string, title: string) => {
  await page.goto(`/tasks?view=table&task=${taskId}`)
  const panel = page.getByRole("complementary", { name: title })
  const activity = panel.getByRole("region", { name: "Activity" })
  await expect(activity).toBeVisible()
  return { panel, activity }
}

test("Events and comments read as one history, oldest first, naming who", async ({
  page,
}) => {
  const { api, task } = await taskWithBotWork(page)
  await api.create(`/tasks/${task.id}/comments/`, { body: "Swapping them now" })
  await api.patch(`/tasks/${task.id}`, { priority: "P2" })
  const { activity } = await open(page, task.id, "Fix the stylesheet")

  const lines = activity.getByRole("listitem")
  // A day separator, then the history from the start. The count is the lines
  // that are moments, not the separator.
  await expect(lines).toHaveText([
    "Today",
    /^\d{1,2}:\d\d.*You created this in Website relaunch$/,
    /^\d{1,2}:\d\d.*inbox-triage moved it to In progress$/,
    /^\d{1,2}:\d\d.*inbox-triage.*bot userTwo pages still use the old sheet$/,
    /^\d{1,2}:\d\d.*YouSwapping them now.*Edit.*Delete$/,
    /^\d{1,2}:\d\d.*You set the priority to P2$/,
  ])
  await expect(
    activity.getByRole("heading", { name: /^Activity\s*5$/ }),
  ).toBeVisible()

  // A bot user's comment is read-only; the reader's own is not.
  const bots = lines.filter({ hasText: "Two pages still use" })
  await expect(
    bots.getByRole("button", { name: "Delete comment" }),
  ).toHaveCount(0)
  await expect(bots.getByRole("button", { name: "Edit comment" })).toHaveCount(
    0,
  )
  const own = lines.filter({ hasText: "Swapping them now" })
  await expect(own.getByRole("button", { name: "Edit comment" })).toBeVisible()
  await expect(
    own.getByRole("button", { name: "Delete comment" }),
  ).toBeVisible()

  // The log never tells a comment twice: no line says one was written.
  await expect(activity).not.toContainText("Commented on")

  // A line that names a bot user opens it over this screen.
  await activity.getByRole("link", { name: "inbox-triage" }).first().click()
  await expect(
    page.getByRole("complementary", { name: "inbox-triage" }),
  ).toBeVisible()
})

test("A comment is posted with Ctrl or Command Enter, and the Comment action", async ({
  page,
}) => {
  const { task } = await taskWithBotWork(page)
  const { activity } = await open(page, task.id, "Fix the stylesheet")
  const field = activity.getByRole("textbox", { name: "New comment" })
  const post = activity.getByRole("button", { name: "Comment", exact: true })

  await expect(post).toBeDisabled()
  await field.fill("First, by keyboard")
  await field.press("ControlOrMeta+Enter")
  await expect(field).toHaveValue("")
  const first = activity
    .getByRole("listitem")
    .filter({ hasText: "First, by keyboard" })
  await expect(first).toBeVisible()

  await field.fill("Second, by the action")
  await post.click()
  await expect(field).toHaveValue("")
  const second = activity
    .getByRole("listitem")
    .filter({ hasText: "Second, by the action" })
  await expect(second).toBeVisible()

  // New comments land at the end, after what was already said.
  const lines = await activity.getByRole("listitem").allTextContents()
  const at = (text: string) => lines.findIndex((l) => l.includes(text))
  expect(at("Two pages still use")).toBeLessThan(at("First, by keyboard"))
  expect(at("First, by keyboard")).toBeLessThan(at("Second, by the action"))
})

test("An unsent comment survives closing the panel and opening the task again", async ({
  page,
}) => {
  const { task } = await taskWithBotWork(page)
  const { panel, activity } = await open(page, task.id, "Fix the stylesheet")
  await activity
    .getByRole("textbox", { name: "New comment" })
    .fill("Still thinking about this")

  await page.keyboard.press("Escape")
  await expect(page.locator("[data-record-column]")).toHaveCount(0)
  // Opened again from the list, not by reloading the page: the draft is kept
  // for as long as the page is open.
  await page
    .getByRole("row", { name: /Fix the stylesheet/ })
    .getByText("Fix the stylesheet")
    .click()

  await expect(
    panel
      .getByRole("region", { name: "Activity" })
      .getByRole("textbox", { name: "New comment" }),
  ).toHaveValue("Still thinking about this")
})

test("An own comment is edited in place, and deleted with an Undo", async ({
  page,
}) => {
  const { api, task } = await taskWithBotWork(page)
  await api.create(`/tasks/${task.id}/comments/`, { body: "Swapping them now" })
  const { activity } = await open(page, task.id, "Fix the stylesheet")
  const own = () =>
    activity.getByRole("listitem").filter({ hasText: /Swapping them|Swapped/ })

  await own().getByRole("button", { name: "Edit comment" }).click()
  const edit = activity.getByRole("textbox", { name: "Edit comment" })
  await edit.fill("Swapped them all")
  await activity.getByRole("button", { name: "Save" }).click()
  await expect(own()).toContainText("Swapped them all")

  await own().getByRole("button", { name: "Delete comment" }).click()
  await expect(own()).toHaveCount(0)
  await page.getByRole("button", { name: "Undo" }).click()
  await expect(own()).toContainText("Swapped them all")
})

test("A task with no history says so in one line", async ({ page }) => {
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", { title: "Blank slate" })
  await page.route("**/api/v1/activity-log/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: [], count: 0 }),
    }),
  )

  const { activity } = await open(page, task.id, "Blank slate")
  await expect(
    activity.getByText("Nothing has happened to this task yet."),
  ).toBeVisible()
})

test("The history reads on a phone without scrolling sideways", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const { task } = await taskWithBotWork(page)
  const { activity } = await open(page, task.id, "Fix the stylesheet")
  await activity.scrollIntoViewIfNeeded()

  await expect(
    activity.getByRole("textbox", { name: "New comment" }),
  ).toBeVisible()
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(0)
})
