import { expect, test } from "@playwright/test"
import { botLine } from "./utils/bots"
import { randomEmail } from "./utils/random"
import { storeTokenAndClose } from "./utils/tokenDialog"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("Granting a bot user “Create tags” lets it add to the vocabulary", async ({
  page,
  request,
}) => {
  const email = randomEmail()
  await logInUser(page, email)
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
  await page.getByRole("button", { name: "New bot user" }).click()
  const draft = page.getByRole("complementary", { name: "New bot user" })
  await draft.getByRole("textbox", { name: "Bot name" }).fill("Triage agent")
  await draft.getByRole("checkbox", { name: "Support queue" }).check()
  await draft.getByRole("checkbox", { name: "Update tasks" }).check()
  await expect(
    draft.getByRole("checkbox", { name: "Create tags" }),
  ).not.toBeChecked()
  await draft.getByRole("button", { name: "Create and issue token" }).click()
  const dialog = page.getByRole("dialog", { name: "Token for Triage agent" })
  const token = await dialog
    .getByRole("textbox", { name: "Bot token" })
    .inputValue()
  await storeTokenAndClose(dialog)
  const asBot = { Authorization: `Bearer ${token}` }

  const line = botLine(page, "Triage agent")
  await expect(line).toContainText("updates")
  await expect(line).not.toContainText("tags")

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
  const createTags = page
    .getByRole("complementary", { name: "Triage agent", exact: true })
    .getByRole("checkbox", { name: "Create tags" })
  await createTags.click()
  await expect(createTags).toBeChecked()
  await page.keyboard.press("Escape")
  await expect(line).toContainText("tags")

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
