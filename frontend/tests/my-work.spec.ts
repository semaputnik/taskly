import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

/** The In my hands panel on the day page. */
const panel = (page: Page) =>
  page.locator("section").filter({
    has: page.getByRole("heading", { level: 2, name: /In my hands/ }),
  })

/** One of its status groups. */
const group = (page: Page, name: string) =>
  panel(page)
    .locator("section")
    .filter({ has: page.getByRole("heading", { level: 3, name }) })

async function me(api: Awaited<ReturnType<typeof userApi>>): Promise<string> {
  return (await (await api.get("/users/me")).json()).id
}

test("My work shows only the tasks on the reader, grouped by status", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const myId = await me(api)
  const project = await api.create("/projects/", { name: "Research" })
  const bot = await api.create("/bot-users/", {
    name: "Triage agent",
    scope: { project_ids: [project.id], permissions: { read_tasks: true } },
  })
  for (const task of [
    { title: "Wait on the landlord", status: "waiting", assignee_id: myId },
    { title: "Order groceries", status: "todo", assignee_id: myId },
    {
      title: "Pay the rent",
      status: "todo",
      assignee_id: myId,
      priority: "P1",
    },
    { title: "Check the summary", status: "review", assignee_id: myId },
    { title: "Migrate the pages", status: "in_progress", assignee_id: myId },
    { title: "Someday, mine", status: "backlog", assignee_id: myId },
    { title: "Nobody's task", status: "todo" },
    {
      title: "The agent's task",
      status: "in_progress",
      project_id: project.id,
      assignee_id: bot.id,
    },
  ]) {
    await api.create("/tasks/", task)
  }
  await page.goto("/")

  await expect(panel(page).getByRole("heading", { level: 2 })).toHaveText(
    /In my hands\s*5/,
  )
  await expect(panel(page).getByRole("heading", { level: 3 })).toHaveText([
    "In progress",
    "Review",
    "To do",
    "Waiting",
  ])
  await expect(group(page, "In progress")).toContainText("Migrate the pages")
  await expect(group(page, "Review")).toContainText("Check the summary")
  // Highest priority first within a group.
  await expect(group(page, "To do").getByRole("link")).toHaveText([
    "Pay the rent",
    "Order groceries",
  ])
  await expect(group(page, "Waiting")).toContainText("Wait on the landlord")
  for (const elsewhere of [
    "Someday, mine",
    "Nobody's task",
    "The agent's task",
  ]) {
    await expect(panel(page)).not.toContainText(elsewhere)
  }
})

test("A group too long to show hands off to the list narrowed the same way", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const myId = await me(api)
  for (const index of [1, 2, 3, 4]) {
    await api.create("/tasks/", {
      title: `Errand ${index}`,
      status: "todo",
      assignee_id: myId,
    })
  }
  await page.goto("/")

  await group(page, "To do").getByRole("link", { name: "1 more" }).click()
  await expect(page).toHaveURL(/\/tasks\?.*assignee=me/)
  await expect(page.getByText("Status: To do")).toBeVisible()
  await expect(page.getByText("Errand 4")).toBeVisible()
})

test("With nothing on the reader, the panel says so rather than disappearing", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tasks/", { title: "Nobody's task", status: "todo" })
  await page.goto("/")

  await expect(panel(page)).toContainText("Nothing is in your hands right now.")
})

test("A bot user's hand-over is named, and Close it closes the task with an Undo", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const myId = await me(api)
  const project = await api.create("/projects/", { name: "Research" })
  const bot = await api.create("/bot-users/", {
    name: "research-agent",
    scope: {
      project_ids: [project.id],
      permissions: { read_tasks: true, update_tasks: true },
    },
  })
  const { token } = await api.create(`/bot-users/${bot.id}/token`)
  const task = await api.create("/tasks/", {
    title: "Summarise the trackers",
    status: "in_progress",
    project_id: project.id,
    assignee_id: bot.id,
  })
  // The hand-over: the bot user finishes, and puts the task in the owner's
  // hands as the API documentation asks.
  const handed = await page.request.patch(`${api.url}/tasks/${task.id}`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { status: "review", assignee_id: myId },
  })
  expect(handed.ok()).toBe(true)
  await page.goto("/")

  const review = group(page, "Review")
  await expect(review).toContainText(
    /research-agent finished this at \d{1,2}:\d\d(\s?[AP]M)? and handed it to you/i,
  )
  await review
    .getByRole("button", { name: "Close it: Summarise the trackers" })
    .click()

  await expect(page.getByText("“Summarise the trackers” done")).toBeVisible()
  await expect(panel(page)).not.toContainText("Summarise the trackers")

  await page.getByRole("button", { name: "Undo" }).click()
  // Undoing a close returns the task to To do, as it always does.
  await expect(group(page, "To do")).toContainText("Summarise the trackers")
})
