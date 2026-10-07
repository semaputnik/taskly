import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"
import { openCaptured, openDraft } from "./utils/capture"
import { randomEmail } from "./utils/random"
import { taskLine } from "./utils/tasks"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("A user's own changes appear on the Activity page, newest first", async ({
  page,
}) => {
  const email = randomEmail()
  await logInUser(page, email)

  await page.goto("/tasks")
  await openDraft(page)
  const title = page.getByRole("textbox", { name: "Task title" })
  await title.fill("Renew the passport")
  await title.press("Enter")
  await openCaptured(page)
  await expect(
    page.getByRole("complementary", { name: "Renew the passport" }),
  ).toBeVisible()
  await page.keyboard.press("Escape")

  await taskLine(page, "Renew the passport")
    .getByRole("checkbox", { name: "Mark done" })
    .click()
  // The list holds open work, so the task leaves it once it is done
  // (ADR-0006). Where it went is the point of the rest of this test.
  await expect(taskLine(page, "Renew the passport")).toHaveCount(0)

  await page.goto("/activity")
  const rows = page
    .getByRole("listitem")
    .filter({ hasText: "Renew the passport" })
  await expect(rows).toHaveCount(2)
  await expect(rows.nth(0)).toContainText("Completed Renew the passport")
  await expect(rows.nth(1)).toContainText("Created Renew the passport in Inbox")
  await expect(rows.nth(0)).toContainText("You")

  // The task still exists, so its entry opens it — here, over the log, rather
  // than dropping the reader on the task list.
  await rows.nth(1).getByRole("link", { name: "Renew the passport" }).click()
  await expect(page).toHaveURL(/\/activity\?task=/)
  await expect(
    page.getByRole("complementary", { name: /Renew the passport/ }),
  ).toBeVisible()
})

test("A deleted task can be restored from the Activity page", async ({
  page,
}) => {
  const email = randomEmail()
  await logInUser(page, email)

  await page.goto("/tasks")
  await openDraft(page)
  const title = page.getByRole("textbox", { name: "Task title" })
  await title.fill("Cancel the gym")
  await title.press("Enter")
  await openCaptured(page)
  await expect(
    page.getByRole("complementary", { name: "Cancel the gym" }),
  ).toBeVisible()
  await page.keyboard.press("Escape")
  // Gone before the row behind it is clicked, not still fading out over it.
  await expect(page.locator("[data-record-column]")).toHaveCount(0)

  const taskRow = taskLine(page, "Cancel the gym")
  await taskRow.getByRole("link", { name: "Cancel the gym" }).click()
  await page.getByRole("button", { name: "Delete task" }).click()
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Delete", exact: true })
    .click()
  await expect(
    page.getByText("It can be restored from the activity log"),
  ).toBeVisible()
  await expect(taskRow).toHaveCount(0)

  await page.goto("/activity")
  const deletion = page
    .getByRole("listitem")
    .filter({ hasText: "Deleted Cancel the gym" })
  await deletion.getByRole("button", { name: "Restore" }).click()
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Restore", exact: true })
    .click()
  await expect(page.getByText("“Cancel the gym” restored")).toBeVisible()
  await expect(
    page.getByRole("listitem").filter({ hasText: "Restored Cancel the gym" }),
  ).toBeVisible()
  // Its rows are back, so the deletion offers nothing more to restore.
  await expect(deletion.getByRole("button", { name: "Restore" })).toHaveCount(0)

  await page.goto("/tasks")
  await expect(taskLine(page, "Cancel the gym")).toBeVisible()
})

test("A bot user's changes appear on the Activity page under its name", async ({
  page,
  request,
}) => {
  const email = randomEmail()
  await logInUser(page, email)

  // The bot user is set up over the API: its management page has its own
  // test, and what matters here is how its changes are shown.
  const api = `${process.env.VITE_API_URL}/api/v1`
  const userToken = await page.evaluate(() =>
    localStorage.getItem("access_token"),
  )
  const asUser = { Authorization: `Bearer ${userToken}` }
  const project = await (
    await request.post(`${api}/projects/`, {
      headers: asUser,
      data: { name: "Releases" },
    })
  ).json()
  const bot = await (
    await request.post(`${api}/bot-users/`, {
      headers: asUser,
      data: {
        name: "Release bot",
        scope: {
          project_ids: [project.id],
          permissions: { create_tasks: true },
        },
      },
    })
  ).json()
  const { token } = await (
    await request.post(`${api}/bot-users/${bot.id}/token`, { headers: asUser })
  ).json()

  const created = await request.post(`${api}/tasks/`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { title: "Tag the release", project_id: project.id },
  })
  expect(created.ok()).toBe(true)

  await page.goto("/activity")
  const row = page.getByRole("listitem").filter({ hasText: "Tag the release" })
  await expect(row).toContainText("Created Tag the release in Releases")
  await expect(row).toContainText("Release bot")
  await expect(row).not.toContainText("You")
})

/** The log's lines, by what they say, newest or oldest first as drawn. */
const lines = (page: Page) =>
  page.getByRole("listitem").filter({ has: page.locator("time") })

