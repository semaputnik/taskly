import { expect, type Page, test } from "@playwright/test"
import { isoDay } from "../src/lib/dates"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

const TITLES = ["Pay the rent", "Book the vet", "Call the plumber"]

/** Three tasks on the day page's date bands, and the order they are shown in. */
async function dayPage(page: Page) {
  await newUser(page)
  const api = await userApi(page)
  const today = isoDay(new Date())
  for (const title of TITLES) {
    await api.create("/tasks/", { title, due_date: today })
  }
  await page.goto("/")
  const links = page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: /^Due today/ }) })
    .getByRole("link", { name: new RegExp(TITLES.join("|")) })
  await expect(links).toHaveCount(3)
  const order = await links.allTextContents()
  return {
    api,
    order,
    link: (title: string) => links.filter({ hasText: title }),
  }
}

const column = (page: Page, name?: string) =>
  name
    ? page.getByRole("complementary", { name })
    : page.locator("[data-record-column]")

test("A task opens in a 560px column and the page beside it stays live", async ({
  page,
}) => {
  const { order, link } = await dayPage(page)
  await link(order[0]).click()

  const panel = column(page, order[0])
  await expect(panel).toBeVisible()
  const place = await panel.boundingBox()
  expect(place?.width).toBeCloseTo(560, 0)
  expect((place?.x ?? 0) + (place?.width ?? 0)).toBeCloseTo(1280, 0)
  // A hairline on its left, and nothing laid over the page.
  await expect(panel).toHaveCSS("border-left-width", "1px")
  await expect(page.locator("[data-slot=sheet-overlay]")).toHaveCount(0)

  // The page is neither inert nor hidden from a screen reader: its capture
  // line takes focus and typing while the column is open.
  const line = page.getByRole("combobox", { name: "Add a task" })
  await line.click()
  await line.fill("Still typing")
  await expect(line).toHaveValue("Still typing")
  await expect(line).toBeFocused()
  await expect(panel).toBeVisible()

  // The line that is open is marked, as it is tinted (the router's own
  // aria-current on the link that points at where the reader is).
  await expect(link(order[0])).toHaveAttribute("aria-current", "page")
})

test("Escape and the close control close it, and Back brings it back", async ({
  page,
}) => {
  const { order, link } = await dayPage(page)
  await link(order[0]).click()
  await expect(page).toHaveURL(/task=[0-9a-f-]{36}/)

  await page.keyboard.press("Escape")
  await expect(column(page)).toHaveCount(0)
  await expect(page).not.toHaveURL(/task=/)

  await page.goBack()
  await expect(column(page, order[0])).toBeVisible()

  await column(page).getByRole("button", { name: "Close" }).click()
  await expect(column(page)).toHaveCount(0)
  await expect(page).not.toHaveURL(/task=/)
})

test("Opening focuses the column, closing gives focus back to the line", async ({
  page,
}) => {
  const { order, link } = await dayPage(page)
  const opener = link(order[1])
  await opener.focus()
  await page.keyboard.press("Enter")

  const panel = column(page, order[1])
  await expect(panel).toBeFocused()

  await page.keyboard.press("Escape")
  await expect(column(page)).toHaveCount(0)
  await expect(opener).toBeFocused()
})

test("Next and previous walk the list the task was opened from", async ({
  page,
}) => {
  const { order, link } = await dayPage(page)
  await link(order[0]).click()
  const panel = column(page, order[0])

  await expect(panel).toContainText("1 of 3")
  await expect(panel.getByRole("button", { name: "Next task" })).toBeVisible()
  await expect(
    panel.getByRole("button", { name: "Previous task" }),
  ).toHaveAttribute("aria-disabled", "true")

  await panel.getByRole("button", { name: "Next task" }).click()
  await expect(column(page, order[1])).toContainText("2 of 3")
  await expect(link(order[1])).toHaveAttribute("aria-current", "page")

  // The keyboard walks too, from anywhere that is not a field or a menu.
  await page.keyboard.press("ArrowDown")
  await expect(column(page, order[2])).toContainText("3 of 3")
  await expect(
    column(page).getByRole("button", { name: "Next task" }),
  ).toHaveAttribute("aria-disabled", "true")
  await page.keyboard.press("ArrowDown")
  await expect(column(page, order[2])).toBeVisible()
  await page.keyboard.press("ArrowUp")
  await expect(column(page, order[1])).toContainText("2 of 3")

  // Walking is one visit: Back leaves the column rather than retracing it.
  await page.goBack()
  await expect(column(page)).toHaveCount(0)
})

test("After a walk, closing gives focus to the line now open", async ({
  page,
}) => {
  const { order, link } = await dayPage(page)
  await link(order[0]).click()
  await expect(column(page, order[0])).toBeVisible()
  await page.keyboard.press("ArrowDown")
  await expect(column(page, order[1])).toBeVisible()

  await page.keyboard.press("Escape")
  await expect(column(page)).toHaveCount(0)
  await expect(link(order[1])).toBeFocused()
})

