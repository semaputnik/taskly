import { expect, type Page, test } from "@playwright/test"
import { isoDay } from "../src/lib/dates"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

const MEASURE = 820
const PAGES = ["/", "/tasks", "/bots", "/activity"]

/** A reader with a task and a bot user, and the ids to open them by. */
async function scene(page: Page, longTitle = "Pay the rent") {
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", {
    title: longTitle,
    due_date: isoDay(new Date()),
  })
  const bot = await api.create("/bot-users/", {
    name: "Triage agent",
    scope: { project_ids: [], permissions: {} },
  })
  return { task, bot }
}

/** Where a page's column sits, measured from the main area's content box. */
async function placeOf(page: Page) {
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
  return page.evaluate(() => {
    const main = document.querySelector("main")
    const column = main?.querySelector(".page-column")
    if (!main || !column) throw new Error("No page column")
    const style = getComputedStyle(main)
    const box = main.getBoundingClientRect()
    const left = box.left + Number.parseFloat(style.paddingLeft)
    const right = box.right - Number.parseFloat(style.paddingRight)
    const at = column.getBoundingClientRect()
    return {
      gapLeft: at.left - left,
      gapRight: right - at.right,
      width: at.width,
      right: at.right,
    }
  })
}

const sideways = (page: Page) =>
  page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  )

for (const width of [1280, 1440, 1920, 2560]) {
  test(`At ${width}px every page holds one measure and centres it while no record is open`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 })
    await scene(page)

    const widths = new Set<number>()
    for (const path of PAGES) {
      await page.goto(path)
      const place = await placeOf(page)
      widths.add(Math.round(place.width))
      expect(place.width).toBeCloseTo(MEASURE, 0)
      expect(place.gapLeft).toBeGreaterThan(0)
      expect(place.gapLeft).toBeCloseTo(place.gapRight, 0)
    }
    expect([...widths]).toEqual([MEASURE])
  })
}

test("An open record takes the right and the page column moves left to sit beside it", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1920, height: 900 })
  const { task, bot } = await scene(page)

  const opened = [
    ["/", `/?task=${task.id}`],
    ["/tasks", `/tasks?task=${task.id}`],
    ["/bots", `/bots?bot=${bot.id}`],
    ["/activity", `/activity?task=${task.id}`],
  ]
  for (const [closed, open] of opened) {
    await page.goto(closed)
    const before = await placeOf(page)
    expect(before.gapLeft).toBeGreaterThan(100)

    await page.goto(open)
    const column = page.locator("[data-record-column]")
    await expect(column).toBeVisible()
    // The page settles against the left edge, whole, and ends before the
    // record column begins.
    await expect
      .poll(async () => (await placeOf(page)).gapLeft, { timeout: 3000 })
      .toBeCloseTo(0, 0)
    const beside = await placeOf(page)
    expect(beside.width).toBeCloseTo(MEASURE, 0)
    const record = await column.boundingBox()
    expect(beside.right).toBeLessThanOrEqual((record?.x ?? 0) + 0.5)
    expect(record?.width).toBeCloseTo(560, 0)
  }

  // Closing it brings the column back to the centre.
  await page.keyboard.press("Escape")
  await expect(page.locator("[data-record-column]")).toHaveCount(0)
  await expect
    .poll(async () => (await placeOf(page)).gapLeft, { timeout: 3000 })
    .toBeGreaterThan(100)
})

test("A walk with the arrow keys leaves the page column where it is", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1920, height: 900 })
  const { task } = await scene(page)
  const api = await userApi(page)
  await api.create("/tasks/", { title: "Book the vet" })
  await page.goto(`/tasks?task=${task.id}`)
  await expect(page.locator("[data-record-column]")).toBeVisible()
  await expect
    .poll(async () => (await placeOf(page)).gapLeft, { timeout: 3000 })
    .toBeCloseTo(0, 0)

  const column = page.locator("[data-record-column]")
  await column.focus()
  const first = await page
    .getByRole("link", { name: "Book the vet" })
    .boundingBox()
  await page.keyboard.press("ArrowDown")
  await page.keyboard.press("ArrowUp")
  const after = await page
    .getByRole("link", { name: "Book the vet" })
    .boundingBox()
  expect(after?.x).toBeCloseTo(first?.x ?? 0, 0)
  expect(after?.y).toBeCloseTo(first?.y ?? 0, 0)
})

test("Where there is room beside the shell's own columns, 768 to 1199px still centres the page", async ({
  page,
}) => {
  await scene(page)
  for (const width of [1024, 1180]) {
    await page.setViewportSize({ width, height: 900 })
    for (const path of PAGES) {
      await page.goto(path)
      const place = await placeOf(page)
      const room = width - 200 - 96
      expect(place.width).toBeCloseTo(Math.min(MEASURE, room), 0)
      expect(place.gapLeft).toBeCloseTo(place.gapRight, 0)
    }
  }
})

test("Asked for less motion, the page column does not glide", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" })
  await page.setViewportSize({ width: 1920, height: 900 })
  await scene(page)
  await page.goto("/tasks")
  await expect(page.locator("main .page-column")).toHaveCSS(
    "transition-duration",
    "0s",
  )
})

for (const [width, height] of [
  [375, 812],
  [390, 844],
]) {
  test(`At ${width}px no page scrolls sideways and its column fills the screen`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height })
    await scene(
      page,
      `${"Extraordinarily".repeat(6)} ${"long ".repeat(12)}title`,
    )
    for (const path of PAGES) {
      await page.goto(path)
      const place = await placeOf(page)
      expect(await sideways(page)).toBeLessThanOrEqual(0)
      expect(place.gapLeft).toBeCloseTo(0, 0)
      expect(place.width).toBeCloseTo(width - 32, 0)
    }
  })
}
