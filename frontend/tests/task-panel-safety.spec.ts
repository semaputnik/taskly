import { expect, type Locator, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

async function box(locator: Locator) {
  const found = await locator.boundingBox()
  if (!found) throw new Error("not on screen")
  return found
}

/** The shortest distance between the edges of two boxes; 0 when they touch. */
function gap(
  a: { x: number; y: number; width: number; height: number },
  b: { x: number; y: number; width: number; height: number },
) {
  const dx = Math.max(0, b.x - (a.x + a.width), a.x - (b.x + b.width))
  const dy = Math.max(0, b.y - (a.y + a.height), a.y - (b.y + b.height))
  return Math.hypot(dx, dy)
}

async function openTaskWithSubtask(page: Page) {
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", { title: "Plan the trip" })
  await api.create("/tasks/", { title: "Book the train", parent_id: task.id })
  await page.goto(`/tasks?view=table&task=${task.id}`)
  const panel = page.getByRole("dialog", { name: "Plan the trip" })
  await expect(panel).toBeVisible()
  return panel
}

async function expectSafeCorner(page: Page, panel: Locator, minTarget: number) {
  const close = panel.getByRole("button", { name: "Close", exact: true })
  const remove = panel.getByRole("button", { name: "Delete task" })
  await remove.scrollIntoViewIfNeeded()
  const closeBox = await box(close)
  const deleteBox = await box(remove)

  expect(closeBox.width).toBeGreaterThanOrEqual(minTarget)
  expect(closeBox.height).toBeGreaterThanOrEqual(minTarget)
  // Delete is nowhere near the control a hand reaches for to dismiss.
  expect(gap(closeBox, deleteBox)).toBeGreaterThan(100)
  // And it stays one control, not a menu.
  await expect(remove).not.toHaveAttribute("aria-haspopup")

  // The confirmation's own dismiss control is a comfortable target too.
  await remove.click()
  const confirm = page.getByRole("dialog", { name: "Delete task" })
  // Measured once the dialog has finished zooming in.
  await confirm.evaluate((el) =>
    Promise.all(el.getAnimations().map((animation) => animation.finished)),
  )
  const confirmClose = await box(
    confirm.getByRole("button", { name: "Close", exact: true }),
  )
  expect(confirmClose.width).toBeGreaterThanOrEqual(minTarget)
  expect(confirmClose.height).toBeGreaterThanOrEqual(minTarget)
  await page.keyboard.press("Escape")
  await expect(confirm).toBeHidden()
}

test("Delete sits away from close, and close is a comfortable target", async ({
  page,
}) => {
  const panel = await openTaskWithSubtask(page)

  // Opening the panel puts focus on the panel itself — not on a control, and
  // so not on one beside delete — and the first Tab lands at the top.
  await expect(panel).toBeFocused()
  await page.keyboard.press("Tab")
  const first = page.locator(":focus")
  expect(
    gap(
      await box(first),
      await box(panel.getByRole("button", { name: "Delete task" })),
    ),
  ).toBeGreaterThan(100)

  await expectSafeCorner(page, panel, 24)
})

test.describe("on a touch screen", () => {
  test.use({
    viewport: { width: 375, height: 812 },
    hasTouch: true,
    isMobile: true,
  })

  test("Close is a thumb-sized target and delete is far from it", async ({
    page,
  }) => {
    const panel = await openTaskWithSubtask(page)
    await expectSafeCorner(page, panel, 44)
  })
})

test("The delete confirmation says the task comes back from the activity log, and it does", async ({
  page,
}) => {
  const panel = await openTaskWithSubtask(page)

  await panel.getByRole("button", { name: "Delete task" }).click()
  const confirm = page.getByRole("dialog", { name: "Delete task" })
  await expect(confirm).toContainText("will be deleted")
  await expect(confirm).toContainText(
    "The deletion is recorded in your activity log, and the task can be restored from there.",
  )
  await confirm.getByRole("button", { name: "Delete", exact: true }).click()

  // The cascade warning is kept, and says the way back holds for the subtasks.
  const cascade = page.getByRole("dialog", { name: "This task has subtasks" })
  await expect(cascade).toContainText("deletes its subtasks too")
  await expect(cascade).toContainText("Nothing was deleted yet")
  await expect(cascade).toContainText(
    "recorded in your activity log as one deletion, and can be restored from there together",
  )
  await cascade
    .getByRole("button", { name: "Delete task and subtasks" })
    .click()
  await expect(page.getByRole("dialog")).toHaveCount(0)

  await page.goto("/activity")
  const deletions = page
    .getByRole("row")
    .filter({ hasText: "Deleted Plan the trip" })
  await expect(deletions).toHaveCount(1)
  await deletions.getByRole("button", { name: "Restore" }).click()
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Restore", exact: true })
    .click()
  await expect(page.getByText("“Plan the trip” restored")).toBeVisible()

  await page.goto("/tasks?view=table")
  await expect(page.getByRole("row", { name: /Plan the trip/ })).toBeVisible()
  const api = await userApi(page)
  const titles = (await (await api.get("/tasks/")).json()).data.map(
    (task: { title: string }) => task.title,
  )
  expect(titles.sort()).toEqual(["Book the train", "Plan the trip"])
})
