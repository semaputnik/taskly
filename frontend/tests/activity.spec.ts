import { expect, test } from "@playwright/test"
import { openCaptured } from "./utils/capture"
import { createUser } from "./utils/privateApi.ts"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("A user's own changes appear on the Activity page, newest first", async ({
  page,
}) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await logInUser(page, email, password)

  await page.goto("/tasks?view=table")
  await page.getByRole("button", { name: "Add Task" }).click()
  const title = page.getByRole("textbox", { name: "Task title" })
  await title.fill("Renew the passport")
  await title.press("Enter")
  await openCaptured(page)
  await expect(
    page.getByRole("dialog", { name: "Renew the passport" }),
  ).toBeVisible()
  await page.keyboard.press("Escape")

  await page
    .getByRole("row", { name: /Renew the passport/ })
    .getByRole("checkbox", { name: "Mark as done" })
    .click()
  await expect(
    page
      .getByRole("row", { name: /Renew the passport/ })
      .getByRole("checkbox", { name: "Reopen task" }),
  ).toBeVisible()

  await page.goto("/activity")
  const rows = page.getByRole("row").filter({ hasText: "Renew the passport" })
  await expect(rows).toHaveCount(2)
  await expect(rows.nth(0)).toContainText("Completed Renew the passport")
  await expect(rows.nth(1)).toContainText("Created Renew the passport in Inbox")
  await expect(rows.nth(0)).toContainText("You")

  // The task still exists, so its entry opens it — here, over the log, rather
  // than dropping the reader on the task list.
  await rows.nth(1).getByRole("link", { name: "Renew the passport" }).click()
  await expect(page).toHaveURL(/\/activity\?task=/)
  await expect(
    page.getByRole("dialog", { name: /Renew the passport/ }),
  ).toBeVisible()
})

test("A deleted task can be restored from the Activity page", async ({
  page,
}) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await logInUser(page, email, password)

  await page.goto("/tasks?view=table")
  await page.getByRole("button", { name: "Add Task" }).click()
  const title = page.getByRole("textbox", { name: "Task title" })
  await title.fill("Cancel the gym")
  await title.press("Enter")
  await openCaptured(page)
  await expect(
    page.getByRole("dialog", { name: "Cancel the gym" }),
  ).toBeVisible()
  await page.keyboard.press("Escape")
  // Gone before the row behind it is clicked, not still fading out over it.
  await expect(page.getByRole("dialog")).toHaveCount(0)

  const taskRow = page.getByRole("row", { name: /Cancel the gym/ })
  await taskRow.getByText("Cancel the gym").click()
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
    .getByRole("row")
    .filter({ hasText: "Deleted Cancel the gym" })
  await deletion.getByRole("button", { name: "Restore" }).click()
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Restore", exact: true })
    .click()
  await expect(page.getByText("“Cancel the gym” restored")).toBeVisible()
  await expect(
    page.getByRole("row").filter({ hasText: "Restored Cancel the gym" }),
  ).toBeVisible()
  // Its rows are back, so the deletion offers nothing more to restore.
  await expect(deletion.getByRole("button", { name: "Restore" })).toHaveCount(0)

  await page.goto("/tasks?view=table")
  await expect(page.getByRole("row", { name: /Cancel the gym/ })).toBeVisible()
})

test("A bot user's changes appear on the Activity page under its name", async ({
  page,
  request,
}) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await logInUser(page, email, password)

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
  const row = page.getByRole("row").filter({ hasText: "Tag the release" })
  await expect(row).toContainText("Created Tag the release in Releases")
  await expect(row).toContainText("Release bot")
  await expect(row).toContainText("Bot")
  await expect(row).not.toContainText("You")
})
