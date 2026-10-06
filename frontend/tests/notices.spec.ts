import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

/** A notice, raised by writing a task into the day page's line. */
async function raiseNotice(page: Page, title: string) {
  await page.goto("/")
  // A phone has no line on the page: the bar's add control raises the sheet
  // that carries it.
  const add = page.getByRole("button", { name: "Add a task" })
  const line = page.getByRole("combobox", { name: "Add a task" })
  await expect(add.or(line)).toBeVisible()
  if (await add.isVisible()) await add.click()
  await line.fill(title)
  await line.press("Enter")
  const notice = page.locator("[data-sonner-toast]").filter({ hasText: title })
  await expect(notice).toBeVisible()
  // Sonner slides a notice in; its place is read once it has arrived.
  await expect
    .poll(async () => (await notice.boundingBox())?.y ?? -1, { timeout: 2_000 })
    .toBeGreaterThanOrEqual(0)
  return notice
}

async function box(locator: ReturnType<Page["locator"]>) {
  await locator.waitFor()
  // Let the slide-in settle before measuring.
  let previous = await locator.boundingBox()
  for (let tries = 0; tries < 20; tries++) {
    await locator.page().waitForTimeout(50)
    const next = await locator.boundingBox()
    if (next && previous && next.y === previous.y && next.x === previous.x) {
      return next
    }
    previous = next
  }
  throw new Error("The notice never settled")
}

for (const theme of ["light", "dark"]) {
  test(`A notice is at the top of the screen, centred, in the ${theme} theme`, async ({
    page,
  }) => {
    await newUser(page)
    await page.evaluate(
      (chosen) => localStorage.setItem("vite-ui-theme", chosen),
      theme,
    )
    await page.setViewportSize({ width: 1280, height: 800 })
    const notice = await raiseNotice(page, "Order milk")

    const place = await box(notice)
    expect(place.y).toBeLessThan(40)
    expect(Math.abs(place.x + place.width / 2 - 1280 / 2)).toBeLessThan(2)
    // Nothing is left at the bottom of the screen.
    expect(place.y + place.height).toBeLessThan(800 / 2)
  })
}

test.describe("On a phone", () => {
  test.use({
    viewport: { width: 375, height: 812 },
    hasTouch: true,
    isMobile: true,
  })

  test("A notice runs the screen's width between 16px gutters, at the top", async ({
    page,
  }) => {
    await newUser(page)
    const notice = await raiseNotice(page, "Order milk")

    const place = await box(notice)
    expect(place.y).toBeLessThan(40)
    expect(Math.abs(place.x - 16)).toBeLessThan(2)
    expect(Math.abs(place.x + place.width - (375 - 16))).toBeLessThan(2)
    // Its text actions are targets a thumb can hit.
    for (const name of ["Open", "Undo"]) {
      const action = await notice.getByRole("button", { name }).boundingBox()
      expect(action?.height).toBeGreaterThanOrEqual(44)
    }
  })
})

test("A notice's actions are reached from the keyboard, Open before Undo", async ({
  page,
}) => {
  await newUser(page)
  const notice = await raiseNotice(page, "Order milk")

  // The notifications region answers to its hotkey, then Tab walks in.
  await page.keyboard.press("Alt+KeyT")
  await expect(page.locator("[data-sonner-toaster]")).toBeFocused()
  const names: string[] = []
  for (let step = 0; step < 6 && !names.includes("Undo"); step++) {
    await page.keyboard.press("Tab")
    const name = await page.evaluate(
      () => document.activeElement?.textContent?.trim() ?? "",
    )
    if (name) names.push(name)
  }
  expect(names.filter((name) => ["Open", "Undo"].includes(name))).toEqual([
    "Open",
    "Undo",
  ])

  await page.keyboard.press("Enter")
  await expect(notice).toHaveCount(0)
  const api = await userApi(page)
  await expect
    .poll(async () => (await (await api.get("/tasks/")).json()).count)
    .toBe(0)
})

test("A notice raised from inside a panel is at the top of the screen too", async ({
  page,
}) => {
  await newUser(page)
  await page.setViewportSize({ width: 1280, height: 800 })
  const api = await userApi(page)
  const task = await api.create("/tasks/", { title: "Renew the lease" })
  await api.create(`/tasks/${task.id}/comments/`, { body: "Sign it by Friday" })

  await page.goto(`/tasks?task=${task.id}`)
  const panel = page.getByRole("complementary", { name: "Renew the lease" })
  await panel
    .getByRole("listitem")
    .filter({ hasText: "Sign it by Friday" })
    .getByRole("button", { name: "Delete comment" })
    .click()

  const notice = page
    .locator("[data-sonner-toast]")
    .filter({ hasText: "Comment deleted" })
  const place = await box(notice)
  // The panel is a column at the right edge; the notice is still centred on
  // the screen, not on the column it is raised from.
  expect(place.y).toBeLessThan(40)
  expect(Math.abs(place.x + place.width / 2 - 1280 / 2)).toBeLessThan(2)
  // And its action works from there, the column being no modal.
  await notice.getByRole("button", { name: "Undo" }).click()
  await expect(panel.getByText("Sign it by Friday")).toBeVisible()
})

test("Undo of a line's task leaves it, and says why, once it has subtasks", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const notice = await raiseNotice(page, "Plan the trip")
  const [task] = (await (await api.get("/tasks/")).json()).data
  await api.create("/tasks/", { title: "Book flights", parent_id: task.id })

  await notice.getByRole("button", { name: "Undo" }).click()
  await expect(
    page
      .locator("[data-sonner-toast]")
      .filter({ hasText: "has subtasks now, so it was not removed" }),
  ).toBeVisible()
  const { count } = await (await api.get("/tasks/")).json()
  expect(count).toBe(2)
})

test("The same title sent twice while the first is on its way is not handed back to the line", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await page.goto("/")
  // Hold the first request so the second Enter finds it still in flight.
  await page.route("**/api/v1/tasks/", async (route) => {
    if (route.request().method() === "POST") {
      await new Promise((resolve) => setTimeout(resolve, 600))
    }
    await route.continue()
  })
  const line = page.getByRole("combobox", { name: "Add a task" })
  await line.fill("Water the plants")
  await line.press("Enter")
  await line.fill("Water the plants")
  await line.press("Enter")

  await expect(line).toHaveValue("")
  await expect
    .poll(async () => (await (await api.get("/tasks/")).json()).count)
    .toBe(1)
  await page.waitForTimeout(800)
  await expect(line).toHaveValue("")
})
