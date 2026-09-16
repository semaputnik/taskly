import { expect, test } from "@playwright/test"
import { createUser } from "./utils/privateApi.ts"
import { randomEmail, randomPassword } from "./utils/random"
import { storeTokenAndClose } from "./utils/tokenDialog"
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
  const projectName = page.getByRole("textbox", { name: "Project name" })
  await projectName.fill("Support queue")
  await projectName.press("Enter")
  await expect(
    page.getByRole("dialog", { name: "Support queue" }),
  ).toBeVisible()
  await page.keyboard.press("Escape")

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

  await storeTokenAndClose(dialog)

  const row = page.getByRole("row", { name: "Open Triage agent" })
  await expect(row).toContainText("Support queue")
  await expect(row).toContainText("Read tasks")
  await expect(row).toContainText("Active")

  // Once the dialog is gone, nothing can show the token again. The request
  // above used it, which the bot user's panel reports.
  await page.reload()
  await row.click()
  const panel = page.getByRole("dialog", { name: "Triage agent", exact: true })
  await expect(panel).toContainText("Never — it works until revoked")
  await expect(panel).not.toContainText("Never used")
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
  await storeTokenAndClose(firstDialog)

  const row = page.getByRole("row", { name: "Open Nightly sync" })
  await row.click()
  const panel = page.getByRole("dialog", { name: "Nightly sync", exact: true })
  await panel.getByRole("button", { name: "Revoke" }).click()
  await page
    .getByRole("dialog", { name: "Revoke the token for Nightly sync?" })
    .getByRole("button", { name: "Revoke", exact: true })
    .click()
  await expect(panel).toContainText("Revoked — its requests are refused")

  const refused = await request.get(`${api}/tasks/`, {
    headers: { Authorization: `Bearer ${first}` },
  })
  expect(refused.status()).toBe(401)

  await panel.getByRole("button", { name: "Issue new token" }).click()
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
  await storeTokenAndClose(secondDialog)

  await expect(panel).toContainText("Working")
  await expect(panel).toContainText("Never used")
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
    const field = page.getByRole("textbox", { name: "Project name" })
    await field.fill(name)
    await field.press("Enter")
    await expect(page.getByRole("dialog", { name })).toBeVisible()
    await page.keyboard.press("Escape")
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
  await storeTokenAndClose(tokenDialog)
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

  // Narrowed to Docs, renamed, and able to create nothing any more — each
  // change saving on its own, in the panel.
  await page.getByRole("row", { name: "Open Changelog agent" }).click()
  const panel = page.getByRole("dialog", { name: "Changelog agent" })
  const billingBox = panel.getByRole("checkbox", { name: "Billing" })
  await expect(billingBox).toBeChecked()
  await billingBox.click()
  await expect(billingBox).not.toBeChecked()
  const createTasks = panel.getByRole("checkbox", { name: "Create tasks" })
  await createTasks.click()
  await expect(createTasks).not.toBeChecked()
  // Renaming last: the panel is announced by the record's name, and the
  // record's name is what is being changed.
  const name = panel.getByRole("textbox", { name: "Bot name" })
  await name.fill("Docs agent")
  await name.press("Enter")
  await page.keyboard.press("Escape")

  const row = page.getByRole("row", { name: "Open Docs agent" })
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

  await row.click()
  await page
    .getByRole("dialog", { name: "Docs agent", exact: true })
    .getByRole("button", { name: "Delete bot user" })
    .click()
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
