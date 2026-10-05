import { expect, type Locator, type Page, test } from "@playwright/test"
import { isoDay } from "../src/lib/dates"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

/** A local calendar day this many days from today, as the API takes it. */
function day(offset: number): string {
  const date = new Date()
  date.setDate(date.getDate() + offset)
  return isoDay(date)
}

const band = (page: Page, name: RegExp) =>
  page.locator("section").filter({ has: page.getByRole("heading", { name }) })

async function seed(
  page: Page,
  tasks: { title: string; status?: string; due_date?: string }[],
) {
  const api = await userApi(page)
  for (const task of tasks) await api.create("/tasks/", task)
}

test("The bands take every open status but Waiting, and the sentence counts them", async ({
  page,
}) => {
  await newUser(page)
  await seed(page, [
    { title: "Pay the rent", due_date: day(-2), status: "todo" },
    { title: "File the taxes", due_date: day(-1), status: "backlog" },
    { title: "Chase the plumber", due_date: day(-3), status: "waiting" },
    { title: "Order groceries", due_date: day(0), status: "in_progress" },
    { title: "Check the summary", due_date: day(0), status: "review" },
    { title: "Hear back today", due_date: day(0), status: "waiting" },
    { title: "Rewrite the copy", due_date: day(3) },
    { title: "Book the dentist", due_date: day(5), status: "backlog" },
    { title: "Someday", due_date: day(20) },
  ])
  // A late task on a bot user, filed by the bot user itself: the bands are
  // not narrowed to the reader as assignee, and the filing is its change.
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Support queue" })
  const bot = await api.create("/bot-users/", {
    name: "Triage agent",
    scope: { project_ids: [project.id], permissions: { create_tasks: true } },
  })
  const { token } = await api.create(`/bot-users/${bot.id}/token`)
  const filed = await page.request.post(`${api.url}/tasks/`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      title: "Answer the refund",
      project_id: project.id,
      due_date: day(-1),
      assignee_id: bot.id,
    },
  })
  expect(filed.ok()).toBe(true)
  await page.goto("/")

  const overdue = band(page, /^Overdue/)
  await expect(overdue.getByRole("heading")).toHaveText(/^Overdue\s*3$/)
  await expect(overdue).toContainText("Answer the refund")
  await expect(overdue).toContainText("Pay the rent")
  // Backlog is open like any other status: its due date counts.
  await expect(overdue).toContainText("File the taxes")
  await expect(overdue).not.toContainText("Chase the plumber")

  const today = band(page, /^Due today/)
  await expect(today.getByRole("heading")).toHaveText(/^Due today\s*2$/)
  await expect(today).toContainText("Order groceries")
  await expect(today).toContainText("Check the summary")
  await expect(today).not.toContainText("Hear back today")

  // Waiting has no band of its own on the day page.
  await expect(page.getByRole("heading", { name: /Waiting/ })).toHaveCount(0)

  await expect(page.getByText("5 need you.")).toBeVisible()
  // A first visit counts every change the bot users have made. The Changes
  // log counts the reader's own seeding too, so the sentence names the bot
  // users' share of the very figure the log's heading shows.
  const logHeading = page.getByRole("heading", { name: /^Changes/ })
  await expect(logHeading).toHaveText(/^Changes\s*\d+/)
  const logCount = (await logHeading.innerText()).match(/\d+/)?.[0]
  await expect(
    page.getByText(
      `Your bot users have made 1 of the ${logCount} changes so far.`,
    ),
  ).toBeVisible()

  const week = page.getByRole("link", { name: /2 more due later this week/ })
  await expect(week).toBeVisible()
  await week.click()
  await expect(page).toHaveURL(/\/tasks/)
  await expect(
    page.getByText("Status: Backlog, To do, In progress, Review"),
  ).toBeVisible()
})

test("A band too long to show hands off to the list narrowed the same way", async ({
  page,
}) => {
  await newUser(page)
  await seed(
    page,
    Array.from({ length: 7 }, (_, index) => ({
      title: `Late ${index + 1}`,
      due_date: day(-1),
    })),
  )
  await page.goto("/")

  const overdue = band(page, /^Overdue/)
  await expect(overdue.getByRole("heading")).toHaveText(/^Overdue\s*7$/)
  await overdue.getByRole("link", { name: "2 more" }).click()
  await expect(page).toHaveURL(/\/tasks\?.*overdue=true/)
  await expect(
    page.getByText("Status: Backlog, To do, In progress, Review"),
  ).toBeVisible()
  await expect(page.getByText("Late 7")).toBeVisible()
})

