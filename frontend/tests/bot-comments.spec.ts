import { expect, test } from "@playwright/test"
import { createUser } from "./utils/privateApi.ts"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("A bot user's comment names the bot and offers no edit or delete", async ({
  page,
  request,
}) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await logInUser(page, email, password)

  // Everything up to the comment happens over the API, as an integration
  // would do it; what is under test is how the thread shows it.
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
  const task = await (
    await request.post(`${api}/tasks/`, {
      headers: asUser,
      data: { title: "Ship 1.2", project_id: project.id },
    })
  ).json()
  const bot = await (
    await request.post(`${api}/bot-users/`, {
      headers: asUser,
      data: {
        name: "Status bot",
        scope: {
          project_ids: [project.id],
          permissions: { read_tasks: true, add_comments: true },
        },
      },
    })
  ).json()
  const { token } = await (
    await request.post(`${api}/bot-users/${bot.id}/token`, { headers: asUser })
  ).json()
  const commented = await request.post(`${api}/tasks/${task.id}/comments/`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { body: "Deployed to staging" },
  })
  expect(commented.ok()).toBe(true)

  await page.goto(`/tasks?project_id=${project.id}`)
  await page
    .getByRole("row", { name: /Ship 1\.2/ })
    .getByText("Ship 1.2")
    .click()

  // Comments are the panel's first tab.
  const dialog = page.getByRole("dialog", { name: /Ship 1\.2/ })
  const botComment = dialog
    .locator("div.rounded-md")
    .filter({ hasText: "Deployed to staging" })
  await expect(botComment).toContainText("Status bot")
  await expect(botComment).toContainText("Bot")
  await expect(
    botComment.getByRole("button", { name: "Edit comment" }),
  ).toHaveCount(0)
  await expect(
    botComment.getByRole("button", { name: "Delete comment" }),
  ).toHaveCount(0)

  // The user's own comment keeps both.
  await dialog.getByPlaceholder("Add a comment").fill("Thanks")
  await dialog.getByRole("button", { name: "Comment", exact: true }).click()
  const ownComment = dialog
    .locator("div.rounded-md")
    .filter({ hasText: "Thanks" })
  await expect(
    ownComment.getByRole("button", { name: "Edit comment" }),
  ).toBeVisible()
})
