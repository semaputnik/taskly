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

/** More tasks than one page holds, so paging has something to page. */
async function seedTasks(
  page: Page,
  count: number,
  extra: (index: number) => Record<string, unknown> = () => ({}),
) {
  const { url, headers } = await api(page)
  const ids: string[] = []
  for (let index = 0; index < count; index++) {
    const created = await page.request.post(`${url}/tasks/`, {
      headers,
      data: {
        title: `Task ${String(index).padStart(2, "0")}`,
        ...extra(index),
      },
    })
    ids.push((await created.json()).id)
  }
  return ids
}

const row = (page: Page, title: string) =>
  page.getByRole("row", { name: `Open ${title}` })

test("The footer counts what matches, and every task is reachable by paging", async ({
  page,
}) => {
  await newUser(page)
  await seedTasks(page, 28)

  await page.goto("/tasks?view=table")
  await expect(page.getByText("28 tasks · page 1 of 2")).toBeVisible()
  await expect(row(page, "Task 00")).toBeVisible()
  await expect(row(page, "Task 27")).toHaveCount(0)

  await page.getByRole("button", { name: "Next" }).click()
  await expect(page).toHaveURL(/page=2/)
  await expect(page.getByText("28 tasks · page 2 of 2")).toBeVisible()
  await expect(row(page, "Task 27")).toBeVisible()

  // The page is part of the address, so a reload lands where it left off.
  await page.reload()
  await expect(row(page, "Task 27")).toBeVisible()
})

test("A column header sorts the whole result set, both ways", async ({
  page,
}) => {
  await newUser(page)
  // Due dates run backwards against the titles, so the extreme value is only
  // on the first page if the server did the sorting.
  await seedTasks(page, 28, (index) => ({
    due_date: `2026-${String(Math.floor((27 - index) / 28) + 1).padStart(2, "0")}-${String(((27 - index) % 28) + 1).padStart(2, "0")}`,
  }))

  await page.goto("/tasks?view=table")
  await page.getByRole("button", { name: "Due date" }).click()
  await expect(page).toHaveURL(/sort=due_date/)

  const header = page.getByRole("columnheader", { name: /Due date/ })
  await expect(header).toHaveAttribute("aria-sort", "ascending")
  // The earliest due date belongs to the last task created.
  await expect(row(page, "Task 27")).toBeVisible()

  await page.getByRole("button", { name: "Due date" }).click()
  await expect(header).toHaveAttribute("aria-sort", "descending")
  await expect(page).toHaveURL(/order=desc/)
  await expect(row(page, "Task 00")).toBeVisible()

  // Sorting survives a reload, and is not a filter: clearing the filters
  // leaves it alone.
  await page.reload()
  await expect(
    page.getByRole("columnheader", { name: /Due date/ }),
  ).toHaveAttribute("aria-sort", "descending")
})

test("Changing a filter returns to the first page", async ({ page }) => {
  await newUser(page)
  const { url, headers } = await api(page)
  const project = await (
    await page.request.post(`${url}/projects/`, {
      headers,
      data: { name: "Sweep" },
    })
  ).json()
  await seedTasks(page, 28)
  await page.request.post(`${url}/tasks/`, {
    headers,
    data: { title: "In the project", project_id: project.id },
  })

  await page.goto("/tasks?view=table&page=2")
  await expect(page.getByText("page 2 of 2")).toBeVisible()

  await page.getByRole("button", { name: "Filters" }).click()
  await page.getByRole("combobox", { name: "Project" }).first().click()
  await page.getByRole("option", { name: "Sweep" }).click()

  await expect(page).not.toHaveURL(/page=2/)
  await expect(row(page, "In the project")).toBeVisible()
})

test("A selection is counted, survives paging and is cleared by a filter", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers } = await api(page)
  const _project = await (
    await page.request.post(`${url}/projects/`, {
      headers,
      data: { name: "Sweep" },
    })
  ).json()
  await seedTasks(page, 28)

  await page.goto("/tasks?view=table")
  await page.getByRole("checkbox", { name: "Select Task 00" }).check()
  await expect(page.getByText("1 selected")).toBeVisible()

  // Gathered across pages of one filter set.
  await page.getByRole("button", { name: "Next" }).click()
  await page.getByRole("checkbox", { name: "Select Task 27" }).check()
  await expect(page.getByText("2 selected")).toBeVisible()

  // And dropped when the filters change, because those tasks may be gone.
  await page.getByRole("button", { name: "Filters" }).click()
  await page.getByRole("combobox", { name: "Project" }).first().click()
  await page.getByRole("option", { name: "Sweep" }).click()
  await expect(page.getByText("selected")).toHaveCount(0)
})

test("Select-all takes the page, and offers every matching task", async ({
  page,
}) => {
  await newUser(page)
  await seedTasks(page, 28)

  await page.goto("/tasks?view=table")
  await page
    .getByRole("checkbox", { name: "Select every task on this page" })
    .check()
  await expect(page.getByText("25 selected")).toBeVisible()
  // Which selection is in force is stated, not implied.
  await page
    .getByRole("button", { name: "Select all 28 tasks matching these filters" })
    .click()
  await expect(page.getByText("28 selected")).toBeVisible()

  await page.getByRole("button", { name: "Clear selection" }).click()
  await expect(page.getByText("selected")).toHaveCount(0)
})

