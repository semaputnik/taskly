import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

// Everything here is on a phone: a narrow screen, touched rather than
// pointed at.
test.use({
  storageState: { cookies: [], origins: [] },
  viewport: { width: 375, height: 812 },
  hasTouch: true,
  isMobile: true,
})

test("A tap on the due date lands on the native date field, and the day it picks is saved", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", { title: "Book the MOT" })
  await page.goto(`/tasks?task=${task.id}`)

  // The native field is the control here, named as the button is with a
  // mouse, so a screen reader reaches the same thing a finger does.
  const field = page.getByLabel(/^Due date:/)
  await expect(field).toHaveAccessibleName("Due date: not set")

  // iOS opens no picker for a date field from script (`showPicker`, or
  // `focus` on a hidden field), so the finger itself has to reach the
  // native field: it lies over the button, and is what a tap hits.
  await field.scrollIntoViewIfNeeded()
  const box = await field.boundingBox()
  if (!box) throw new Error("The due date field has no box")
  const hit = await page.evaluate(
    ([x, y]) => {
      const element = document.elementFromPoint(x, y)
      return element instanceof HTMLInputElement ? element.type : null
    },
    [box.x + box.width / 2, box.y + box.height / 2],
  )
  expect(hit).toBe("date")

  const saved = page.waitForRequest(
    (request) =>
      request.method() === "PATCH" && request.url().includes(task.id),
  )
  await field.fill("2030-03-14")
  expect((await saved).postDataJSON()).toMatchObject({
    due_date: "2030-03-14",
  })
  await expect(field).not.toHaveAccessibleName("Due date: not set")
})

const line = (page: Page) => page.getByRole("combobox", { name: /^Add a task/ })

/** The box of something that must be on screen. */
async function boxOf(locator: ReturnType<Page["locator"]>) {
  const box = await locator.boundingBox()
  if (!box) throw new Error("Nothing to measure: it has no box")
  return box
}

/**
 * Stands in for a keyboard: the visual viewport shrinks and the layout
 * viewport does not, which is what iOS Safari does (Chromium resizes both).
 */
async function raiseKeyboard(page: Page, height: number) {
  await page.evaluate((keyboard) => {
    const viewport = window.visualViewport
    if (!viewport) throw new Error("No visual viewport")
    Object.defineProperty(viewport, "height", {
      configurable: true,
      value: window.innerHeight - keyboard,
    })
    viewport.dispatchEvent(new Event("resize"))
  }, height)
}

test("The capture line is pinned to the bottom of the task list and the day page, and there is no floating button", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  for (let n = 1; n <= 25; n++) {
    await api.create("/tasks/", { title: `Task number ${n}` })
  }

  for (const path of ["/tasks", "/"]) {
    await page.goto(path)
    await expect(line(page)).toBeVisible()
    // Nothing floats: the line is the way to add a task.
    await expect(page.getByRole("button", { name: "Add a task" })).toHaveCount(
      0,
    )

    const box = await boxOf(line(page))
    expect(box.y).toBeGreaterThan(812 - 90)
    expect(box.y + box.height).toBeLessThanOrEqual(812)
    expect(box.height).toBeGreaterThanOrEqual(44)
    // A field set smaller than 16px makes iOS zoom the page in on focus.
    const size = await line(page).evaluate(
      (element) => getComputedStyle(element).fontSize,
    )
    expect(Number.parseFloat(size)).toBeGreaterThanOrEqual(16)

    // Scrolled to the foot, it has not moved.
    await page.mouse.wheel(0, 5000)
    await page.waitForTimeout(150)
    expect((await boxOf(line(page))).y).toBe(box.y)
  }
})

test("The pinned line follows the keyboard, and writing a task from it files it", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks")
  const rest = await boxOf(line(page))

  await line(page).tap()
  await raiseKeyboard(page, 300)
  await expect
    .poll(async () => (await boxOf(line(page))).y)
    .toBeCloseTo(rest.y - 300, 0)

  // Nothing to send while nothing is written.
  await expect(page.getByRole("button", { name: "Create task" })).toHaveCount(0)
  await line(page).fill("Buy milk")
  await page.getByRole("button", { name: "Create task" }).tap()
  await expect(page.getByText("“Buy milk” created")).toBeVisible()
  await expect(line(page)).toHaveValue("")
  await expect(page.getByRole("list", { name: "Tasks" })).toContainText(
    "Buy milk",
  )

  // Return does the same.
  await line(page).fill("Call the bank")
  await line(page).press("Enter")
  await expect(page.getByText("“Call the bank” created")).toBeVisible()
})

test("The matches open upward from the pinned line, above the keyboard", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  for (const title of ["Redirect the old URLs", "Check the redirect map"]) {
    await api.create("/tasks/", { title })
  }
  await page.goto("/tasks")

  await line(page).tap()
  await raiseKeyboard(page, 300)
  await line(page).fill("redirect")
  const list = page.getByRole("listbox", { name: /^Open tasks matching/ })
  await expect(list.getByRole("option")).toHaveCount(2)

  const above = await boxOf(list)
  const field = await boxOf(line(page))
  expect(above.y + above.height).toBeLessThanOrEqual(field.y)
  expect(above.y).toBeGreaterThanOrEqual(0)
  // A tap on a match opens it.
  await list.getByRole("option").first().tap()
  await expect(page.locator("[data-record-column]")).toBeVisible()
})

