import { expect, type Page, test } from "@playwright/test"
import { isoDay } from "../src/lib/dates"
import { newUser, userApi } from "./utils/account"
import { taskLine } from "./utils/tasks"

test.use({ storageState: { cookies: [], origins: [] } })

/** A bot user with a token, scoped to one project. */
async function seedBot(page: Page, name: string, projectId: string) {
  const api = await userApi(page)
  const bot = await api.create("/bot-users/", {
    name,
    scope: {
      project_ids: [projectId],
      permissions: { read_tasks: true, update_tasks: true },
    },
  })
  const { token } = await api.create(`/bot-users/${bot.id}/token`)
  return { ...bot, token } as { id: string; token: string }
}

/** The bot user puts a task in the owner's hands, as the API asks (ADR-0008). */
async function handOver(
  page: Page,
  bot: { token: string },
  taskId: string,
  ownerId: string,
) {
  const api = await userApi(page)
  const handed = await page.request.patch(`${api.url}/tasks/${taskId}`, {
    headers: { Authorization: `Bearer ${bot.token}` },
    data: { status: "review", assignee_id: ownerId },
  })
  expect(handed.ok()).toBe(true)
}

test("A task line names its assignee, before the project, and nobody when unassigned", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const me = await (await api.get("/users/me")).json()
  const project = await api.create("/projects/", { name: "Releases" })
  const bot = await seedBot(page, "release-bot", project.id)
  await api.create("/tasks/", {
    title: "Mine",
    status: "todo",
    project_id: project.id,
    assignee_id: me.id,
    tags: ["web"],
  })
  await api.create("/tasks/", {
    title: "On the bot",
    status: "in_progress",
    project_id: project.id,
    assignee_id: bot.id,
  })
  const handed = await api.create("/tasks/", {
    title: "Finished by the bot",
    status: "in_progress",
    project_id: project.id,
    assignee_id: bot.id,
  })
  await handOver(page, bot, handed.id, me.id)
  await api.create("/tasks/", { title: "Nobody's", project_id: project.id })

  await page.goto("/tasks")

  // After the tags, before the project.
  await expect(taskLine(page, "Mine")).toContainText(
    /Tag:\s*web.*Assigned to:\s*you.*Project:\s*Releases/,
  )
  await expect(taskLine(page, "On the bot")).toContainText(
    /Assigned to:\s*release-bot.*Project:\s*Releases/,
  )
  await expect(taskLine(page, "Finished by the bot")).toContainText(
    /Handed over by:\s*release-bot → you.*Project:\s*Releases/,
  )
  await expect(taskLine(page, "Nobody's")).not.toContainText(
    /Assigned to|Handed over by/,
  )
})

test("A deleted bot user is still named on its tasks and its hand-overs", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const me = await (await api.get("/users/me")).json()
  const project = await api.create("/projects/", { name: "Releases" })
  const bot = await seedBot(page, "old-bot", project.id)
  await api.create("/tasks/", {
    title: "Left with it",
    status: "in_progress",
    project_id: project.id,
    assignee_id: bot.id,
  })
  const handed = await api.create("/tasks/", {
    title: "Handed over by it",
    status: "in_progress",
    project_id: project.id,
    assignee_id: bot.id,
  })
  await handOver(page, bot, handed.id, me.id)
  expect((await api.delete(`/bot-users/${bot.id}`)).ok()).toBe(true)

  await page.goto("/tasks")

  await expect(taskLine(page, "Left with it")).toContainText(
    /Assigned to:\s*old-bot/,
  )
  await expect(taskLine(page, "Handed over by it")).toContainText(
    /Handed over by:\s*old-bot → you/,
  )
})

test("The day page names the hand-over, and a subtask line names its bot user once", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const me = await (await api.get("/users/me")).json()
  const project = await api.create("/projects/", { name: "Releases" })
  const bot = await seedBot(page, "release-bot", project.id)
  const handed = await api.create("/tasks/", {
    title: "Check the redirect map",
    status: "in_progress",
    project_id: project.id,
    assignee_id: bot.id,
  })
  await handOver(page, bot, handed.id, me.id)
  const parent = await api.create("/tasks/", {
    title: "Migrate the pages",
    status: "todo",
    project_id: project.id,
    assignee_id: me.id,
  })
  await api.create("/tasks/", {
    title: "Redirect the old URLs",
    parent_id: parent.id,
    assignee_id: bot.id,
    due_date: isoDay(new Date()),
  })

  await page.goto("/")
  const review = page
    .locator("section")
    .filter({ has: page.getByRole("heading", { level: 3, name: "Review" }) })
    // The outermost match is the whole panel; the last is the group.
    .last()
  await expect(review).toContainText(
    /Handed over by:\s*release-bot → you.*Project:\s*Releases/,
  )

  await page.goto(`/tasks?task=${parent.id}`)
  const subtasks = page
    .getByRole("complementary", { name: "Migrate the pages" })
    .getByRole("region", { name: "Subtasks" })
  const line = subtasks
    .getByRole("listitem")
    .filter({ hasText: "Redirect the old URLs" })
  await expect(line).toContainText(/Today.*Assigned to:\s*release-bot/)
  await expect(line.getByText("release-bot")).toHaveCount(1)
})
