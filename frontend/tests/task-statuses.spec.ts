import { expect, type Page, test } from "@playwright/test"
import {
  describeStatusFilter,
  OPEN_STATUSES,
} from "../src/components/Tasks/statuses"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

const row = (page: Page, title: string) =>
  page.getByRole("row", { name: `Open ${title}` })

const statusTrigger = (page: Page, title: string) =>
  row(page, title).getByRole("button", { name: /Change status of/ })

async function seed(
  page: Page,
  tasks: { title: string; status?: string; due_date?: string }[],
) {
  const api = await userApi(page)
  const ids: Record<string, string> = {}
  for (const task of tasks) {
    ids[task.title] = (await api.create("/tasks/", task)).id
  }
  return { api, ids }
}

/** The body of the next task update the page sends. */
function nextUpdate(page: Page) {
  return page
    .waitForRequest(
      (request) =>
        request.method() === "PATCH" && /\/tasks\/[^/]+$/.test(request.url()),
    )
    .then((request) => request.postDataJSON())
}

test("The Open filter is its three statuses, and one status reads as itself", () => {
  expect(OPEN_STATUSES).toEqual(["todo", "in_progress", "waiting"])
  expect(describeStatusFilter(["waiting", "todo", "in_progress"])).toBe("Open")
  expect(describeStatusFilter(["waiting"])).toBe("Waiting")
  expect(describeStatusFilter(["todo", "done"])).toBe("To do, Done")
  expect(describeStatusFilter(undefined)).toBeUndefined()
})

test("The checkbox is checked only for Done, and sends done or todo", async ({
  page,
}) => {
  await newUser(page)
  await seed(page, [
    { title: "Started", status: "in_progress" },
    { title: "Parked", status: "waiting" },
  ])
  await page.goto("/tasks")

  for (const title of ["Started", "Parked"]) {
    const box = row(page, title).getByRole("checkbox", { name: "Mark as done" })
    await expect(box).not.toBeChecked()
    const sent = nextUpdate(page)
    await box.click()
    expect(await sent).toEqual({ status: "done" })
    const reopen = row(page, title).getByRole("checkbox", {
      name: "Reopen task",
    })
    await expect(reopen).toBeChecked()

    // Unchecking cannot know the status before, so it is always To do.
    const back = nextUpdate(page)
    await reopen.click()
    expect(await back).toEqual({ status: "todo" })
    await expect(statusTrigger(page, title)).toContainText("To do")
  }
})

test("A status is changed from the list column and from the panel", async ({
  page,
}) => {
  await newUser(page)
  await seed(page, [{ title: "Call the bank" }])
  await page.goto("/tasks")

  await expect(page.getByRole("columnheader", { name: "Status" })).toBeVisible()
  await expect(statusTrigger(page, "Call the bank")).toContainText("To do")
  await statusTrigger(page, "Call the bank").click()
  await expect(page.getByRole("menuitemradio", { name: "To do" })).toBeChecked()
  await page.getByRole("menuitemradio", { name: "Waiting" }).click()
  await expect(statusTrigger(page, "Call the bank")).toContainText("Waiting")
  // Choosing in the menu did not open the task behind it.
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(page.getByText("Call the bank moved to Waiting")).toBeAttached()

  await row(page, "Call the bank").click()
  const panel = page.getByRole("dialog", { name: "Call the bank" })
  const select = panel.getByRole("combobox", { name: "Status" })
  await expect(select).toContainText("Waiting")
  await select.click()
  await page.getByRole("option", { name: "In progress" }).click()
  await expect(select).toContainText("In progress")
  await page.keyboard.press("Escape")
  await expect(statusTrigger(page, "Call the bank")).toContainText(
    "In progress",
  )
})

test("Done asks about open subtasks from the checkbox and from the menu", async ({
  page,
}) => {
  await newUser(page)
  const { api, ids } = await seed(page, [
    { title: "Move house" },
    { title: "Other parent" },
  ])
  await api.create("/tasks/", {
    title: "Pack books",
    parent_id: ids["Move house"],
  })
  await api.create("/tasks/", {
    title: "Pack plates",
    parent_id: ids["Other parent"],
    status: "in_progress",
  })
  await page.goto("/tasks")

  await row(page, "Move house")
    .getByRole("checkbox", { name: "Mark as done" })
    .click()
  let prompt = page.getByRole("dialog", {
    name: "This task has open subtasks",
  })
  await expect(prompt).toBeVisible()
  await prompt
    .getByRole("button", { name: "Mark the subtasks done too" })
    .click()
  await expect(prompt).toBeHidden()
  await expect(statusTrigger(page, "Pack books")).toContainText("Done")

  await statusTrigger(page, "Other parent").click()
  await page.getByRole("menuitemradio", { name: "Done" }).click()
  prompt = page.getByRole("dialog", { name: "This task has open subtasks" })
  await expect(prompt).toBeVisible()
  await prompt
    .getByRole("button", { name: "Leave the subtasks as they are" })
    .click()
  await expect(statusTrigger(page, "Other parent")).toContainText("Done")
  await expect(statusTrigger(page, "Pack plates")).toContainText("In progress")
})

