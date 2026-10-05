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
  // A first visit counts every change the bot users have made.
  await expect(
    page.getByText("Your agents have made 1 change so far."),
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

test("The next visit counts the agents' changes since the last one", async ({
  page,
  context,
}) => {
  await newUser(page)
  await page.goto("/")
  await expect(
    page.getByText("Your agents have made no changes yet."),
  ).toBeVisible()
  // A reload is the same visit.
  await page.reload()
  await expect(
    page.getByText("Your agents have made no changes yet."),
  ).toBeVisible()

  // A new tab is a new visit, counted from the last look.
  const later = await context.newPage()
  await later.goto("/")
  await expect(
    later.getByText("Your agents made no changes since your last visit."),
  ).toBeVisible()
})

test("The capture line opens capture with what was typed", async ({ page }) => {
  await newUser(page)
  await page.goto("/")

  const line = page.getByRole("textbox", { name: "Add a task" })
  await line.fill("Call the bank")
  await line.press("Enter")

  const panel = page.getByRole("dialog")
  await expect(panel).toBeVisible()
  await expect(panel.getByRole("textbox", { name: "Task title" })).toHaveValue(
    "Call the bank",
  )
  await panel.getByRole("button", { name: "Create task" }).click()
  await expect(page.getByText("“Call the bank” created")).toBeVisible()
  // Read once the panel has closed: while it is open the page is inert.
  await expect(line).toHaveValue("")

  // The key still opens an empty capture from the page.
  await page.getByRole("heading", { level: 1 }).click()
  await page.keyboard.press("c")
  await expect(
    page.getByRole("dialog").getByRole("textbox", { name: "Task title" }),
  ).toHaveValue("")
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
})