test("A batch changes exactly the tasks selected", async ({ page }) => {
  await newUser(page)
  await seedTasks(page, 3)

  await page.goto("/tasks?view=table")
  await page.getByRole("checkbox", { name: "Select Task 00" }).check()
  await page.getByRole("checkbox", { name: "Select Task 01" }).check()

  await page.getByRole("combobox", { name: "Set priority" }).click()
  await page.getByRole("option", { name: "P1" }).click()
  await expect(page.getByText("2 tasks changed")).toBeVisible()

  await expect(row(page, "Task 00")).toContainText("P1")
  await expect(row(page, "Task 01")).toContainText("P1")
  await expect(row(page, "Task 02")).toContainText("No priority")

  // One act, one entry: the log records what the user did, not how many
  // requests it took.
  await page.goto("/activity")
  const entries = page.getByRole("row").filter({ hasText: "2 tasks" })
  await expect(entries).toHaveCount(1)
})

test("A batch that cannot be done whole names the rows in the way", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers } = await api(page)
  const _project = await (
    await page.request.post(`${url}/projects/`, {
      headers,
      data: { name: "Elsewhere" },
    })
  ).json()
  const parent = await (
    await page.request.post(`${url}/tasks/`, {
      headers,
      data: { title: "Parent task" },
    })
  ).json()
  await page.request.post(`${url}/tasks/`, {
    headers,
    data: { title: "Child task", parent_id: parent.id },
  })

  await page.goto("/tasks?view=table")
  await page
    .getByRole("checkbox", { name: "Select every task on this page" })
    .check()
  await page.getByRole("combobox", { name: "Move to project" }).click()
  await page.getByRole("option", { name: "Elsewhere" }).click()

  await expect(page.getByText("stood in the way")).toBeVisible()
  await expect(
    page.getByText("A subtask follows the project of the task at the top"),
  ).toBeVisible()
  // Nothing moved, including the task that could have.
  await expect(row(page, "Parent task")).toContainText("Inbox")
})

test("A batch delete confirms with the count, and restores as one act", async ({
  page,
}) => {
  await newUser(page)
  await seedTasks(page, 3)

  await page.goto("/tasks?view=table")
  await page
    .getByRole("checkbox", { name: "Select every task on this page" })
    .check()
  await page.getByRole("button", { name: "Delete" }).click()
  const confirm = page.getByRole("dialog", { name: "Delete 3 tasks?" })
  await expect(confirm).toContainText("restored from there")
  await confirm.getByRole("button", { name: "Delete", exact: true }).click()

  await expect(page.getByText("3 tasks deleted")).toBeVisible()
  await expect(page.getByText("No tasks yet")).toBeVisible()

  await page.goto("/activity")
  const deletion = page.getByRole("row").filter({ hasText: "Deleted" })
  await expect(deletion).toHaveCount(1)
  await deletion.getByRole("button", { name: "Restore" }).click()
  const restore = page.getByRole("dialog", { name: "Restore tasks" })
  // The batch comes back as the batch it was, and the confirmation says so.
  await expect(restore).toContainText("3 tasks")
  await restore.getByRole("button", { name: "Restore", exact: true }).click()
  await expect(page.getByText("“3 tasks” restored")).toBeVisible()

  await page.goto("/tasks?view=table")
  await expect(page.getByText("3 tasks", { exact: true })).toBeVisible()
})

test("Completion still works from the row, beside the title", async ({
  page,
}) => {
  await newUser(page)
  await seedTasks(page, 1)

  await page.goto("/tasks?view=table")
  await row(page, "Task 00")
    .getByRole("checkbox", { name: "Mark as done" })
    .click()
  // Round check, beside the title: it closes the task, so the row leaves a
  // list of open work (ADR-0006) and the notice says so.
  await expect(row(page, "Task 00")).toHaveCount(0)
  await expect(
    page.locator("[data-sonner-toast]").filter({ hasText: "Task 00" }),
  ).toBeVisible()
  // The selection checkbox is a different control: closing a task is not
  // selecting one, so nothing was selected.
  await expect(page.getByText("selected")).toHaveCount(0)
})

test("On a narrow screen the table says it continues sideways", async ({
  page,
}) => {
  await newUser(page)
  await seedTasks(page, 2)
  await page.setViewportSize({ width: 500, height: 800 })

  await page.goto("/tasks?view=table")
  const scroller = page.getByRole("region", {
    name: "Tasks, scrollable sideways",
  })
  await expect(scroller).toBeVisible()

  // It really does scroll, rather than clipping what it cannot fit.
  const overflow = await scroller.evaluate(
    (element) => element.scrollWidth - element.clientWidth,
  )
  expect(overflow).toBeGreaterThan(0)

  // And it says so in words, not only in pixels.
  await expect(
    page.getByText("Swipe sideways for the rest of each row"),
  ).toBeVisible()
})

test("A batch can clear a priority, and the selection drops with the filters", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers } = await api(page)
  for (const title of ["Task 00", "Task 01"]) {
    await page.request.post(`${url}/tasks/`, {
      headers,
      data: { title, priority: "P1" },
    })
  }

  await page.goto("/tasks?view=table")
  await page
    .getByRole("checkbox", { name: "Select every task on this page" })
    .check()
  await page.getByRole("combobox", { name: "Set priority" }).click()
  await page.getByRole("option", { name: "No priority" }).click()
  await expect(page.getByText("2 tasks changed")).toBeVisible()
  await expect(row(page, "Task 00")).toContainText("No priority")

  // A selection belongs to the filters it was gathered under.
  await page
    .getByRole("checkbox", { name: "Select every task on this page" })
    .check()
  await expect(page.getByText("2 selected")).toBeVisible()
  await page.getByRole("button", { name: "Overdue" }).click()
  await expect(page.getByText("selected")).toHaveCount(0)
})