test("The log is read in day groups with a count, and can be turned oldest first", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  for (const title of ["First thing", "Second thing", "Third thing"]) {
    await api.create("/tasks/", { title })
  }

  await page.goto("/activity")
  await expect(
    page.getByText("Every change in your account, newest first."),
  ).toBeVisible()
  // Everything happened today: one group, named, with how many lines it holds.
  const heading = page.getByRole("heading", { name: /^Today\s*3$/ })
  await expect(heading).toBeVisible()
  await expect(lines(page)).toHaveCount(3)
  await expect(lines(page).nth(0)).toContainText("Third thing")
  await expect(lines(page).nth(2)).toContainText("First thing")
  // Each line has its time in its own column.
  await expect(lines(page).first().locator("time")).toHaveText(
    /^\d{1,2}[:.]\d{2}/,
  )

  await page.getByRole("button", { name: "Order: Newest first" }).click()
  await page.getByRole("menuitemradio", { name: "Oldest first" }).click()
  await expect(page).toHaveURL(/order=oldest/)
  await expect(
    page.getByText("Every change in your account, oldest first."),
  ).toBeVisible()
  await expect(lines(page).nth(0)).toContainText("First thing")
  await expect(lines(page).nth(2)).toContainText("Third thing")
  await expect(heading).toBeVisible()

  // The order is in the address: it survives a reload.
  await page.reload()
  await expect(
    page.getByRole("button", { name: "Order: Oldest first" }),
  ).toBeVisible()
  await expect(lines(page).nth(0)).toContainText("First thing")

  await page.getByRole("button", { name: "Order: Oldest first" }).click()
  await page.getByRole("menuitemradio", { name: "Newest first" }).click()
  await expect(page).not.toHaveURL(/order=/)
  await expect(lines(page).nth(0)).toContainText("Third thing")
})

test("The pager says the page, and what a page further on is called follows the order", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  for (let n = 1; n <= 52; n++) {
    await api.create("/tasks/", { title: `Entry ${n}` })
  }

  await page.goto("/activity")
  await expect(page.getByText("52 entries · page 1 of 2")).toBeVisible()
  await expect(page.getByRole("button", { name: "Newer" })).toBeDisabled()
  await page.getByRole("button", { name: "Older" }).click()
  await expect(page).toHaveURL(/page=2/)
  await expect(page.getByText("52 entries · page 2 of 2")).toBeVisible()
  await expect(lines(page)).toHaveCount(2)
  await expect(lines(page).nth(1)).toContainText("Entry 1")

  // Oldest first: the same pager walks the other way, and says so.
  await page.goto("/activity?order=oldest")
  await expect(page.getByRole("button", { name: "Older" })).toBeDisabled()
  await page.getByRole("button", { name: "Newer" }).click()
  await expect(page).toHaveURL(/page=2/)
  await expect(lines(page)).toHaveCount(2)
  await expect(lines(page).nth(1)).toContainText("Entry 52")
})

test("The log is narrowed by kind and by actor, each said on the filter row", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Releases" })
  const bot = await api.create("/bot-users/", {
    name: "Release bot",
    scope: {
      project_ids: [project.id],
      permissions: { create_tasks: true },
    },
  })
  const { token } = await api.create(`/bot-users/${bot.id}/token`)
  const asBot = { Authorization: `Bearer ${token}` }
  await page.request.post(`${api.url}/tasks/`, {
    headers: asBot,
    data: { title: "Cut the build", project_id: project.id },
  })
  await api.create("/tasks/", { title: "Water the plants" })
  // The bot user goes; what it did stays readable under its name.
  expect((await api.delete(`/bot-users/${bot.id}`)).ok()).toBe(true)

  await page.goto("/activity")
  await expect(
    page.getByText(/entries, 1 of them by your bot users/),
  ).toBeVisible()

  // Everyone is offered: the reader, and the bot user although it is deleted.
  await page.getByRole("button", { name: "By anyone" }).click()
  await expect(page.getByRole("menuitemradio", { name: "You" })).toBeVisible()
  await page.getByRole("menuitemradio", { name: /Release bot/ }).click()
  await expect(page).toHaveURL(/actor=/)
  await expect(
    page.getByRole("button", { name: "Actor: By Release bot" }),
  ).toBeVisible()
  await expect(lines(page)).toHaveCount(1)
  await expect(lines(page).first()).toContainText("Cut the build")
  // A deleted bot user's name is struck through.
  await expect(
    lines(page).first().getByRole("link", { name: "Release bot" }),
  ).toHaveCSS("text-decoration-line", /line-through/)

  // The narrowings combine, and an empty one says what it was narrowed to.
  await page.getByRole("button", { name: "Anything that happened" }).click()
  await page.getByRole("menuitemradio", { name: "Completed" }).click()
  await expect(page).toHaveURL(/kind=completed/)
  await expect(
    page.getByText("This bot user has nothing under “Completed”."),
  ).toBeVisible()

  await page.getByRole("button", { name: "Clear all filters" }).click()
  await expect(page).not.toHaveURL(/actor=|kind=/)
  await expect(page.getByText(/Cut the build/)).toBeVisible()

  // "You" is the other side of it.
  await page.getByRole("button", { name: "By anyone" }).click()
  await page.getByRole("menuitemradio", { name: "You" }).click()
  await expect(page).toHaveURL(/actor=me/)
  await expect(lines(page).filter({ hasText: "Water the plants" })).toHaveCount(
    1,
  )
  await expect(lines(page).filter({ hasText: "Cut the build" })).toHaveCount(0)
  await page.getByRole("button", { name: "Remove the actor filter" }).click()
  await expect(lines(page).filter({ hasText: "Cut the build" })).toHaveCount(1)
})

test("A narrowed log that is empty names the narrowing, in its own words", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/activity?kind=tags")
  await expect(
    page.getByText("Nothing has happened to your tags yet."),
  ).toBeVisible()
  await page.goto("/activity?actor=me")
  await expect(
    page.getByText("You have not changed anything yet."),
  ).toBeVisible()
})
