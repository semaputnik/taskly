import { expect, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"
import { botColumn, botLine, createBotInColumn, openBot } from "./utils/bots"
import { randomEmail } from "./utils/random"
import { storeSecretAndClose } from "./utils/secretDialog"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("A bot user is drafted in the column and its token is shown once", async ({
  page,
  request,
}) => {
  const email = randomEmail()
  await logInUser(page, email)

  await page.goto("/projects")
  await page.getByRole("button", { name: "New project" }).click()
  const projectName = page.getByRole("textbox", { name: "Project name" })
  await projectName.fill("Support queue")
  await projectName.press("Enter")
  await expect(
    page.getByRole("complementary", { name: "Support queue" }),
  ).toBeVisible()
  await page.keyboard.press("Escape")

  await page.goto("/bots")
  await expect(page.getByRole("heading", { name: "Bots" })).toBeVisible()
  await page.getByRole("button", { name: "New bot user" }).click()

  // The draft is the column, with nothing saved yet.
  const draft = page.getByRole("complementary", { name: "New bot user" })
  await expect(draft).toContainText("Not saved yet")
  await expect(
    draft.getByRole("button", { name: "Create and issue token" }),
  ).toBeDisabled()
  await draft.getByRole("textbox", { name: "Bot name" }).fill("Triage agent")
  await draft.getByRole("checkbox", { name: "Support queue" }).check()
  await expect(
    draft.getByRole("checkbox", { name: "Read tasks" }),
  ).toBeChecked()
  await draft.getByRole("button", { name: "Create and issue token" }).click()

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

  await storeSecretAndClose(dialog)

  // Created, the draft has become the record, at the record's address.
  const column = botColumn(page, "Triage agent")
  await expect(column).toContainText("Working")
  await expect(page).toHaveURL(/bot=/)
  const line = botLine(page, "Triage agent")
  await expect(line).toContainText("Working")
  await expect(line).toContainText("Support queue")
  await expect(line).toContainText("reads")

  // Once the dialog is gone, nothing can show the token again. The request
  // above used it, which the column reports.
  await page.reload()
  await expect(column).toContainText("never expires")
  await expect(column).not.toContainText("Never used")
  expect(await page.content()).not.toContain(token)
})

test("A draft that is closed leaves nothing behind", async ({ page }) => {
  await newUser(page)
  const api = await userApi(page)

  await page.goto("/bots")
  await page.getByRole("button", { name: "New bot user" }).click()
  const draft = page.getByRole("complementary", { name: "New bot user" })
  await draft.getByRole("textbox", { name: "Bot name" }).fill("Never made")
  await page.keyboard.press("Escape")
  await expect(draft).toBeHidden()

  const bots = await (await api.get("/bot-users/")).json()
  expect(bots.count).toBe(0)
})

test("A token is revoked and a new one issued with an expiry", async ({
  page,
  request,
}) => {
  await newUser(page)
  const api = `${process.env.VITE_API_URL}/api/v1`

  await page.goto("/bots")
  await page.getByRole("button", { name: "New bot user" }).click()
  const draft = page.getByRole("complementary", { name: "New bot user" })
  await draft.getByRole("textbox", { name: "Bot name" }).fill("Nightly sync")
  await draft.getByRole("button", { name: "Create and issue token" }).click()
  const firstDialog = page.getByRole("dialog", {
    name: "Token for Nightly sync",
  })
  const first = await firstDialog
    .getByRole("textbox", { name: "Bot token" })
    .inputValue()
  await storeSecretAndClose(firstDialog)

  const panel = botColumn(page, "Nightly sync")
  await panel.getByRole("button", { name: "Revoke" }).click()
  await page
    .getByRole("dialog", { name: "Revoke the token for Nightly sync?" })
    .getByRole("button", { name: "Revoke", exact: true })
    .click()
  await expect(panel).toContainText("Revoked")
  await expect(panel).toContainText("its requests are refused")
  await expect(botLine(page, "Nightly sync")).toContainText("Revoked")

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
  await page.getByRole("dialog").locator('input[type="date"]').fill(date)
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
  await storeSecretAndClose(secondDialog)

  await expect(panel).toContainText("Working")
  await expect(panel).toContainText("expires")
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
  await newUser(page)
  const api = await userApi(page)

  await page.goto("/projects")
  for (const name of ["Docs", "Billing"]) {
    await page.getByRole("button", { name: "New project" }).click()
    const field = page.getByRole("textbox", { name: "Project name" })
    await field.fill(name)
    await field.press("Enter")
    await expect(page.getByRole("complementary", { name })).toBeVisible()
    await page.keyboard.press("Escape")
    await expect(page.locator("[data-record-column]")).toBeHidden()
  }

  await page.goto("/bots")
  const token = await createBotInColumn(page, {
    name: "Changelog agent",
    projects: ["Docs", "Billing"],
    permissions: ["Create tasks"],
  })
  const asBot = { Authorization: `Bearer ${token}` }
  const botId = new URL(page.url()).searchParams.get("bot")
  expect(botId).not.toBeNull()

  // The bot works in Billing while Billing is still in its scope.
  const projects = await (
    await request.get(`${api.url}/projects/`, { headers: asBot })
  ).json()
  const billing = projects.data.find(
    (p: { name: string }) => p.name === "Billing",
  )
  const created = await request.post(`${api.url}/tasks/`, {
    headers: asBot,
    data: { title: "Draft the invoice notes", project_id: billing.id },
  })
  expect(created.ok()).toBe(true)
  const task = await created.json()
  // And a task of the user's own is handed to it.
  await api.create("/tasks/", {
    title: "Check the footers",
    assignee_id: botId,
  })

  // Narrowed to Docs, renamed, and able to create nothing any more — each
  // change saving on its own, in the column.
  const panel = botColumn(page, "Changelog agent")
  const billingBox = panel.getByRole("checkbox", { name: "Billing" })
  await expect(billingBox).toBeChecked()
  await billingBox.click()
  await expect(billingBox).not.toBeChecked()
  await expect(panel).toContainText("1 of 3")
  const createTasks = panel.getByRole("checkbox", { name: "Create tasks" })
  await createTasks.click()
  await expect(createTasks).not.toBeChecked()
  // Renaming last: the column is announced by the record's name, and the
  // record's name is what is being changed.
  const name = panel.getByRole("textbox", { name: "Bot name" })
  await name.fill("Docs agent")
  await name.press("Enter")
  await page.keyboard.press("Escape")

  const line = botLine(page, "Docs agent")
  await expect(line).toContainText("Docs")
  await expect(line).not.toContainText("Billing")
  await expect(line).toContainText("reads")
  await expect(line).not.toContainText("creates")

  // The same token's very next request is held to the new scope.
  const outside = await request.get(`${api.url}/tasks/${task.id}`, {
    headers: asBot,
  })
  expect(outside.status()).toBe(403)
  expect((await outside.json()).detail.code).toBe("outside_scope")

  await openBot(page, "Docs agent")
  await botColumn(page, "Docs agent")
    .getByRole("button", { name: "Delete bot user" })
    .click()
  await page
    .getByRole("dialog", { name: "Delete Docs agent?" })
    .getByRole("button", { name: "Delete" })
    .click()
  await expect(page.getByText("“Docs agent” was deleted")).toBeVisible()

  // Off the list of bot users, and in its own quiet section with what it is
  // still named on.
  await expect(
    page.getByRole("list", { name: "Bot users", exact: true }),
  ).toHaveCount(0)
  const deleted = page.getByRole("list", { name: "Deleted bot users" })
  await expect(deleted).toContainText("Docs agent")
  await expect(deleted).toContainText("deleted")
  await expect(deleted).toContainText("still named on 1 task and in the log")

  const refused = await request.get(`${api.url}/tasks/`, { headers: asBot })
  expect(refused.status()).toBe(401)

  // What it did is still in the log under its name.
  await page.goto("/activity")
  await expect(
    page.getByRole("listitem").filter({ hasText: "Draft the invoice notes" }),
  ).toContainText("Docs agent")
})

test("A deleted bot user is read-only in its column", async ({ page }) => {
  await newUser(page)
  const api = await userApi(page)
  const bot = await api.create("/bot-users/", {
    name: "Old backup",
    scope: { project_ids: [], permissions: { read_tasks: true } },
  })
  await api.create("/tasks/", {
    title: "Still on the record",
    assignee_id: bot.id,
  })
  expect((await api.delete(`/bot-users/${bot.id}`)).ok()).toBe(true)

  await page.goto("/bots")
  await openBot(page, "Old backup")
  const column = botColumn(page, "Old backup")
  await expect(column).toContainText(/Bot user.?Deleted/)
  await expect(column).toContainText("This bot user was deleted")
  await expect(column).toContainText("cannot be undone")
  // What it was given is still read, as the user's own tasks.
  await expect(
    column.getByRole("list", { name: "Tasks assigned to Old backup" }),
  ).toContainText("Still on the record")
  // Nothing about it changes again: no field, no scope to tick, no token
  // control, no way to delete it twice.
  await expect(column.getByRole("textbox")).toHaveCount(0)
  await expect(column.getByRole("region", { name: "Projects" })).toHaveCount(0)
  await expect(column.getByRole("region", { name: "Permissions" })).toHaveCount(
    0,
  )
  await expect(
    column.getByRole("button", { name: /token|Revoke/i }),
  ).toHaveCount(0)
  await expect(
    column.getByRole("button", { name: "Delete bot user" }),
  ).toHaveCount(0)
})

test("The page counts the bot users and their week", async ({ page }) => {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Shared" })
  const scope = {
    project_ids: [project.id],
    permissions: { create_tasks: true },
  }
  const working = await api.create("/bot-users/", { name: "Alpha", scope })
  const { token } = await api.create(`/bot-users/${working.id}/token`)
  await api.create("/bot-users/", { name: "Beta", scope })
  const created = await page.request.post(`${api.url}/tasks/`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { title: "From Alpha", project_id: project.id },
  })
  expect(created.ok()).toBe(true)

  await page.goto("/bots")
  const sentence = page.locator("main p").first()
  await expect(sentence).toContainText("2 bot users.")
  await expect(sentence).toContainText("1 working, 1 without a token.")
  await expect(sentence).toContainText("They made 1 change this week.")
  await expect(botLine(page, "Beta")).toContainText("No token")
  await expect(botLine(page, "Beta")).toContainText("never used")
})

