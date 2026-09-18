import { expect, test } from "@playwright/test"
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

test("Add Task is one tap from any screen, in the thumb's corner", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/")

  const add = page.getByRole("button", { name: "Add Task" })
  await expect(add).toBeVisible()
  const box = await add.boundingBox()
  if (!box) throw new Error("Add Task has no box")
  expect(box.width).toBeGreaterThanOrEqual(44)
  expect(box.x + box.width).toBeGreaterThan(375 - 40)
  expect(box.y + box.height).toBeGreaterThan(812 - 60)

  await add.tap()
  await page.getByRole("textbox", { name: "Task title" }).fill("Buy milk")
  await page.getByRole("textbox", { name: "Task title" }).press("Enter")
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(page.getByText("“Buy milk” created")).toBeVisible()
})

test("The list's bar lines up in two rows: filters, then order and view", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks")

  const filters = await page
    .getByRole("button", { name: "Filters" })
    .boundingBox()
  const sort = await page
    .getByRole("combobox", { name: "Sort by" })
    .boundingBox()
  const view = await page.getByRole("group", { name: "View" }).boundingBox()
  if (!filters || !sort || !view) throw new Error("The bar is missing")

  // The order starts the second row under Filters, and the view ends it.
  expect(sort.y).toBeGreaterThan(filters.y + filters.height - 1)
  expect(Math.abs(sort.x - filters.x)).toBeLessThan(2)
  expect(Math.abs(view.y - sort.y)).toBeLessThan(4)
})
