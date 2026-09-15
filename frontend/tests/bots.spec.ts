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

test("A bot's scope is narrowed and the bot is deleted from the Bots page", async ({
  page,
  request,
}) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await logInUser(page, email, password)
  const api = `${process.env.VITE_API_URL}/api/v1`

  await page.goto("/projects")
  for (const name of ["Docs", "Billing"]) {
    await page.getByRole("button", { name: "Add Project" }).click()
    await page.getByPlaceholder("Project name").fill(name)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Project created successfully")).toBeVisible()
    await expect(page.getByRole("dialog")).toBeHidden()
  }

  await page.goto("/bots")
  await page.getByRole("button", { name: "Add Bot" }).click()
  await page.getByPlaceholder("Bot name").fill("Changelog agent")
  await page.getByRole("checkbox", { name: "Docs" }).check()
  await page.getByRole("checkbox", { name: "Billing" }).check()
  await page.getByRole("checkbox", { name: "Create tasks" }).check()
  await page.getByRole("button", { name: "Create and issue token" }).click()
  const tokenDialog = page.getByRole("dialog", {
    name: "Token for Changelog agent",
  })
  const token = await tokenDialog
    .getByRole("textbox", { name: "Bot token" })
    .inputValue()
  await tokenDialog.getByRole("button", { name: "Done" }).click()
  const asBot = { Authorization: `Bearer ${token}` }

  // The bot works in Billing while Billing is still in its scope.
  const projects = await (
    await request.get(`${api}/projects/`, { headers: asBot })
  ).json()
  const billing = projects.data.find(
    (p: { name: string }) => p.name === "Billing",
  )
  const created = await request.post(`${api}/tasks/`, {
    headers: asBot,
    data: { title: "Draft the invoice notes", project_id: billing.id },
  })
  expect(created.ok()).toBe(true)
  const task = await created.json()

  // Narrowed to Docs, renamed, and able to create nothing any more.
  await page
    .getByRole("button", { name: "Actions for Changelog agent" })
    .click()
  await page.getByRole("menuitem", { name: "Edit Bot" }).click()
  const editDialog = page.getByRole("dialog", { name: "Edit Bot" })
  await expect(
    editDialog.getByRole("checkbox", { name: "Billing" }),
  ).toBeChecked()
  await editDialog.getByPlaceholder("Bot name").fill("Docs agent")
  await editDialog.getByRole("checkbox", { name: "Billing" }).uncheck()
  await editDialog.getByRole("checkbox", { name: "Create tasks" }).uncheck()
  await editDialog.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Bot updated successfully")).toBeVisible()
  await expect(editDialog).toBeHidden()

  const row = page.getByRole("row").filter({ hasText: "Docs agent" })
  await expect(row).toContainText("Docs")
  await expect(row).not.toContainText("Billing")
  await expect(row).toContainText("Read tasks")
  await expect(row).not.toContainText("Create tasks")

  // The same token's very next request is held to the new scope.
  const outside = await request.get(`${api}/tasks/${task.id}`, {
    headers: asBot,
  })
  expect(outside.status()).toBe(403)
  expect((await outside.json()).detail.code).toBe("outside_scope")

  await page.getByRole("button", { name: "Actions for Docs agent" }).click()
  await page.getByRole("menuitem", { name: "Delete Bot" }).click()
  await page
    .getByRole("dialog", { name: "Delete Docs agent?" })
    .getByRole("button", { name: "Delete" })
    .click()
  await expect(page.getByText("“Docs agent” was deleted")).toBeVisible()
  await expect(row).toHaveCount(0)

  const refused = await request.get(`${api}/tasks/`, { headers: asBot })
  expect(refused.status()).toBe(401)

  // What it did is still in the log under its name.
  await page.goto("/activity")
  await expect(
    page.getByRole("row").filter({ hasText: "Draft the invoice notes" }),
  ).toContainText("Docs agent")
})
