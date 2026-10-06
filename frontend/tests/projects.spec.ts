import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"
import { taskLine, taskLines } from "./utils/tasks"

test.use({ storageState: { cookies: [], origins: [] } })

/** A project's name on its line: the link that opens its column. */
const projectLink = (page: Page, name: string) =>
  page.getByRole("main").getByRole("link", { name, exact: true })

/** The line that has this project's name as its link. */
const hasName = (page: Page, name: string) => ({
  has: page.getByRole("link", { name, exact: true }),
})

const liveProjects = (page: Page) =>
  page.getByRole("list", { name: "Projects", exact: true })

const archivedProjects = (page: Page) =>
  page.getByRole("list", { name: "Archived projects" })

/** One project with a few tasks in it, a bot user at work there, and another project. */
async function scene(page: Page) {
  const api = await userApi(page)
  const website = await api.create("/projects/", {
    name: "Website relaunch",
    description: "Moving the marketing pages off the old template.",
  })
  const home = await api.create("/projects/", { name: "Home" })
  await api.create("/bot-users/", {
    name: "release-bot",
    scope: {
      project_ids: [website.id],
      permissions: { read_tasks: true },
    },
  })
  const make = (project: { id: string }, title: string, extra = {}) =>
    api.create("/tasks/", { title, project_id: project.id, ...extra })
  await make(website, "Renew the domain", { due_date: "2000-01-01" })
  await make(website, "Check the redirect map", { status: "review" })
  await make(website, "Rewrite the pricing copy")
  await make(website, "Launch announcement", { status: "done" })
  await make(home, "Fix the gate")
  return { api, website, home }
}

test("The Projects page counts, and its open count is one click into the project's tasks", async ({
  page,
}) => {
  await newUser(page)
  const { website } = await scene(page)

  await page.goto("/projects")
  await expect(
    page.getByRole("heading", { name: "Projects", exact: true }),
  ).toBeVisible()
  await expect(page.getByRole("main")).toContainText(
    "3 projects, 4 open tasks. 1 is overdue, in Website relaunch.",
  )

  const line = liveProjects(page)
    .getByRole("listitem")
    .filter(hasName(page, "Website relaunch"))
  await expect(line).toContainText(
    "Moving the marketing pages off the old template.",
  )
  await expect(line).toContainText("1 overdue")
  await expect(line).toContainText("2 in Backlog")
  await expect(line).toContainText("1 in Review")
  await expect(line).toContainText("release-bot works here")

  // The count is the link, and the list it opens is narrowed to the project.
  await line.getByRole("link", { name: /3 open/ }).click()
  await expect(page).toHaveURL(
    new RegExp(`/tasks\\?.*project_id=${website.id}`),
  )
  await expect(taskLine(page, "Renew the domain")).toBeVisible()
  await expect(taskLines(page).getByRole("listitem")).toHaveCount(3)
  await expect(taskLine(page, "Fix the gate")).toHaveCount(0)
})

test("Archived projects are a section of the page, with their kept tasks read-only behind a link", async ({
  page,
}) => {
  await newUser(page)
  const { api, website } = await scene(page)
  expect((await api.post(`/projects/${website.id}/archive`)).ok()).toBe(true)

  await page.goto("/projects")
  await expect(
    liveProjects(page).getByRole("link", { name: "Website relaunch" }),
  ).toHaveCount(0)
  await expect(page.getByRole("heading", { name: "Archived" })).toBeVisible()
  const kept = archivedProjects(page)
    .getByRole("listitem")
    .filter(hasName(page, "Website relaunch"))
  await expect(kept).toContainText("4 tasks kept with it")

  await kept.getByRole("link", { name: /4 tasks/ }).click()
  await expect(page).toHaveURL(new RegExp(`/projects/${website.id}/tasks`))
  await expect(
    page.getByRole("heading", { name: "Website relaunch" }),
  ).toBeVisible()
  // Everything it kept, the finished work too, and nothing to change.
  const lines = page.getByRole("list", {
    name: "Tasks kept in Website relaunch",
  })
  await expect(lines.getByRole("listitem")).toHaveCount(4)
  await expect(lines).toContainText("Launch announcement")
  await expect(page.getByRole("checkbox")).toHaveCount(0)
  await expect(lines.getByRole("link")).toHaveCount(0)
})

