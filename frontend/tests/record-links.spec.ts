import { expect, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

test("A task linked from a bot user's activity replaces the bot's sheet", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Support queue" })
  const bot = await api.create("/bot-users/", {
    name: "Triage agent",
    scope: { project_ids: [project.id], permissions: { create_tasks: true } },
  })
  const { token } = await api.create(`/bot-users/${bot.id}/token`)
  const created = await page.request.post(`${api.url}/tasks/`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { title: "Answer the refund request", project_id: project.id },
  })
  expect(created.ok()).toBe(true)

  await page.goto(`/bots?bot=${bot.id}`)
  const feed = page
    .getByRole("dialog", { name: "Triage agent" })
    .getByRole("list", { name: "Recent activity by Triage agent" })
  await feed.getByRole("link", { name: "Answer the refund request" }).click()

  await expect(
    page.getByRole("dialog", { name: "Answer the refund request" }),
  ).toBeVisible()
  await expect(page.getByRole("dialog")).toHaveCount(1)
  expect(new URL(page.url()).searchParams.has("bot")).toBe(false)
})

test("Activity entries open the record they name", async ({ page }) => {
  await newUser(page)
  const api = await userApi(page)
  const tag = await api.create("/tags/", { name: "errands" })
  const task = await api.create("/tasks/", { title: "Book the vet" })
  await api.create(`/tasks/${task.id}/comments/`, { body: "Friday works" })

  await page.goto("/activity")
  const rows = page.getByRole("row")

  await rows
    .filter({ hasText: "errands" })
    .getByRole("link", { name: "errands" })
    .click()
  await expect(page.getByRole("dialog", { name: "errands" })).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`/activity\\?.*tag_id=${tag.id}`))
  await page.keyboard.press("Escape")
  await expect(page.getByRole("dialog")).toHaveCount(0)

  await rows
    .filter({ hasText: "Commented on Book the vet" })
    .getByRole("link", { name: "Book the vet" })
    .click()
  await expect(page.getByRole("dialog", { name: "Book the vet" })).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`/activity\\?.*task=${task.id}`))
})