test("The arrows leave a field, a select and a menu their keys", async ({
  page,
}) => {
  const { order, link } = await dayPage(page)
  await link(order[0]).click()
  const panel = column(page, order[0])

  // Typing in the title: the caret moves, the task does not.
  const title = panel.getByRole("textbox", { name: "Task title" })
  await title.focus()
  await page.keyboard.press("ArrowDown")
  await page.keyboard.press("ArrowUp")
  await expect(column(page, order[0])).toBeVisible()

  // An open select: the arrow picks an option.
  await panel.getByRole("combobox", { name: "Status" }).click()
  await expect(page.getByRole("listbox")).toBeVisible()
  await page.keyboard.press("ArrowDown")
  await expect(column(page, order[0])).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(page.getByRole("listbox")).toHaveCount(0)
  // The Escape closed the select, not the column.
  await expect(column(page, order[0])).toBeVisible()
})

test("A task opened from nowhere in a list has nothing to walk", async ({
  page,
}) => {
  const { api } = await dayPage(page)
  const task = (await (await api.get("/tasks/")).json()).data[0]
  await page.goto(`/activity?task=${task.id}`)

  const panel = column(page, task.title)
  await expect(panel).toBeVisible()
  await expect(panel.getByRole("button", { name: "Close" })).toBeVisible()
  await expect(panel.getByRole("button", { name: "Next task" })).toHaveCount(0)
  await expect(
    panel.getByRole("button", { name: "Previous task" }),
  ).toHaveCount(0)
  await page.keyboard.press("ArrowDown")
  await expect(column(page, task.title)).toBeVisible()
})

test("The bar's controls are targets of at least 24px", async ({ page }) => {
  const { order, link } = await dayPage(page)
  await link(order[0]).click()
  const panel = column(page, order[0])
  for (const name of ["Previous task", "Next task", "Close"]) {
    const place = await panel.getByRole("button", { name }).boundingBox()
    expect(place?.width).toBeGreaterThanOrEqual(24)
    expect(place?.height).toBeGreaterThanOrEqual(24)
  }
})

test("The full draft opens in the same column", async ({ page }) => {
  await newUser(page)
  await page.keyboard.press("c")

  const panel = column(page, "New task")
  await expect(panel).toBeVisible()
  const place = await panel.boundingBox()
  expect(place?.width).toBeCloseTo(560, 0)
  await expect(page.locator("[data-slot=sheet-overlay]")).toHaveCount(0)
})

test("A notice's Open never closes the column, however soon it is pressed", async ({
  page,
}) => {
  await newUser(page)
  await page.keyboard.press("c")
  const title = page.getByRole("textbox", { name: "Task title" })
  await title.fill("Order milk")
  await title.press("Enter")

  // The draft closes on a single capture and its notice is the receipt; Open
  // is pressed at once, while the draft's column is still on its way out.
  await page
    .locator("[data-sonner-toast]")
    .filter({ hasText: "Order milk" })
    .getByRole("button", { name: "Open" })
    .click()
  await expect(page).toHaveURL(/task=[0-9a-f-]{36}/)
  await page.waitForTimeout(600)
  await expect(column(page, "Order milk")).toBeVisible()
  await expect(page).toHaveURL(/task=[0-9a-f-]{36}/)
})

test("A notice pressed beside an open column leaves it open", async ({
  page,
}) => {
  const { order, link } = await dayPage(page)
  await link(order[0]).click()
  await expect(column(page, order[0])).toBeVisible()

  const line = page.getByRole("combobox", { name: "Add a task" })
  await line.fill("Order milk")
  await line.press("Enter")
  const notice = page
    .locator("[data-sonner-toast]")
    .filter({ hasText: "Order milk" })
  await notice.getByText("Order milk").click()
  await expect(column(page, order[0])).toBeVisible()
  await expect(page).toHaveURL(/task=[0-9a-f-]{36}/)
})

test.describe("On a phone", () => {
  test.use({
    viewport: { width: 375, height: 812 },
    hasTouch: true,
    isMobile: true,
  })

  test("The column takes the whole screen, with a close control at the top", async ({
    page,
  }) => {
    const { order, link } = await dayPage(page)
    await link(order[0]).click()

    const panel = column(page, order[0])
    await expect(panel).toBeVisible()
    const place = await panel.boundingBox()
    expect(place?.x).toBe(0)
    expect(place?.y).toBe(0)
    expect(place?.width).toBe(375)
    expect(place?.height).toBe(812)

    const close = await panel
      .getByRole("button", { name: "Close" })
      .boundingBox()
    expect(close?.y).toBeLessThan(60)
    expect(close?.width).toBeGreaterThanOrEqual(44)
    expect(close?.height).toBeGreaterThanOrEqual(44)

    await panel.getByRole("button", { name: "Close" }).tap()
    await expect(column(page)).toHaveCount(0)
  })
})