test("The list filters by Open and by a single status", async ({ page }) => {
  await newUser(page)
  await seed(page, [
    { title: "Planned" },
    { title: "Parked", status: "waiting" },
    { title: "Finished", status: "done" },
  ])
  await page.goto("/tasks")

  await page.getByRole("button", { name: "Filters" }).click()
  const filter = page.getByRole("combobox", { name: "Status" })

  const listed = page.waitForRequest(
    (request) =>
      request.url().includes("/tasks/?") &&
      request.url().includes("status=todo&status=in_progress&status=waiting"),
  )
  await filter.click()
  await page.getByRole("option", { name: "Open" }).click()
  await listed
  await expect(page.getByText("Status: Open")).toBeVisible()
  await expect(row(page, "Planned")).toBeVisible()
  await expect(row(page, "Parked")).toBeVisible()
  await expect(row(page, "Finished")).toHaveCount(0)

  await filter.click()
  await page.getByRole("option", { name: "Waiting" }).click()
  await expect(page.getByText("Status: Waiting")).toBeVisible()
  await expect(row(page, "Parked")).toBeVisible()
  await expect(row(page, "Planned")).toHaveCount(0)

  // The view is in the address.
  await page.reload()
  await expect(page.getByText("Status: Waiting")).toBeVisible()
  await expect(row(page, "Planned")).toHaveCount(0)
})

test("Bulk Set status moves every selected task", async ({ page }) => {
  await newUser(page)
  await seed(page, [{ title: "One" }, { title: "Two" }])
  await page.goto("/tasks")

  await page
    .getByRole("checkbox", { name: "Select every task on this page" })
    .check()
  await page.getByRole("button", { name: "Set status" }).click()
  await page.getByRole("menuitemradio", { name: "In progress" }).click()
  await expect(page.getByText("2 tasks changed")).toBeVisible()
  await expect(statusTrigger(page, "One")).toContainText("In progress")
  await expect(statusTrigger(page, "Two")).toContainText("In progress")
})

test("A late waiting task is in Waiting on others, not in Overdue", async ({
  page,
}) => {
  await newUser(page)
  await seed(page, [
    { title: "Chase the plumber", status: "waiting", due_date: "2026-01-01" },
    { title: "Pay the rent", due_date: "2026-01-01" },
    { title: "Hear back someday", status: "waiting" },
  ])
  await page.goto("/")

  const overdue = page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: /^Overdue/ }) })
  await expect(overdue).toContainText("Pay the rent")
  await expect(overdue).not.toContainText("Chase the plumber")

  const waiting = page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: /^Waiting on others/ }) })
  await expect(waiting).toBeVisible()
  const rows = waiting.getByRole("link")
  // Dated first, undated last; the late one still says it is late, in red.
  await expect(rows.nth(0)).toHaveText("Chase the plumber")
  await expect(rows.nth(1)).toHaveText("Hear back someday")
  await expect(waiting.getByText(/days late/)).toHaveClass(/text-destructive/)

  await waiting.getByRole("link", { name: "See all" }).click()
  await expect(page).toHaveURL(/\/tasks/)
  await expect(page.getByText("Status: Waiting")).toBeVisible()
})

test("The activity log says a task moved to Waiting", async ({ page }) => {
  await newUser(page)
  const { api, ids } = await seed(page, [{ title: "Renew the lease" }])
  await api.patch(`/tasks/${ids["Renew the lease"]}`, { status: "waiting" })

  await page.goto("/activity")
  await expect(
    page.getByRole("row").filter({ hasText: "Renew the lease" }).first(),
  ).toContainText("Moved Renew the lease to Waiting")
})

test("On a phone the status column is a glyph with a 44px target", async ({
  page,
}) => {
  await newUser(page)
  await seed(page, [{ title: "Water the plants", status: "in_progress" }])
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto("/tasks")

  const trigger = statusTrigger(page, "Water the plants")
  await expect(trigger).toHaveAccessibleName(/In progress/)
  await expect(trigger.getByText("In progress")).toBeHidden()
  const box = await trigger.boundingBox()
  expect(box?.width).toBeGreaterThanOrEqual(44)
  expect(box?.height).toBeGreaterThanOrEqual(44)
})