test("↓ and ↑ walk the bot users, and Escape closes the column", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const scope = { project_ids: [], permissions: {} }
  await api.create("/bot-users/", { name: "First bot", scope })
  await api.create("/bot-users/", { name: "Second bot", scope })

  await page.goto("/bots")
  await openBot(page, "First bot")
  await expect(botColumn(page, "First bot")).toContainText("1 of 2")
  await expect(botLine(page, "First bot")).toHaveClass(/row-tint/)

  await page.keyboard.press("ArrowDown")
  await expect(botColumn(page, "Second bot")).toContainText("2 of 2")
  await expect(botLine(page, "Second bot")).toHaveClass(/row-tint/)
  await page.keyboard.press("ArrowUp")
  await expect(botColumn(page, "First bot")).toBeVisible()

  // Walking replaces the visit, so one Escape leaves the column.
  await page.keyboard.press("Escape")
  await expect(page.locator("[data-record-column]")).toHaveCount(0)
})

test.describe("on a phone", () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test("the lines fit the screen and the column takes all of it", async ({
    page,
  }) => {
    await newUser(page)
    const api = await userApi(page)
    const project = await api.create("/projects/", {
      name: "A project with a rather long name",
    })
    await api.create("/bot-users/", {
      name: "inbox-triage-with-a-long-name",
      scope: {
        project_ids: [project.id],
        permissions: {
          read_tasks: true,
          update_tasks: true,
          add_comments: true,
        },
      },
    })

    await page.goto("/bots")
    const line = botLine(page, "inbox-triage-with-a-long-name")
    await expect(line).toBeVisible()
    const fits = () =>
      page.evaluate(
        () =>
          document.documentElement.scrollWidth <=
          document.documentElement.clientWidth,
      )
    expect(await fits()).toBe(true)

    await openBot(page, "inbox-triage-with-a-long-name")
    const column = botColumn(page, "inbox-triage-with-a-long-name")
    await expect(column).toBeVisible()
    const box = await column.boundingBox()
    expect(box?.width).toBeCloseTo(375, 0)
    // The scope's checkboxes stack to one column at this width.
    const [first, second] = await Promise.all([
      column.getByRole("checkbox", { name: "Read tasks" }).boundingBox(),
      column.getByRole("checkbox", { name: "Create tasks" }).boundingBox(),
    ])
    expect(second?.y).toBeGreaterThan((first?.y ?? 0) + 10)
  })
})
