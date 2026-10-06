import { expect, type Page, test } from "@playwright/test"
import {
  describeStatusFilter,
  OPEN_STATUSES,
} from "../src/components/Tasks/statuses"
import { newUser, userApi } from "./utils/account"
import { openDraft } from "./utils/capture"
import { taskLine } from "./utils/tasks"

test.use({ storageState: { cookies: [], origins: [] } })

const row = taskLine

/**
 * A line's mark, which says the task's status in its name: it is the control
 * that closes the task, and carries the status for a screen reader.
 */
const mark = (page: Page, title: string, status: string) =>
  taskLine(page, title).getByRole("checkbox", {
    name: new RegExp(`\\(${status}[,)]`),
  })

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

test("Every open status is the baseline, and one status reads as itself", () => {
  expect(OPEN_STATUSES).toEqual([
    "backlog",
    "todo",
    "in_progress",
    "review",
    "waiting",
  ])
  // The list holds open work, so naming every open status narrows nothing:
  // it reads as no filter at all, and gets no chip offering to remove it
  // (ADR-0006).
  expect(
    describeStatusFilter([
      "waiting",
      "review",
      "todo",
      "in_progress",
      "backlog",
    ]),
  ).toBeUndefined()
  // The three open statuses there once were are a narrowing now.
  expect(describeStatusFilter(["todo", "in_progress", "waiting"])).toBe(
    "To do, In progress, Waiting",
  )
  expect(describeStatusFilter(["waiting"])).toBe("Waiting")
  expect(describeStatusFilter(["todo", "in_progress"])).toBe(
    "To do, In progress",
  )
  expect(describeStatusFilter(undefined)).toBeUndefined()
})

test("Completing sends done, takes the row away, and undoes to To do", async ({
  page,
}) => {
  await newUser(page)
  await seed(page, [
    { title: "Started", status: "in_progress" },
    { title: "Parked", status: "waiting" },
  ])
  await page.goto("/tasks")

  for (const title of ["Started", "Parked"]) {
    const box = row(page, title).getByRole("checkbox", {
      name: "Mark as done",
    })
    await expect(box).not.toBeChecked()
    const sent = nextUpdate(page)
    await box.click()
    expect(await sent).toEqual({ status: "done" })

    // The list holds open work, so the row goes. The row used to be its own
    // receipt; with it gone the notice takes that job, and carries the way
    // back (ADR-0006).
    await expect(row(page, title)).toHaveCount(0)
    const notice = page
      .locator("[data-sonner-toast]")
      .filter({ hasText: title })
    await expect(notice).toBeVisible()

    // Undoing cannot know the status before, so it is always To do.
    const back = nextUpdate(page)
    await notice.getByRole("button", { name: "Undo" }).click()
    expect(await back).toEqual({ status: "todo" })
    await expect(mark(page, title, "To do")).toBeVisible()
  }
})

test("A task captured from the interface starts in Backlog", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks")
  await openDraft(page)
  const title = page.getByRole("textbox", { name: "Task title" })
  await expect(title).toBeFocused()
  const created = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/tasks\/$/.test(response.url()),
  )
  await title.fill("Book the dentist")
  await title.press("Enter")
  expect((await (await created).json()).status).toBe("backlog")

  await expect(mark(page, "Book the dentist", "Backlog")).toBeVisible()
})

test("A status is changed in the panel, and the line's mark follows", async ({
  page,
}) => {
  await newUser(page)
  await seed(page, [{ title: "Call the bank" }])
  await page.goto("/tasks")

  await expect(mark(page, "Call the bank", "Backlog")).toBeVisible()
  await row(page, "Call the bank")
    .getByRole("link", { name: "Call the bank" })
    .click()
  const panel = page.getByRole("complementary", { name: "Call the bank" })
  const select = panel.getByRole("combobox", { name: "Status" })
  await expect(select).toContainText("Backlog")
  await select.click()
  // Every status, in the order work moves.
  await expect(page.getByRole("option")).toHaveText([
    "Backlog",
    "To do",
    "In progress",
    "Review",
    "Waiting",
    "Done",
  ])
  await page.getByRole("option", { name: "Waiting" }).click()
  await expect(select).toContainText("Waiting")
  await expect(mark(page, "Call the bank", "Waiting")).toBeVisible()

  await select.click()
  await page.getByRole("option", { name: "Review" }).click()
  await expect(select).toContainText("Review")
  await page.keyboard.press("Escape")
  await expect(mark(page, "Call the bank", "Review")).toBeVisible()
})

