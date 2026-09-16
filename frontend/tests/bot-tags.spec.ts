import { expect, test } from "@playwright/test"
import { createUser } from "./utils/privateApi.ts"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("Granting a bot user “Create tags” lets it add to the vocabulary", async ({
  page,
  request,
}) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await logInUser(page, email, password)
  const api = `${process.env.VITE_API_URL}/api/v1`
  const userToken = await page.evaluate(() =>
    localStorage.getItem("access_token"),
  )
  const asUser = { Authorization: `Bearer ${userToken}` }

  const project = await (
    await request.post(`${api}/projects/`, {
      headers: asUser,
      data: { name: "Support queue" },
    })
  ).json()
  const task = await (
    await request.post(`${api}/tasks/`, {
      headers: asUser,
      data: {
        title: "Answer the ticket",
        project_id: project.id,
        tags: ["urgent"],
      },
    })
  ).json()

  // Created with the tasks it needs and without the tags permission, which is
  // off until it is checked.
  await page.goto("/bots")
  await page.getByRole("button", { name: "Add Bot" }).click()
  await page.getByPlaceholder("Bot name").fill("Triage agent")
  await page.getByRole("checkbox", { name: "Support queue" }).check()
  await page.getByRole("checkbox", { name: "Update tasks" }).check()
  await expect(
    page.getByRole("checkbox", { name: "Create tags" }),
  ).not.toBeChecked()
  await page.getByRole("button", { name: "Create and issue token" }).click()
  const dialog = page.getByRole("dialog", { name: "Token for Triage agent" })
  const token = await dialog
    .getByRole("textbox", { name: "Bot token" })
    .inputValue()
  await dialog.getByRole("button", { name: "Done" }).click()
  const asBot = { Authorization: `Bearer ${token}` }

  const row = page.getByRole("row", { name: "Open Triage agent" })
  await expect(row).toContainText("Update tasks")
  await expect(row).not.toContainText("Create tags")

  // It applies a tag the user already has, and is refused a name that is not
  // a tag yet.
  const applied = await request.patch(`${api}/tasks/${task.id}`, {
    headers: asBot,
    data: { tags: ["urgent"] },
  })
  expect(applied.ok()).toBe(true)
  const refused = await request.post(`${api}/tags/`, {
    headers: asBot,
    data: { name: "billing" },
  })
  expect(refused.status()).toBe(403)
  expect((await refused.json()).detail.permission).toBe("create_tags")

  // Granted in the bot user's panel, the same request goes through.
  await row.click()
  const createTags = page
    .getByRole("dialog", { name: "Triage agent" })
    .getByRole("checkbox", { name: "Create tags" })
  await createTags.click()
  await expect(createTags).toBeChecked()
  await page.keyboard.press("Escape")
  await expect(row).toContainText("Create tags")

  const created = await request.post(`${api}/tags/`, {
    headers: asBot,
    data: { name: "billing" },
  })
  expect(created.ok()).toBe(true)
  const tagged = await request.patch(`${api}/tasks/${task.id}`, {
    headers: asBot,
    data: { tags: ["urgent", "refund"] },
  })
  expect(tagged.ok()).toBe(true)

  // Both show on the Tags page, among the user's own vocabulary.
  await page.goto("/tags")
  await expect(
    page.getByRole("row").filter({ hasText: "billing" }),
  ).toContainText("No tasks")
  await expect(
    page.getByRole("row").filter({ hasText: "refund" }),
  ).toContainText("1 task")

  // And the tags are the bot user's doing, not its owner's.
  await page.goto("/activity")
  const logRow = page.getByRole("row").filter({ hasText: "Created the tag" })
  await expect(logRow.first()).toContainText("Triage agent")
  await expect(logRow.first()).not.toContainText("You")
})