test("The old Archive address lands on Projects, and the navigation no longer lists it", async ({
  page,
}) => {
  await newUser(page)

  await page.goto("/archive")
  await expect(page).toHaveURL(/\/projects$/)
  await expect(
    page.getByRole("heading", { name: "Projects", exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole("navigation", { name: "Main" }).getByRole("link", {
      name: "Archive",
    }),
  ).toHaveCount(0)
})

test("A project's column files tasks into it and hands off to the list and the log", async ({
  page,
}) => {
  await newUser(page)
  const { api, website } = await scene(page)
  for (const title of ["Task A", "Task B", "Task C"]) {
    await api.create("/tasks/", { title, project_id: website.id })
  }

  await page.goto("/projects")
  await projectLink(page, "Website relaunch").click()
  const column = page.getByRole("complementary", { name: "Website relaunch" })
  await expect(column).toContainText("6 open · 1 overdue · 1 done")
  await expect(column).toContainText("release-bot")

  // Six open tasks: five as lines, the rest one link away.
  const open = column.getByRole("region", { name: "Open tasks" })
  await expect(
    open
      .getByRole("list", { name: "Open tasks in Website relaunch" })
      .getByRole("listitem"),
  ).toHaveCount(5)
  await expect(
    open.getByRole("link", { name: /1 more in the list/ }),
  ).toBeVisible()

  // The capture line files into the project, whatever page is behind.
  const capture = open.getByRole("combobox", {
    name: "Add a task to Website relaunch",
  })
  await capture.fill("Order the new fonts")
  await capture.press("Enter")
  await expect(
    page.getByText("“Order the new fonts” created in Website relaunch"),
  ).toBeVisible()
  await expect(
    open.getByRole("link", { name: /2 more in the list/ }),
  ).toBeVisible()
  await expect(column).toContainText("7 open")

  await open.getByRole("link", { name: /2 more in the list/ }).click()
  await expect(page).toHaveURL(
    new RegExp(`/tasks\\?.*project_id=${website.id}`),
  )
  await expect(taskLine(page, "Order the new fonts")).toBeVisible()

  // The log, narrowed to the project, from the column's Activity section.
  await page.goto(`/projects?project=${website.id}`)
  await page
    .getByRole("complementary", { name: "Website relaunch" })
    .getByRole("link", { name: /Everything in this project/ })
    .click()
  await expect(page).toHaveURL(
    new RegExp(`/activity\\?.*project_id=${website.id}`),
  )
  await expect(
    page.getByRole("button", { name: "In Website relaunch" }),
  ).toBeVisible()
})

test("A project is drafted in the column, and Delete project names the tasks that go with it", async ({
  page,
}) => {
  await newUser(page)
  const { website } = await scene(page)

  await page.goto("/projects")
  await page.getByRole("button", { name: "New project" }).click()
  const draft = page.getByRole("complementary", { name: "New project" })
  await expect(draft).toContainText("Not saved yet")
  await expect(
    draft.getByRole("button", { name: "Create project" }),
  ).toBeDisabled()
  await draft.getByRole("textbox", { name: "Project name" }).fill("Garden")
  await draft
    .getByRole("textbox", { name: "Project description" })
    .fill("The back beds.")
  await draft.getByRole("button", { name: "Create project" }).click()

  const column = page.getByRole("complementary", { name: "Garden" })
  await expect(column).toContainText("The back beds.")
  await expect(projectLink(page, "Garden")).toBeVisible()

  await page.goto(`/projects?project=${website.id}`)
  await page.getByRole("button", { name: "Delete project" }).click()
  const dialog = page.getByRole("dialog", { name: "Delete Website relaunch?" })
  await expect(dialog).toContainText("Its 4 tasks go with it")
  await dialog.getByRole("button", { name: "Delete", exact: true }).click()
  await expect(projectLink(page, "Website relaunch")).toHaveCount(0)
})

test("The arrow keys walk the projects as listed, and the Inbox is read-only", async ({
  page,
}) => {
  await newUser(page)
  await scene(page)

  await page.goto("/projects")
  await expect(projectLink(page, "Inbox")).toBeVisible()
  const names = await liveProjects(page)
    .getByRole("listitem")
    .getByRole("link")
    .filter({ hasNotText: /open/ })
    .allInnerTexts()
  expect(names.length).toBeGreaterThanOrEqual(3)

  await projectLink(page, names[0]).click()
  const first = page.getByRole("complementary", { name: names[0] })
  await expect(first).toBeVisible()
  await expect(first).toContainText(`1 of ${names.length}`)
  await page.keyboard.press("ArrowDown")
  await expect(
    page.getByRole("complementary", { name: names[1] }),
  ).toBeVisible()
  await page.keyboard.press("ArrowUp")
  await expect(
    page.getByRole("complementary", { name: names[0] }),
  ).toBeVisible()

  await projectLink(page, "Inbox").click()
  const inbox = page.getByRole("complementary", { name: "Inbox" })
  await expect(inbox).toContainText("cannot be renamed, archived or deleted")
  await expect(inbox.getByRole("button", { name: "Archive" })).toHaveCount(0)
  await expect(
    inbox.getByRole("button", { name: "Delete project" }),
  ).toHaveCount(0)
})

test("Enter pressed right after a refusal sends the draft again", async ({
  page,
}) => {
  await newUser(page)

  // The first attempt is refused; the second goes through to the server.
  let refused = false
  await page.route("**/api/v1/projects/", async (route) => {
    if (route.request().method() !== "POST" || refused) return route.continue()
    refused = true
    await route.fulfill({
      status: 422,
      contentType: "application/json",
      body: JSON.stringify({ detail: "That name will not do." }),
    })
  })

  await page.goto("/projects")
  await page.getByRole("button", { name: "New project" }).click()
  const name = page.getByRole("textbox", { name: "Project name" })
  await name.fill("Garden")
  await name.press("Enter")
  await expect.poll(() => refused).toBe(true)

  await name.press("Enter")
  await expect(
    page.getByRole("complementary", { name: "Garden" }),
  ).toBeVisible()
})
