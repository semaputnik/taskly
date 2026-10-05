import { expect, test } from "@playwright/test"
import { openCaptured, openDraft } from "./utils/capture"
import { randomEmail } from "./utils/random"
import { chooseFilter, taskLine } from "./utils/tasks"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("A task is assigned to a bot user from the task form and found by it", async ({
  page,
  request,
}) => {
  const email = randomEmail()
  await logInUser(page, email)

  // The bot user is created over the API; the Bots page has its own test.
  const userToken = await page.evaluate(() =>
    localStorage.getItem("access_token"),
  )
  const created = await request.post(
    `${process.env.VITE_API_URL}/api/v1/bot-users/`,
    {
      headers: { Authorization: `Bearer ${userToken}` },
      data: {
        name: "Triage bot",
        scope: { project_ids: [], permissions: {} },
      },
    },
  )
  expect(created.ok()).toBe(true)

  await page.goto("/tasks")
  // Captured in one field, then assigned in the panel that capture leaves
  // open — the same controls that edit a task any other day.
  await openDraft(page)
  const title = page.getByRole("textbox", { name: "Task title" })
  await title.fill("Sort the inbox")
  await title.press("Enter")
  await openCaptured(page)
  const panel = page.getByRole("complementary", { name: "Sort the inbox" })
  await panel.getByRole("combobox", { name: "Assignee" }).click()
  await page.getByRole("option", { name: "Triage bot" }).click()
  await expect(panel.getByRole("combobox", { name: "Assignee" })).toContainText(
    "Triage bot",
  )
  await page.keyboard.press("Escape")

  await openDraft(page)
  await title.fill("Call the bank")
  await title.press("Enter")
  await openCaptured(page)
  await expect(
    page.getByRole("complementary", { name: "Call the bank" }),
  ).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(taskLine(page, "Call the bank")).toBeVisible()

  await chooseFilter(page, "Anyone", "Triage bot")
  await expect(page).toHaveURL(/assignee=/)
  await expect(taskLine(page, "Sort the inbox")).toBeVisible()
  await expect(taskLine(page, "Call the bank")).toHaveCount(0)
})
