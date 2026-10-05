import { expect, type Page, test } from "@playwright/test"
import { isoDay } from "../src/lib/dates"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

/** One of My work's status groups on the day page. */
const group = (page: Page, name: string) =>
  page
    .locator("section")
    .filter({ has: page.getByRole("heading", { level: 3, name }) })
    .last()

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

test("The task list opens in compact rows, and switches to the table and back, keeping its filters", async ({
  page,
}) => {
  await newUser(page)
  await seedStarted(page)
  await page.goto("/tasks?status=%5B%22in_progress%22%5D")

  await expect(page.getByRole("button", { name: "Compact" })).toHaveAttribute(
    "aria-pressed",
    "true",
  )
  await expect(page.getByRole("table")).toHaveCount(0)
  await expect(page.getByRole("link", { name: "File the taxes" })).toBeVisible()
  await expect(page.getByText("Status: In progress")).toBeVisible()
  await expect(page.getByText("Water the plants")).toHaveCount(0)

  // Compact rows have no headers to sort from, so the bar offers the order.
  await page.getByRole("combobox", { name: "Sort by" }).click()
  await page.getByRole("option", { name: "Priority" }).click()
  await expect(page).toHaveURL(/sort=priority/)
  await expect(
    page.getByRole("link").filter({ hasText: /taxes|shed/ }),
  ).toHaveText(["File the taxes", "Tidy the shed"])

  await page.getByRole("button", { name: "Table" }).click()
  await expect(page).toHaveURL(/view=table/)
  await expect(page.getByRole("table")).toBeVisible()
  await expect(page.getByText("Status: In progress")).toBeVisible()

  await page.getByRole("button", { name: "Compact" }).click()
  await expect(page).not.toHaveURL(/view=/)
  await expect(page.getByRole("table")).toHaveCount(0)
})

test("A priority badge in the table carries its hue; P4 stays ink", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tasks/", { title: "Urgent", priority: "P1" })
  await api.create("/tasks/", { title: "Someday", priority: "P4" })
  await page.goto("/tasks?view=table")

  const urgent = page.getByRole("row", { name: "Open Urgent" })
  await expect(urgent.getByText("P1", { exact: true })).toHaveClass(
    /text-priority-p1/,
  )
  const someday = page.getByRole("row", { name: "Open Someday" })
  await expect(someday.getByText("P4", { exact: true })).not.toHaveClass(
    /text-priority/,
  )
})
