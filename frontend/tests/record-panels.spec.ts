import { expect, type Page, test } from "@playwright/test"
import { createUser } from "./utils/privateApi.ts"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

/** A user of this test's own: the suite shares a database with development. */
async function newUser(page: Page) {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await logInUser(page, email, password)
}

async function api(page: Page) {
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  return {
    url: `${process.env.VITE_API_URL}/api/v1`,
    headers: { Authorization: `Bearer ${token}` },
  }
}

/**
 * A record's row, by the name it says it opens: two tables can be on one
 * screen, and a task's row carries its project's name too.
 */
const row = (page: Page, name: string) =>
  page.getByRole("row", { name: `Open ${name}` })

test("A project is read, renamed and archived in its own panel", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers } = await api(page)
  const project = await (
    await page.request.post(`${url}/projects/`, {
      headers,
      data: { name: "Kitchen rebuild" },
    })
  ).json()
  await page.request.post(`${url}/tasks/`, {
    headers,
    data: { title: "Measure the alcove", project_id: project.id },
  })

  await page.goto("/projects")
  await row(page, "Kitchen rebuild").click()

  const panel = page.getByRole("dialog", { name: "Kitchen rebuild" })
  await expect(panel).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`project=${project.id}`))
  await expect(panel.getByRole("link", { name: "1 task" })).toBeVisible()

  // Renaming is typing in the name, and the list behind it keeps up.
  const name = panel.getByRole("textbox", { name: "Project name" })
  await name.fill("Kitchen refit")
  await name.press("Enter")
  await page.keyboard.press("Escape")
  await expect(row(page, "Kitchen refit")).toBeVisible()

  // Archiving is a property of the project, read where it is changed.
  await row(page, "Kitchen refit").click()
  await page
    .getByRole("dialog", { name: "Kitchen refit" })
    .getByRole("button", { name: "Archive" })
    .click()
  await expect(page.getByText("moved to the archive")).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(row(page, "Kitchen refit")).toHaveCount(0)

  await page.goto("/archive")
  await expect(row(page, "Kitchen refit")).toBeVisible()
  await row(page, "Kitchen refit").click()
  await page
    .getByRole("dialog", { name: "Kitchen refit" })
    .getByRole("button", { name: "Unarchive" })
    .click()
  await expect(page.getByText("is back in your projects")).toBeVisible()
})

test("A panel opens on reload and from a link the list would exclude", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers } = await api(page)
  const project = await (
    await page.request.post(`${url}/projects/`, {
      headers,
      data: { name: "Old house" },
    })
  ).json()
  expect(
    (
      await page.request.post(`${url}/projects/${project.id}/archive`, {
        headers,
      })
    ).ok(),
  ).toBe(true)

  // The live list excludes it; its own address still opens it.
  await page.goto(`/projects?project=${project.id}`)
  const panel = page.getByRole("dialog", { name: "Old house" })
  await expect(panel).toBeVisible()
  await expect(panel.getByRole("button", { name: "Unarchive" })).toBeVisible()
  await expect(row(page, "Old house")).toHaveCount(0)

  await page.reload()
  await expect(page.getByRole("dialog", { name: "Old house" })).toBeVisible()
})

test("The Inbox says what cannot be done to it", async ({ page }) => {
  await newUser(page)

  await page.goto("/projects")
  await row(page, "Inbox").click()

  const panel = page.getByRole("dialog", { name: "Inbox" })
  await expect(panel).toContainText(
    "The Inbox is always in use, so it is never archived or renamed",
  )
  await expect(
    panel.getByRole("textbox", { name: "Project name" }),
  ).toHaveCount(0)
  await expect(
    panel.getByRole("button", { name: "Delete project" }),
  ).toHaveCount(0)
})

