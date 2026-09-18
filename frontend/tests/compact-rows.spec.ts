import { expect, type Page, test } from "@playwright/test"
import { isoDay } from "../src/lib/dates"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

const band = (page: Page, name: RegExp) =>
  page.locator("section").filter({ has: page.getByRole("heading", { name }) })

/** A root task with two subtasks, one done, due today and tagged. */
async function seedStarted(page: Page) {
  const api = await userApi(page)
  const today = isoDay(new Date())
  const low = await api.create("/tasks/", {
    title: "Tidy the shed",
    status: "in_progress",
    priority: "P3",
  })
  const high = await api.create("/tasks/", {
    title: "File the taxes",
    status: "in_progress",
    priority: "P1",
    due_date: today,
    tags: ["home"],
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

test("The dashboard has a sheet of what is in progress, most pressing first", async ({
  page,
}) => {
  await newUser(page)
  await seedStarted(page)
  await page.goto("/")

  const started = band(page, /^In progress/)
  await expect(started.getByRole("heading")).toHaveText(/In progress\s*2/)
  const titles = started.getByRole("link")
  await expect(titles.nth(0)).toHaveText("File the taxes")
  await expect(titles.nth(1)).toHaveText("Tidy the shed")
  await expect(started).not.toContainText("Water the plants")
})

test("An empty in-progress sheet says so rather than disappearing", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/")
  await expect(band(page, /^In progress/)).toContainText("Nothing in progress")
})

test("A compact row shows subtasks, due day and tags, and its priority on the checkbox", async ({
  page,
}) => {
  await newUser(page)
  await seedStarted(page)
  await page.goto("/")

  const started = band(page, /^In progress/)
  const row = started
    .locator("div")
    .filter({ has: page.getByRole("link", { name: "File the taxes" }) })
    // The outermost match is the row; the rest are its own lines.
    .first()
  await expect(row).toContainText("1/2")
  await expect(row).toContainText("Today")
  await expect(row).toContainText("home")

  const urgent = row.getByRole("checkbox", {
    name: "Mark as done, priority P1",
  })
  await expect(urgent).toHaveClass(/border-priority-p1/)
  // A low priority is its own hue, not the same ring in another place.
  await expect(
    started.getByRole("checkbox", { name: "Mark as done, priority P3" }),
  ).toHaveClass(/border-priority-p3/)
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