test("A clear day says so in a sentence, not an empty box", async ({
  page,
}) => {
  await newUser(page)
  await seed(page, [{ title: "Rewrite the copy", due_date: day(2) }])
  await page.goto("/")

  await expect(page.getByText("Nothing needs you today.")).toBeVisible()
  await expect(page.getByText("Nothing is overdue or due today.")).toBeVisible()
  await expect(
    page.getByRole("link", { name: "1 task is due later this week." }),
  ).toBeVisible()
  await expect(page.getByRole("heading", { name: /^Overdue/ })).toHaveCount(0)
  await expect(page.getByRole("heading", { name: /^Due today/ })).toHaveCount(0)
})

test("The next visit counts the bot users' changes since the last one", async ({
  page,
  context,
}) => {
  await newUser(page)
  await page.goto("/")
  await expect(
    page.getByText("Your bot users have made no changes yet."),
  ).toBeVisible()
  // A reload is the same visit.
  await page.reload()
  await expect(
    page.getByText("Your bot users have made no changes yet."),
  ).toBeVisible()

  // A new tab is a new visit, counted from the last look.
  const later = await context.newPage()
  await later.goto("/")
  await expect(
    later.getByText("Your bot users made no changes since your last visit."),
  ).toBeVisible()
})

const notice = (page: Page) =>
  page.locator("[data-sonner-toast]").filter({ hasText: "created" })

test("The capture line makes the task at once, and the key still opens the draft", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/")

  const line = page.getByRole("textbox", { name: "Add a task" })
  const sent = page.waitForRequest(
    (request) =>
      request.method() === "POST" && /\/tasks\/$/.test(request.url()),
  )
  await line.fill("Call the bank")
  await line.press("Enter")

  // One request carrying the title and nothing the reader did not choose.
  const body = (await sent).postDataJSON()
  expect(body.title).toBe("Call the bank")
  expect(body).not.toHaveProperty("project_id")
  expect(body).not.toHaveProperty("status")
  await expect(notice(page)).toContainText("“Call the bank” created in Inbox")
  // No panel opened, and the line is ready for the next thought.
  await expect(page.locator("[data-record-column]")).toHaveCount(0)
  await expect(line).toHaveValue("")
  await expect(line).toBeFocused()

  const api = await userApi(page)
  const tasks = (await (await api.get("/tasks/")).json()).data
  expect(tasks).toHaveLength(1)
  expect(tasks[0]).toMatchObject({ title: "Call the bank", status: "backlog" })
  const projects = (await (await api.get("/projects/")).json()).data
  expect(tasks[0].project_id).toBe(
    projects.find((project: { is_inbox: boolean }) => project.is_inbox).id,
  )

  // The key still opens the full draft, empty.
  await page.getByRole("heading", { level: 1 }).click()
  await page.keyboard.press("c")
  await expect(
    page
      .locator("[data-record-column]")
      .getByRole("textbox", { name: "Task title" }),
  ).toHaveValue("")
})

test("An empty line makes nothing", async ({ page }) => {
  await newUser(page)
  await page.goto("/")

  const requests: string[] = []
  page.on("request", (request) => {
    if (request.method() === "POST") requests.push(request.url())
  })
  const line = page.getByRole("textbox", { name: "Add a task" })
  await line.press("Enter")
  await line.fill("   ")
  await line.press("Enter")
  await expect(line).toBeFocused()
  await expect(page.locator("[data-sonner-toast]")).toHaveCount(0)
  expect(requests).toEqual([])
})

test("The notice's Open lands on the task's panel", async ({ page }) => {
  await newUser(page)
  await page.goto("/")

  const line = page.getByRole("textbox", { name: "Add a task" })
  await line.fill("Order milk")
  await line.press("Enter")
  await notice(page).getByRole("button", { name: "Open" }).click()

  await expect(page).toHaveURL(/task=[0-9a-f-]{36}/)
  await expect(
    page.getByRole("complementary", { name: "Order milk" }),
  ).toBeVisible()
})