test("A tag is renamed and deleted from its panel", async ({ page }) => {
  await newUser(page)
  const { url, headers } = await api(page)
  await page.request.post(`${url}/tasks/`, {
    headers,
    data: { title: "Buy stamps", tags: ["errnds"] },
  })

  await page.goto("/tags")
  await row(page, "errnds").click()
  const panel = page.getByRole("dialog", { name: "errnds" })
  const name = panel.getByRole("textbox", { name: "Tag name" })
  await name.fill("errands")
  await name.press("Enter")
  await page.keyboard.press("Escape")
  await expect(row(page, "errands")).toBeVisible()

  // Deleting says what it takes with it, first.
  await row(page, "errands").click()
  await page
    .getByRole("dialog", { name: "errands" })
    .getByRole("button", { name: "Delete tag" })
    .click()
  const confirm = page.getByRole("dialog", { name: /Delete the tag/ })
  await expect(confirm).toContainText("It will be taken off 1 task.")
  await confirm.getByRole("button", { name: "Delete", exact: true }).click()
  await expect(page.getByText("was deleted")).toBeVisible()
  await expect(row(page, "errands")).toHaveCount(0)

  // And it is off the task that carried it.
  await page.goto("/tasks")
  await expect(row(page, "Buy stamps")).not.toContainText("errands")
})

test("A bot user's scope and permissions each save on their own", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers } = await api(page)
  const project = await (
    await page.request.post(`${url}/projects/`, {
      headers,
      data: { name: "Support queue" },
    })
  ).json()
  const bot = await (
    await page.request.post(`${url}/bot-users/`, {
      headers,
      data: {
        name: "Triage agent",
        scope: { project_ids: [], permissions: { read_tasks: true } },
      },
    })
  ).json()

  await page.goto("/bots")
  await row(page, "Triage agent").click()
  const panel = page.getByRole("dialog", { name: "Triage agent" })
  await expect(panel.getByRole("textbox", { name: "Bot name" })).toHaveValue(
    "Triage agent",
  )

  const inScope = panel.getByRole("checkbox", { name: "Support queue" })
  await inScope.click()
  await expect(inScope).toBeChecked()
  const createTasks = panel.getByRole("checkbox", { name: "Create tasks" })
  await createTasks.click()
  await expect(createTasks).toBeChecked()

  // No Save anywhere: what the panel shows is what the API holds.
  await expect(panel.getByRole("button", { name: "Save" })).toHaveCount(0)
  await expect
    .poll(async () => {
      const read = await page.request.get(`${url}/bot-users/${bot.id}`, {
        headers,
      })
      const current = await read.json()
      return {
        projects: current.scope.project_ids,
        create: current.scope.permissions.create_tasks,
      }
    })
    .toEqual({ projects: [project.id], create: true })

  await page.reload()
  const reopened = page.getByRole("dialog", { name: "Triage agent" })
  await expect(
    reopened.getByRole("checkbox", { name: "Support queue" }),
  ).toBeChecked()
})

test("A token is issued and revoked from the bot user's panel", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers } = await api(page)
  await page.request.post(`${url}/bot-users/`, {
    headers,
    data: { name: "Nightly sync", scope: { project_ids: [], permissions: {} } },
  })

  await page.goto("/bots")
  await row(page, "Nightly sync").click()
  const panel = page.getByRole("dialog", { name: "Nightly sync" })
  await expect(panel).toContainText("No token issued")

  await panel.getByRole("button", { name: "Issue token" }).click()
  await page
    .getByRole("dialog", { name: /Issue token for Nightly sync/ })
    .getByRole("button", { name: "Issue" })
    .click()

  // The reveal is its own deliberate step, opened over the panel: it shows
  // the token once and says so. (Guarding it against a stray dismissal is
  // semaputnik/taskly#77, which is still open.)
  const reveal = page.getByRole("dialog", { name: "Token for Nightly sync" })
  await expect(reveal).toContainText("It won't be shown again")
  const token = await reveal
    .getByRole("textbox", { name: "Bot token" })
    .inputValue()
  expect(token).toMatch(/^taskly_bot_/)
  await expect(reveal.getByRole("button", { name: "Copy" })).toBeVisible()
  await reveal.getByRole("button", { name: "Done" }).click()
  await expect(reveal).toBeHidden()

  await expect(panel).toContainText("Active")
  await panel.getByRole("button", { name: "Revoke" }).click()
  await page
    .getByRole("dialog", { name: /Revoke the token/ })
    .getByRole("button", { name: "Revoke", exact: true })
    .click()
  await expect(page.getByText("was revoked")).toBeVisible()
  await expect(panel).toContainText("Revoked")
  // The bot user itself is untouched.
  await expect(panel.getByRole("textbox", { name: "Bot name" })).toHaveValue(
    "Nightly sync",
  )
})

