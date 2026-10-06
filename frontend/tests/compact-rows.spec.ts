import { expect, type Page, test } from "@playwright/test"
import { isoDay } from "../src/lib/dates"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

/** One of My work's status groups on the day page. */
const group = (page: Page, name: string) =>
  page
    .locator("section")
    .filter({
      has: page.getByRole("heading", { level: 2, name: /In my hands/ }),
    })
    .locator("section")
    .filter({ has: page.getByRole("heading", { level: 3, name }) })

/** A root task with two subtasks, one done, due today and tagged. */
async function seedStarted(page: Page) {
  const api = await userApi(page)
  const me = await (await api.get("/users/me")).json()
  const today = isoDay(new Date())
  const low = await api.create("/tasks/", {
    title: "Tidy the shed",
    status: "in_progress",
    priority: "P3",
    assignee_id: me.id,
  })
  const high = await api.create("/tasks/", {
    title: "File the taxes",
    status: "in_progress",
    priority: "P1",
    due_date: today,
    tags: ["home"],
    assignee_id: me.id,
  })
  const first = await api.create("/tasks/", {
    title: "Find the receipts",
    parent_id: high.id,
  })
  await api.create("/tasks/", { title: "Fill the form", parent_id: high.id })
  await api.patch(`/tasks/${first.id}`, { status: "done" })
  await api.create("/tasks/", { title: "Water the plants" })
  return { api, low, high }
}

test("My work lists what is in progress, most pressing first", async ({
  page,
}) => {
  await newUser(page)
  await seedStarted(page)
  await page.goto("/")

  const started = group(page, "In progress")
  const titles = started.getByRole("link")
  await expect(titles.nth(0)).toHaveText("File the taxes")
  await expect(titles.nth(1)).toHaveText("Tidy the shed")
  await expect(started).not.toContainText("Water the plants")
})

test("A compact row shows subtasks, due day, tags and project, and its status mark in its priority's colour", async ({
  page,
}) => {
  await newUser(page)
  await seedStarted(page)
  await page.goto("/")

  const started = group(page, "In progress")
  const row = started
    .locator("div")
    .filter({ has: page.getByRole("link", { name: "File the taxes" }) })
    // The outermost match is the row; the rest are its own lines.
    .first()
  // The meta line in its order: subtasks, due day, tags, then the project.
  await expect(row).toContainText(
    /Subtasks done:\s*1\/2.*Due:\s*Today.*Tag:\s*home.*Project:\s*Inbox/,
  )

  // The mark is the completion control, named for its status and priority
  // since its shape and colour say nothing to a screen reader.
  const urgent = row.getByRole("checkbox", {
    name: "Mark as done (In progress, priority P1)",
  })
  await expect(urgent).not.toBeChecked()
  await expect(urgent.locator("svg")).toHaveClass(/text-priority-p1/)
  // A low priority is its own hue, not the same mark in another place.
  await expect(
    started
      .getByRole("checkbox", {
        name: "Mark as done (In progress, priority P3)",
      })
      .locator("svg"),
  ).toHaveClass(/text-priority-p3/)
})

test("A status mark names its status in a tip on hover and on keyboard focus, and its name is not said twice", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tasks/", { title: "Look into it", status: "in_progress" })
  await page.goto("/tasks")

  const mark = page.getByRole("checkbox", {
    name: /^Mark as done \(In progress/,
  })
  // The tip is drawn from an attribute, so it is not text a screen reader
  // reads on top of the control's own name.
  await expect(mark).toHaveAccessibleName("Mark as done (In progress)")
  await expect(mark).toHaveAttribute("data-tip", "In progress")
  const tip = () =>
    mark.evaluate((element) => {
      const style = getComputedStyle(element, "::after")
      return { content: style.content, opacity: style.opacity }
    })
  await expect.poll(tip).toEqual({ content: '"In progress"', opacity: "0" })

  // Hovering shows it (after a short pause).
  await mark.hover()
  await expect
    .poll(async () => (await tip()).opacity, { timeout: 3000 })
    .toBe("1")
  await page.mouse.move(600, 400)
  await expect.poll(async () => (await tip()).opacity).toBe("0")

  // So does focus from the keyboard, which a pointer-only tip would miss.
  await page.getByRole("link", { name: "Look into it" }).focus()
  await page.keyboard.press("Shift+Tab")
  await expect(mark).toBeFocused()
  await expect.poll(async () => (await tip()).opacity).toBe("1")
})

test("An overdue line says how late up to a fortnight, then the date, and is red only in its due day", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const daysAgo = (days: number) => {
    const date = new Date()
    date.setDate(date.getDate() - days)
    return isoDay(date)
  }
  await api.create("/tasks/", {
    title: "Pay the invoice",
    priority: "P1",
    due_date: daysAgo(14),
  })
  await api.create("/tasks/", {
    title: "Renew the licence",
    priority: "P2",
    due_date: daysAgo(15),
  })
  await page.goto("/")

  const line = (title: string) =>
    page
      .locator("section")
      .filter({ has: page.getByRole("heading", { name: /^Overdue/ }) })
      .locator("div")
      .filter({ has: page.getByRole("link", { name: title }) })
      // The outermost match is the row; the rest are its own lines.
      .first()
  const recent = line("Pay the invoice")
  await expect(recent).toContainText("14 days late")
  const old = line("Renew the licence")
  await expect(old).toContainText(/due \d{2}\D\d{2}\D\d{4}/)
  await expect(old).not.toContainText("days late")
  // Still red: the date takes the due day's alert colour.
  await expect(old.getByText(/^due /).locator("xpath=..")).toHaveClass(
    /text-late/,
  )

  // Red is said once on an overdue line: the P1 mark is ink there, while
  // another priority keeps its hue.
  await expect(recent.getByRole("checkbox").locator("svg")).not.toHaveClass(
    /text-priority-p1/,
  )
  await expect(old.getByRole("checkbox").locator("svg")).toHaveClass(
    /text-priority-p2/,
  )
})

test("A kept task's status mark carries its priority's hue, and is not a control", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Shelved" })
  await api.create("/tasks/", {
    title: "Urgent",
    priority: "P1",
    project_id: project.id,
  })
  await api.create("/tasks/", {
    title: "Someday",
    priority: "P4",
    project_id: project.id,
  })
  expect((await api.post(`/projects/${project.id}/archive`)).ok()).toBe(true)
  await page.goto(`/projects/${project.id}/tasks`)

  // Read-only: the mark says the status, and there is nothing to tick.
  await expect(page.getByRole("checkbox")).toHaveCount(0)
  await expect(
    page.getByRole("img", { name: "Backlog, priority P1" }),
  ).toHaveClass(/text-priority-p1/)
  await expect(
    page.getByRole("img", { name: "Backlog, priority P4" }),
  ).not.toHaveClass(/text-priority/)
})