test("The pinned line gives way to a record's full-screen column", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", { title: "Pay the invoice" })
  await page.goto("/tasks")
  await expect(line(page)).toBeVisible()

  await page.goto(`/tasks?task=${task.id}`)
  await expect(page.locator("[data-record-column]")).toBeVisible()
  await expect(line(page)).toBeHidden()

  await page.getByRole("button", { name: "Close" }).tap()
  await expect(page.locator("[data-record-column]")).toHaveCount(0)
  await expect(line(page)).toBeVisible()
})

test("The filter row keeps three filters and the order, and folds the rest behind More", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tags/", { name: "copy" })
  await page.goto("/tasks")

  for (const name of [
    "Any project",
    "Anyone",
    "Any status",
    "More",
    /^Order:/,
  ]) {
    await expect(page.getByRole("button", { name })).toBeVisible()
  }
  for (const name of ["Any priority", "Any tag", "Any time"]) {
    await expect(page.getByRole("button", { name })).toHaveCount(0)
  }

  // A menu is a bottom sheet with rows a thumb can hit.
  await page.getByRole("button", { name: "Any status" }).tap()
  const sheet = page.getByRole("dialog", { name: "Status" })
  await expect(sheet).toBeVisible()
  // It rises from the bottom edge and rests on it.
  await expect
    .poll(async () => {
      const box = await boxOf(sheet)
      return box.y + box.height
    })
    .toBeCloseTo(812, 0)
  for (const row of await sheet.getByRole("button").all()) {
    if ((await row.textContent())?.includes("Close")) continue
    expect((await boxOf(row)).height).toBeGreaterThanOrEqual(44)
  }
  await sheet.getByRole("button", { name: "Review" }).tap()
  await expect(sheet).toBeHidden()
  await expect(page).toHaveURL(/status=%5B%22review%22%5D/)
  await expect(
    page.getByRole("button", { name: "Status: Review" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "Remove the status filter" }).tap()

  // More: the folded filters in one sheet, 44px apart.
  await page.getByRole("button", { name: "More" }).tap()
  const more = page.getByRole("dialog", { name: "More filters" })
  await expect(more).toBeVisible()
  for (const name of ["Any priority", "Any tag", "Overdue"]) {
    expect(
      (await boxOf(more.getByText(name, { exact: true }))).height,
    ).toBeGreaterThan(0)
  }
  for (const row of await more
    .getByRole("button", { name: /^(Any priority|Any tag|copy|P1)/ })
    .all()) {
    expect((await boxOf(row)).height).toBeGreaterThanOrEqual(44)
  }
  await more.getByRole("button", { name: "copy" }).tap()
  await more.getByRole("button", { name: "P1" }).tap()
  await more.getByRole("checkbox", { name: "Overdue" }).tap()
  await more.getByRole("button", { name: "Done" }).tap()
  await expect(more).toBeHidden()

  // Folded, but not hidden: every filter that is set is on the row.
  await expect(page.getByRole("button", { name: "Tag: copy" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Priority: P1" })).toBeVisible()
  await expect(page.getByRole("button", { name: /^Time:/ })).toBeVisible()
  await expect(page).toHaveURL(/tag=copy/)

  // Tapping a set one opens the sheet it lives in; its × drops it.
  await page.getByRole("button", { name: "Tag: copy" }).tap()
  await expect(page.getByRole("dialog", { name: "More filters" })).toBeVisible()
  await page.getByRole("button", { name: "Done" }).tap()
  await page.getByRole("button", { name: "Remove the tag filter" }).tap()
  await expect(page.getByRole("button", { name: "Tag: copy" })).toHaveCount(0)
  await expect(page).not.toHaveURL(/tag=copy/)

  // The order is a sheet too.
  await page.getByRole("button", { name: /^Order:/ }).tap()
  await page
    .getByRole("dialog", { name: "Order" })
    .getByRole("button", { name: "Due date" })
    .tap()
  await expect(page).toHaveURL(/sort=due_date/)
})

test("The task list never scrolls sideways, however long a title or a project name", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", {
    name: "A project whose name goes on and on and on and on and on",
  })
  const long = `${"Extraordinarily".repeat(6)} ${"long ".repeat(12)}title`
  const parent = await api.create("/tasks/", {
    title: long,
    project_id: project.id,
    due_date: "2030-03-14",
    tags: [],
  })
  await api.create("/tasks/", { title: long, parent_id: parent.id })

  for (const path of ["/tasks", "/"]) {
    await page.goto(path)
    await expect(line(page)).toBeVisible()
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    )
    expect(overflow).toBeLessThanOrEqual(0)
  }

  // The project marker gives way before the title does: the title keeps its
  // two lines' worth of room, and the line stays inside the screen.
  await page.goto("/tasks")
  const item = page.getByRole("list", { name: "Tasks" }).getByRole("listitem")
  const first = await boxOf(item.first())
  expect(first.x + first.width).toBeLessThanOrEqual(375)
})