test("Creating a project or a tag opens the new record's panel", async ({
  page,
}) => {
  await newUser(page)

  await page.goto("/projects")
  await page.getByRole("button", { name: "Add Project" }).click()
  const projectName = page.getByRole("textbox", { name: "Project name" })
  await expect(projectName).toBeFocused()
  await projectName.fill("Move house")
  await projectName.press("Enter")
  await expect(page.getByRole("dialog", { name: "Move house" })).toBeVisible()
  await expect(page).toHaveURL(/project=[0-9a-f-]{36}/)
  await page.keyboard.press("Escape")
  await expect(row(page, "Move house")).toBeVisible()

  await page.goto("/tags")
  await page.getByRole("button", { name: "Add Tag" }).click()
  const tagName = page.getByRole("textbox", { name: "Tag name" })
  await tagName.fill("packing")
  await tagName.press("Enter")
  await expect(page.getByRole("dialog", { name: "packing" })).toBeVisible()
  await expect(page).toHaveURL(/tag_id=[0-9a-f-]{36}/)
})

test("Creating a bot user still asks for its scope up front", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers } = await api(page)
  await page.request.post(`${url}/projects/`, {
    headers,
    data: { name: "Releases" },
  })

  await page.goto("/bots")
  await page.getByRole("button", { name: "Add Bot" }).click()
  const dialog = page.getByRole("dialog", { name: "Add Bot" })
  await dialog.getByPlaceholder("Bot name").fill("Release agent")
  await dialog.getByRole("checkbox", { name: "Releases" }).check()
  await dialog.getByRole("button", { name: "Create and issue token" }).click()

  await page
    .getByRole("dialog", { name: "Token for Release agent" })
    .getByRole("button", { name: "Done" })
    .click()
  await expect(row(page, "Release agent")).toContainText("Releases")
})

test("No record carries a three-dot menu, and rows open from the keyboard", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers } = await api(page)
  await page.request.post(`${url}/projects/`, {
    headers,
    data: { name: "Garden" },
  })
  await page.request.post(`${url}/tasks/`, {
    headers,
    data: { title: "Plant the beds", tags: ["outdoors"] },
  })
  await page.request.post(`${url}/bot-users/`, {
    headers,
    data: { name: "Watering bot", scope: { project_ids: [], permissions: {} } },
  })

  for (const path of ["/tasks", "/projects", "/tags", "/bots", "/archive"]) {
    await page.goto(path)
    await expect(page.getByRole("button", { name: /^Actions/ })).toHaveCount(0)
    await expect(page.locator(".lucide-ellipsis-vertical")).toHaveCount(0)
  }

  // A row is a control: it takes focus and answers Enter.
  await page.goto("/projects")
  await row(page, "Garden").focus()
  await page.keyboard.press("Enter")
  await expect(page.getByRole("dialog", { name: "Garden" })).toBeVisible()
})

test("A refused rename keeps the name that was typed", async ({ page }) => {
  await newUser(page)
  const { url, headers } = await api(page)
  for (const name of ["errands", "weekend"]) {
    await page.request.post(`${url}/tags/`, { headers, data: { name } })
  }

  await page.goto("/tags")
  await row(page, "weekend").click()
  const panel = page.getByRole("dialog", { name: "weekend" })
  const name = panel.getByRole("textbox", { name: "Tag name" })
  await name.fill("errands")
  await name.press("Enter")

  // The API refuses a name already in use, and says so; the typed name stays
  // where the reader left it rather than snapping back.
  await expect(page.getByText("You already have a tag named")).toBeVisible()
  await expect(name).toHaveValue("errands")

  // And nothing was renamed behind it.
  await page.keyboard.press("Escape")
  await expect(row(page, "weekend")).toBeVisible()
})
