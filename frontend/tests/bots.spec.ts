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
  await expect(row).toContainText("Never expires")
  await expect(row.getByRole("button", { name: "Issue token" })).toHaveCount(0)

  // Once the dialog is gone, nothing on the page can show the token again.
  // The request above used it, which the reloaded page reports.
  await page.reload()
  await expect(row).toBeVisible()
  await expect(row).toContainText("Last used")
  expect(await page.content()).not.toContain(token)
})

test("A token is revoked and a new one issued with an expiry", async ({
  page,
  request,
}) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await logInUser(page, email, password)
  const api = `${process.env.VITE_API_URL}/api/v1`

  await page.goto("/bots")
  await page.getByRole("button", { name: "Add Bot" }).click()
  await page.getByPlaceholder("Bot name").fill("Nightly sync")
  await page.getByRole("button", { name: "Create and issue token" }).click()
  const firstDialog = page.getByRole("dialog", {
    name: "Token for Nightly sync",
  })
  const first = await firstDialog
    .getByRole("textbox", { name: "Bot token" })
    .inputValue()
  await firstDialog.getByRole("button", { name: "Done" }).click()

  const row = page.getByRole("row").filter({ hasText: "Nightly sync" })
  await row.getByRole("button", { name: "Revoke" }).click()
  await page
    .getByRole("dialog", { name: "Revoke the token for Nightly sync?" })
    .getByRole("button", { name: "Revoke" })
    .click()
  await expect(row).toContainText("Revoked")

  const refused = await request.get(`${api}/tasks/`, {
    headers: { Authorization: `Bearer ${first}` },
  })
  expect(refused.status()).toBe(401)

  await row.getByRole("button", { name: "Issue new token" }).click()
  const expiresOn = new Date()
  expiresOn.setDate(expiresOn.getDate() + 7)
  const date = [
    expiresOn.getFullYear(),
    String(expiresOn.getMonth() + 1).padStart(2, "0"),
    String(expiresOn.getDate()).padStart(2, "0"),
  ].join("-")
  await page.getByLabel("Expires on (optional)").fill(date)
  await page.getByRole("button", { name: "Issue", exact: true }).click()

  const secondDialog = page.getByRole("dialog", {
    name: "Token for Nightly sync",
  })
  await expect(secondDialog).toContainText("It won't be shown again")
  await expect(secondDialog).toContainText("It expires")
  const second = await secondDialog
    .getByRole("textbox", { name: "Bot token" })
    .inputValue()
  expect(second).not.toBe(first)
  await secondDialog.getByRole("button", { name: "Done" }).click()

  await expect(row).toContainText("Expires")
  await expect(row).toContainText("Never used")
  const accepted = await request.get(`${api}/tasks/`, {
    headers: { Authorization: `Bearer ${second}` },
  })
  expect(accepted.ok()).toBe(true)
})