test("Done asks about open subtasks from the checkbox and from the panel", async ({
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
  // Both went to done, so both leave the list of open work — and the parent
  // is confirmed, the same as a task closed in one click.
  await expect(row(page, "Move house")).toHaveCount(0)
  await expect(row(page, "Pack books")).toHaveCount(0)
  await expect(
    page.locator("[data-sonner-toast]").filter({ hasText: "Move house" }),
  ).toBeVisible()

  await row(page, "Other parent")
    .getByRole("link", { name: "Other parent" })
    .click()
  const panel = page.getByRole("complementary", { name: "Other parent" })
  await panel.getByRole("combobox", { name: "Status" }).click()
  await page.getByRole("option", { name: "Done" }).click()
  prompt = page.getByRole("dialog", { name: "This task has open subtasks" })
  await expect(prompt).toBeVisible()
  await prompt
    .getByRole("button", { name: "Leave the subtasks as they are" })
    .click()
  await expect(row(page, "Other parent")).toHaveCount(0)
  // Left as it was, so it is still open and still listed.
  await expect(mark(page, "Pack plates", "In progress")).toBeVisible()
})

test("The list holds open work, and narrows to a single open status", async ({
  page,
}) => {
  await newUser(page)
  // The list asks for open work without being told to (ADR-0006), so the
  // request goes out before any filter is touched.
  const listed = page.waitForRequest(
    (request) =>
      request.url().includes("/tasks/?") &&
      request
        .url()
        .includes(
          "status=backlog&status=todo&status=in_progress&status=review&status=waiting",
        ),
  )
  await seed(page, [
    { title: "Planned" },
    { title: "Parked", status: "waiting" },
    { title: "Finished", status: "done" },
  ])
  await page.goto("/tasks")
  await listed

  await expect(row(page, "Planned")).toBeVisible()
  await expect(row(page, "Parked")).toBeVisible()
  await expect(row(page, "Finished")).toHaveCount(0)

  // The baseline is the default, and it is not a filter: "Any status" with
  // no × beside it.
  const filter = page.getByRole("button", { name: "Any status" })
  await expect(filter).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Remove the status filter" }),
  ).toHaveCount(0)

  await filter.click()
  // The five open statuses, in the order work moves. Done is not a view of
  // this list to ask for.
  await expect(page.getByRole("menuitemradio")).toHaveText([
    "Any status",
    "Backlog",
    "To do",
    "In progress",
    "Review",
    "Waiting",
  ])
  await page.getByRole("menuitemradio", { name: "Waiting" }).click()
  await expect(
    page.getByRole("button", { name: "Status: Waiting" }),
  ).toBeVisible()
  await expect(row(page, "Parked")).toBeVisible()
  await expect(row(page, "Planned")).toHaveCount(0)

  // The view is in the address.
  await page.reload()
  await expect(
    page.getByRole("button", { name: "Status: Waiting" }),
  ).toBeVisible()
  await expect(row(page, "Planned")).toHaveCount(0)

  // Dropping it returns to the baseline, which is every open status.
  await page.getByRole("button", { name: "Remove the status filter" }).click()
  await expect(row(page, "Planned")).toBeVisible()
  await expect(row(page, "Parked")).toBeVisible()
})

test("The activity log says a task moved to Waiting", async ({ page }) => {
  await newUser(page)
  const { api, ids } = await seed(page, [{ title: "Renew the lease" }])
  await api.patch(`/tasks/${ids["Renew the lease"]}`, { status: "waiting" })

  await page.goto("/activity")
  await expect(
    page.getByRole("listitem").filter({ hasText: "Renew the lease" }).first(),
  ).toContainText("Moved Renew the lease to Waiting")
})