test("Undo deletes the task, and the activity log keeps both acts", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/")

  const line = page.getByRole("textbox", { name: "Add a task" })
  await line.fill("Order milk")
  await line.press("Enter")
  await notice(page).getByRole("button", { name: "Undo" }).click()
  await expect(notice(page)).toHaveCount(0)

  const api = await userApi(page)
  await expect
    .poll(async () => (await (await api.get("/tasks/")).json()).count)
    .toBe(0)

  await page.goto("/activity")
  const rows = page.getByRole("row").filter({ hasText: "Order milk" })
  await expect(rows).toHaveCount(2)
  await expect(rows.nth(0)).toContainText("Deleted Order milk")
  await expect(rows.nth(1)).toContainText("Created Order milk in Inbox")
})

const changesLog = (page: Page) => band(page, /^Changes/)

/** A bot user of the reader's with every task permission in one project. */
async function botWithProject(page: Page, name: string) {
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Support queue" })
  const bot = await api.create("/bot-users/", {
    name,
    scope: {
      project_ids: [project.id],
      permissions: {
        create_tasks: true,
        read_tasks: true,
        update_tasks: true,
        delete_tasks: true,
      },
    },
  })
  const { token } = await api.create(`/bot-users/${bot.id}/token`)
  const headers = { Authorization: `Bearer ${token}` }
  return {
    file: async (title: string): Promise<{ id: string }> => {
      const response = await page.request.post(`${api.url}/tasks/`, {
        headers,
        data: { title, project_id: project.id },
      })
      expect(response.ok()).toBe(true)
      return response.json()
    },
    remove: async (id: string) => {
      const response = await page.request.delete(`${api.url}/tasks/${id}`, {
        headers,
      })
      expect(response.ok()).toBe(true)
    },
  }
}

test("Changes reads the reader's and the bot users' entries newest first, with Restore on deletions", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const mine = await api.create("/tasks/", { title: "Renew the domain" })
  const bot = await botWithProject(page, "Triage agent")
  const banner = await bot.file("Old staging banner")
  await bot.file("Migrate the marketing pages")
  await bot.remove(banner.id)
  expect((await api.delete(`/tasks/${mine.id}`)).ok()).toBe(true)
  await page.goto("/")

  const log = changesLog(page)
  // A first visit has no last one: the window is everything so far.
  await expect(log.getByRole("heading", { level: 2 })).toHaveText(
    /^Changes\s*6\s*so far$/,
  )
  const lines = log.getByRole("listitem")
  // The actor first, then what they did, newest first.
  await expect(lines).toHaveText([
    /You\s*deleted Renew the domain\s*Restore$/i,
    /Triage agent\s*deleted Old staging banner\s*Restore$/i,
    /Triage agent\s*created Migrate the marketing pages/i,
    /Triage agent\s*created Old staging banner/i,
    /You\s*created the project Support queue/i,
    /You\s*created Renew the domain/i,
  ])
  await expect(log.getByRole("button", { name: /^Restore/ })).toHaveCount(2)
  await expect(
    log.getByRole("link", { name: "Migrate the marketing pages" }),
  ).toBeVisible()

  // The reader's own lines are muted; a bot user's are in full ink.
  const sentenceColour = (line: Locator) =>
    line.evaluate((node) =>
      node.lastElementChild
        ? getComputedStyle(node.lastElementChild).color
        : null,
    )
  expect(await sentenceColour(lines.nth(0))).not.toBe(
    await sentenceColour(lines.nth(1)),
  )
  // In the dark theme too. A reload is the same visit, so the log holds.
  await page.evaluate(() => localStorage.setItem("vite-ui-theme", "dark"))
  await page.reload()
  await expect(lines).toHaveCount(6)
  expect(
    await page.evaluate(
      () => getComputedStyle(document.documentElement).colorScheme,
    ),
  ).toBe("dark")
  expect(await sentenceColour(lines.nth(0))).not.toBe(
    await sentenceColour(lines.nth(1)),
  )

  // Restore is inline: no dialog between the line and what it brings back.
  await lines
    .nth(1)
    .getByRole("button", { name: "Restore Old staging banner" })
    .click()
  await expect(page.getByText("“Old staging banner” restored")).toBeVisible()
  await expect(lines.first()).toHaveText(/You\s*restored Old staging banner/i)
  await expect(log.getByRole("button", { name: /^Restore/ })).toHaveCount(1)

  await log.getByRole("link", { name: "Full log" }).click()
  await expect(page).toHaveURL(/\/activity/)
})

