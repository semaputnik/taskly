import { expect, test } from "@playwright/test"
import { createUser } from "./utils/privateApi.ts"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("A bot user is created on the Bots page and its token is shown once", async ({
  page,
  request,
}) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await logInUser(page, email, password)

  await page.goto("/projects")
  await page.getByRole("button", { name: "Add Project" }).click()
  await page.getByPlaceholder("Project name").fill("Support queue")
  await page.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Project created successfully")).toBeVisible()

  await page.goto("/bots")
  await expect(page.getByRole("heading", { name: "Bots" })).toBeVisible()
  await page.getByRole("button", { name: "Add Bot" }).click()
  await page.getByPlaceholder("Bot name").fill("Triage agent")
  await page.getByRole("checkbox", { name: "Support queue" }).check()
  await expect(page.getByRole("checkbox", { name: "Read tasks" })).toBeChecked()
  await page.getByRole("button", { name: "Create and issue token" }).click()

  const dialog = page.getByRole("dialog", { name: "Token for Triage agent" })
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText("It won't be shown again")
  const token = await dialog
    .getByRole("textbox", { name: "Bot token" })
    .inputValue()
  expect(token).toMatch(/^taskly_bot_/)
  await expect(dialog.getByRole("button", { name: "Copy" })).toBeVisible()

  // The token works against the API as the bot user it was issued for.
  const response = await request.get(
    `${process.env.VITE_API_URL}/api/v1/projects/`,
    { headers: { Authorization: `Bearer ${token}` } },
  )
  expect(response.ok()).toBe(true)
  const projects = await response.json()
  expect(projects.data.map((p: { name: string }) => p.name)).toEqual([
    "Support queue",
  ])

  await dialog.getByRole("button", { name: "Done" }).click()
  await expect(dialog).toBeHidden()

  const row = page.getByRole("row").filter({ hasText: "Triage agent" })
  await expect(row).toContainText("Support queue")
  await expect(row).toContainText("Read tasks")
  await expect(row).toContainText("Issued")
  await expect(row.getByRole("button", { name: "Issue token" })).toHaveCount(0)

  // Once the dialog is gone, nothing on the page can show the token again.
  await page.reload()
  await expect(row).toBeVisible()
  expect(await page.content()).not.toContain(token)
})