test("An empty Changes log says so and points at bot users", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/")
  const log = changesLog(page)
  await expect(log).toContainText("Nothing has happened yet.")
  await expect(log.getByRole("link", { name: "Full log" })).toBeVisible()
  await log.getByRole("link", { name: "bot users", exact: true }).click()
  await expect(page).toHaveURL(/\/bots/)
})

test.describe("on a phone", () => {
  test.use({
    viewport: { width: 375, height: 812 },
    hasTouch: true,
    isMobile: true,
  })

  test("Capture first, then the date, then the bands, with no sideways scroll", async ({
    page,
  }) => {
    await newUser(page)
    await seed(page, [
      {
        title: "A task with a long enough title to need the whole line",
        due_date: day(-1),
      },
      { title: "Due now", due_date: day(0) },
    ])
    await page.goto("/")
    // Measured once the bands have arrived: their skeleton draws the same
    // headings, and a box read off it is gone by the next assertion.
    await expect(
      page.getByRole("link", { name: "Due now" }).first(),
    ).toBeVisible()

    const top = async (locator: Locator) =>
      (await locator.boundingBox())?.y ?? Number.NaN
    const capture = await top(page.getByRole("textbox", { name: "Add a task" }))
    const date = await top(page.getByRole("heading", { level: 1 }))
    const overdue = await top(page.getByRole("heading", { name: /^Overdue/ }))
    const today = await top(page.getByRole("heading", { name: /^Due today/ }))
    expect(capture).toBeLessThan(date)
    expect(date).toBeLessThan(overdue)
    expect(overdue).toBeLessThan(today)

    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    )
    expect(overflow).toBeLessThanOrEqual(0)
  })

  test("A Changes line keeps time and actor on one line, the sentence beneath", async ({
    page,
  }) => {
    await newUser(page)
    const bot = await botWithProject(page, "Research agent")
    const title =
      "Summarise the three trackers and the long discussion that followed"
    await bot.file(title)
    await page.goto("/")

    const line = changesLog(page).getByRole("listitem").first()
    const box = async (locator: Locator) => {
      const found = await locator.boundingBox()
      if (!found) throw new Error("not laid out")
      return found
    }
    const time = await box(line.locator("time"))
    const actor = await box(line.getByRole("link", { name: "Research agent" }))
    const task = await box(line.getByRole("link", { name: title }))
    expect(Math.abs(time.y - actor.y)).toBeLessThan(8)
    expect(task.y).toBeGreaterThanOrEqual(actor.y + actor.height - 1)
    // The task's name wraps whole onto the next line rather than being cut.
    await expect(line).toContainText(title)
    expect(
      await line.evaluate((node) => node.scrollWidth <= node.clientWidth),
    ).toBe(true)
  })
})

test("A section that cannot load says so and leaves the rest of the page", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const myId = (await (await api.get("/users/me")).json()).id
  await api.create("/tasks/", {
    title: "Water the plants",
    status: "in_progress",
    assignee_id: myId,
  })
  // The activity log refuses. The Changes log and the sentence's second
  // half read it; the bands and the reader's own work do not.
  let refuse = true
  await page.route(
    (url) => url.pathname === "/api/v1/activity-log/",
    (route) =>
      refuse
        ? route.fulfill({ status: 404, json: { detail: "Not found" } })
        : route.fallback(),
  )
  await page.goto("/")

  // The sentence under the date loses its half about the bot users; the
  // bands, which read only tasks, stand.
  const alerts = page.getByRole("alert")
  await expect(alerts).toHaveText(["Changes could not be loaded. Try again"])
  await expect(page.getByText("Nothing needs you today.")).toBeVisible()
  await expect(page.getByText(/Your bot users/)).toHaveCount(0)
  const myWork = page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: /^In my hands/ }) })
  await expect(myWork).toContainText("Water the plants")

  refuse = false
  await alerts.getByRole("button", { name: "Try again" }).click()
  await expect(alerts).toHaveCount(0)
  await expect(page.getByRole("heading", { name: /^Changes/ })).toBeVisible()
})
