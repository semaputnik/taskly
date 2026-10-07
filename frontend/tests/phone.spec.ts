import { expect, type Page, test } from "@playwright/test"
import { firstSuperuser } from "./config.ts"
import { newUser, userApi } from "./utils/account"
import { logInUser } from "./utils/user"

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
const addControl = (page: Page) =>
  page.getByRole("button", { name: "Add a task" })
const bar = (page: Page) => page.getByRole("navigation", { name: "Main" })
const sheet = (page: Page) => page.getByRole("dialog", { name: "Add a task" })

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

const SCREENS = [
  "/",
  "/tasks",
  "/bots",
  "/activity",
  "/projects",
  "/tags",
  "/settings",
]

test("The bar at the bottom has five items on every screen, and nothing else adds a task", async ({
  page,
}) => {
  await newUser(page)

  for (const path of SCREENS) {
    await page.goto(path)
    const items = bar(page)
    await expect(items).toBeVisible()
    for (const name of ["Today", "Tasks", "Bots", "Activity"]) {
      await expect(items.getByRole("link", { name })).toBeVisible()
    }
    await expect(items.getByRole("listitem")).toHaveCount(5)

    // It is the foot of the screen, 56px tall, its targets 44px or more.
    const place = await boxOf(items)
    expect(place.y + place.height).toBe(812)
    expect(place.height).toBe(57) // 56px and its hairline
    for (const control of await items
      .getByRole("link")
      .or(items.getByRole("button"))
      .all()) {
      const target = await boxOf(control)
      expect(target.height).toBeGreaterThanOrEqual(44)
      expect(target.width).toBeGreaterThanOrEqual(44)
    }

    // The line and the floating button are gone: the bar's control is the
    // only way to add, and it is one control.
    await expect(line(page)).toHaveCount(0)
    await expect(addControl(page)).toHaveCount(1)
  }
})

test("The current screen is stated and marked by weight, not by colour", async ({
  page,
}) => {
  await newUser(page)
  const weight = (name: string) =>
    bar(page)
      .getByRole("link", { name })
      .evaluate((element) => Number(getComputedStyle(element).fontWeight))

  await page.goto("/bots")
  const bots = bar(page).getByRole("link", { name: "Bots" })
  await expect(bots).toHaveAttribute("aria-current", "page")
  await expect(
    bar(page).getByRole("link", { name: "Today" }),
  ).not.toHaveAttribute("aria-current", "page")
  expect(await weight("Bots")).toBeGreaterThan(await weight("Today"))

  // Labels are 12px; a resting one is ink-2 and the current one ink, and
  // only the current one has the short hairline above its label.
  const look = (name: string) =>
    bar(page)
      .getByRole("link", { name })
      .evaluate((element) => {
        const own = getComputedStyle(element)
        const mark = getComputedStyle(element, "::before")
        return {
          size: own.fontSize,
          color: own.color,
          mark: mark.backgroundColor,
          markHeight: mark.height,
        }
      })
  const current = await look("Bots")
  const resting = await look("Today")
  expect(current.size).toBe("12px")
  expect(resting.size).toBe("12px")
  expect(resting.color).not.toBe(current.color)
  expect(current.mark).toBe(current.color)
  expect(resting.mark).toBe("rgba(0, 0, 0, 0)")

  // Today is the root, which every path starts with: it is current only on
  // the day page.
  await page.goto("/tasks")
  await expect(bar(page).getByRole("link", { name: "Tasks" })).toHaveAttribute(
    "aria-current",
    "page",
  )
  await expect(
    bar(page).getByRole("link", { name: "Today" }),
  ).not.toHaveAttribute("aria-current", "page")

  // A tap goes there.
  await bar(page).getByRole("link", { name: "Activity" }).tap()
  await expect(page).toHaveURL(/\/activity/)
})

test("The add control raises a capture sheet on any screen, and the page has no pinned line", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  for (let n = 1; n <= 25; n++) {
    await api.create("/tasks/", { title: `Task number ${n}` })
  }

  await page.goto("/")
  await expect(line(page)).toHaveCount(0)

  await page.goto("/tasks")
  await expect(line(page)).toHaveCount(0)
  // Scrolled to the foot, the last row is clear of the bar.
  await expect(page.locator("main").getByRole("link").nth(20)).toBeVisible()
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  await page.waitForTimeout(150)
  const last = await boxOf(page.locator("main").getByRole("link").last())
  expect(last.y + last.height).toBeLessThan((await boxOf(bar(page))).y)

  await addControl(page).tap()
  await expect(sheet(page)).toBeVisible()
  // Focus is moved in, to the line, which keeps the 16px iOS needs.
  await expect(line(page)).toBeFocused()
  const size = await line(page).evaluate(
    (element) => getComputedStyle(element).fontSize,
  )
  expect(Number.parseFloat(size)).toBeGreaterThanOrEqual(16)
  expect((await boxOf(line(page))).height).toBeGreaterThanOrEqual(44)
  // The sheet rests on the bottom edge, over a dimmed page.
  await expect
    .poll(async () => {
      const place = await boxOf(sheet(page))
      return place.y + place.height
    })
    .toBeCloseTo(812, 0)
})

test("The sheet follows the keyboard, and Return writes a task from Bots", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/bots")
  await addControl(page).tap()
  await expect(sheet(page)).toBeVisible()
  // At rest on the bottom edge: it is visible from the first frame of its
  // slide, so it is waited for there rather than measured on the way.
  await expect
    .poll(async () => {
      const place = await boxOf(sheet(page))
      return place.y + place.height
    })
    .toBeCloseTo(812, 0)

  await raiseKeyboard(page, 300)
  await expect
    .poll(async () => {
      const place = await boxOf(sheet(page))
      return place.y + place.height
    })
    .toBeCloseTo(812 - 300, 0)

  // Nothing to send while nothing is written.
  const create = sheet(page).getByRole("button", { name: "Create", exact: true })
  await expect(create).toHaveCount(0)
  await line(page).fill("Buy milk")
  // The action is a word, visible, and a tap on it leaves the keyboard up.
  await expect(create).toHaveText("Create")
  await create.tap()
  await expect(page.getByText("“Buy milk” created")).toBeVisible()
  // Done: the sheet gives way to the screen, which stays where it was, and
  // focus goes back to the control that raised it.
  await expect(sheet(page)).toBeHidden()
  await expect(page).toHaveURL(/\/bots/)
  await expect(addControl(page)).toBeFocused()

  const api = await userApi(page)
  await expect
    .poll(async () => (await (await api.get("/tasks/")).json()).count)
    .toBe(1)

  // Return does the same.
  await addControl(page).tap()
  await line(page).fill("Call the bank")
  await line(page).press("Enter")
  await expect(page.getByText("“Call the bank” created")).toBeVisible()
  await expect(sheet(page)).toBeHidden()
})

test("The sheet's matches stand above the line and above the keyboard, and a tap opens one", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  for (const title of ["Redirect the old URLs", "Check the redirect map"]) {
    await api.create("/tasks/", { title })
  }
  await page.goto("/activity")

  await addControl(page).tap()
  await raiseKeyboard(page, 300)
  await line(page).fill("redirect")
  const list = page.getByRole("listbox", { name: /^Open tasks matching/ })
  await expect(list.getByRole("option")).toHaveCount(2)

  const above = await boxOf(list)
  const field = await boxOf(line(page))
  expect(above.y + above.height).toBeLessThanOrEqual(field.y)
  expect(above.y).toBeGreaterThanOrEqual(0)
  for (const option of await list.getByRole("option").all()) {
    expect((await boxOf(option)).height).toBeGreaterThanOrEqual(44)
  }

  // A tap on a match opens it, and the sheet is done.
  await list.getByRole("option").first().tap()
  await expect(page.locator("[data-record-column]")).toBeVisible()
  await expect(sheet(page)).toBeHidden()
})

test("Escape or a tap outside closes the sheet and keeps the words", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/bots")
  await addControl(page).tap()
  await line(page).fill("Ring the plumber")

  // The first Escape closes the matches, the second the sheet.
  await page.keyboard.press("Escape")
  await expect(sheet(page)).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(sheet(page)).toBeHidden()
  await expect(addControl(page)).toBeFocused()

  await addControl(page).tap()
  await expect(line(page)).toHaveValue("Ring the plumber")

  // A tap on the dimmed page above it does the same.
  await page.touchscreen.tap(190, 100)
  await expect(sheet(page)).toBeHidden()
  await addControl(page).tap()
  await expect(line(page)).toHaveValue("Ring the plumber")
})

test("Add details opens the full draft with what was typed", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/activity")
  await addControl(page).tap()
  await line(page).fill("Write the report")
  await sheet(page).getByRole("button", { name: "Add details…" }).tap()

  await expect(sheet(page)).toBeHidden()
  await expect(page).toHaveURL(/capture=task/)
  const draft = page.getByRole("complementary", { name: "New task" })
  await expect(draft).toBeVisible()
  await expect(draft.getByRole("textbox", { name: "Task title" })).toHaveValue(
    "Write the report",
  )
  // The draft covers the screen and takes the bar with it.
  await expect(bar(page)).toBeHidden()

  // The sheet's words went with it: raised again, the line is empty.
  await draft.getByRole("textbox", { name: "Task title" }).fill("")
  await page.getByRole("button", { name: "Close" }).tap()
  await expect(page.locator("[data-record-column]")).toHaveCount(0)
  await addControl(page).tap()
  await expect(line(page)).toHaveValue("")
})

test("Words left in a closed sheet put a dot on the add control, which goes with them", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/bots")
  const dot = page.getByTestId("draft-kept")
  await expect(dot).toHaveCount(0)

  await addControl(page).tap()
  await line(page).fill("Ring the plumber")
  // Open, the sheet holds the words itself: no dot yet.
  await expect(dot).toHaveCount(0)
  await page.keyboard.press("Escape")
  await page.keyboard.press("Escape")
  await expect(sheet(page)).toBeHidden()
  await expect(dot).toBeVisible()
  const kept = page.getByRole("button", { name: "Add a task, draft kept" })
  await expect(kept).toBeVisible()

  // Clearing the words takes the dot away.
  await kept.tap()
  await line(page).fill("")
  await page.keyboard.press("Escape")
  await expect(sheet(page)).toBeHidden()
  await expect(dot).toHaveCount(0)
  await expect(addControl(page)).toHaveCount(1)

  // So does making the task.
  await addControl(page).tap()
  await line(page).fill("Call the bank")
  await page.keyboard.press("Escape")
  await page.keyboard.press("Escape")
  await expect(dot).toBeVisible()
  await addControl(page).tap()
  await line(page).press("Enter")
  await expect(sheet(page)).toBeHidden()
  await expect(dot).toHaveCount(0)
})

test("The dark sheet is a step lighter than the page, with a hairline at its top", async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("vite-ui-theme", "dark"),
  )
  await newUser(page)
  await page.goto("/bots")
  await expect(page.locator("html")).toHaveClass(/dark/)
  await addControl(page).tap()
  await expect(sheet(page)).toBeVisible()
  const look = await sheet(page).evaluate((element) => {
    const own = getComputedStyle(element)
    return {
      ground: own.backgroundColor,
      page: getComputedStyle(document.body).backgroundColor,
      edge: own.borderTopColor,
      edgeWidth: own.borderTopWidth,
    }
  })
  expect(look.ground).not.toBe(look.page)
  expect(look.edgeWidth).toBe("1px")
  expect(look.edge).not.toBe("rgba(0, 0, 0, 0)")
})

test("The bar gives way to a record's full-screen column", async ({ page }) => {
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", { title: "Pay the invoice" })
  await page.goto("/tasks")
  await expect(bar(page)).toBeVisible()

  await page.goto(`/tasks?task=${task.id}`)
  await expect(page.locator("[data-record-column]")).toBeVisible()
  await expect(bar(page)).toBeHidden()

  await page.getByRole("button", { name: "Close" }).tap()
  await expect(page.locator("[data-record-column]")).toHaveCount(0)
  await expect(bar(page)).toBeVisible()
})

test("The account control holds the other screens and signing out", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/")
  const account = page.getByRole("button", { name: "Menu", exact: true })
  // The top bar keeps the wordmark and gains the avatar, a target for a thumb.
  await expect(page.getByRole("link", { name: "Taskly" })).toBeVisible()
  expect((await boxOf(account)).height).toBeGreaterThanOrEqual(44)
  expect((await boxOf(account)).width).toBeGreaterThanOrEqual(44)
  // It says what it is in a word beside the avatar, so Projects is findable.
  await expect(account).toContainText("Menu")
  expect((await boxOf(account)).width).toBeGreaterThan(44)

  await account.tap()
  const menu = page.getByRole("menu")
  for (const name of ["Projects", "Tags", "Settings", "Log out"]) {
    const item = menu.getByRole("menuitem", { name })
    await expect(item).toBeVisible()
    // The menu grows into place; it is measured once it has.
    await expect
      .poll(async () => (await boxOf(item)).height)
      .toBeGreaterThanOrEqual(44)
  }
  // Appearance moved to Settings; the menu is only places and signing out.
  await expect(menu.getByRole("menuitemradio")).toHaveCount(0)
  // This account is not the superuser's: no Users entry either.
  await expect(menu.getByRole("menuitem", { name: "Users" })).toHaveCount(0)

  // The screens that are not tabs are a tap away, and none of the tabs is
  // current there. The menu is still open from the check above.
  await page.getByRole("menuitem", { name: "Projects" }).tap()
  await expect(page).toHaveURL(/\/projects/)
  await expect(bar(page).locator('[aria-current="page"]')).toHaveCount(0)

  await account.tap()
  await page.getByRole("menuitem", { name: "Log out" }).tap()
  await expect(page).toHaveURL(/\/login/)
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

test("The control row is two balanced rows at 375 and 390, and the order never sits alone", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Website relaunch" })
  await api.create("/tasks/", { title: "Anything", project_id: project.id })

  for (const width of [375, 390]) {
    await page.setViewportSize({ width, height: 812 })
    for (const search of ["", `?project_id=${project.id}`]) {
      await page.goto(`/tasks${search}`)
      const row = page.getByRole("group", { name: "Filters" })
      await expect(row).toBeVisible()
      const status = await boxOf(
        row.getByRole("button", { name: /^(Any status|Status:)/ }),
      )
      const more = await boxOf(row.getByRole("button", { name: "More" }))
      const order = await boxOf(row.getByRole("button", { name: /^Order:/ }))
      // The three filters are the first row; More and the order share the
      // second, so the order has company, whatever fits above it.
      expect(more.y).toBeGreaterThan(status.y + 20)
      expect(order.y).toBe(more.y)
      expect(order.x + order.width).toBeLessThanOrEqual(width)
    }
  }
})

test("A line whose facts fill it drops its project to a line of its own instead of cutting it", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Website relaunch" })
  await api.create("/tags/", { name: "copy" })
  await api.create("/tasks/", {
    title: "Rewrite the pricing copy",
    project_id: project.id,
    due_date: "2030-03-14",
    tags: ["copy", "pricing"],
  })

  for (const width of [375, 390]) {
    await page.setViewportSize({ width, height: 812 })
    await page.goto("/tasks")
    const item = page
      .getByRole("list", { name: "Tasks" })
      .getByRole("listitem")
      .first()
    const name = item.getByText("Website relaunch", { exact: true })
    await expect(name).toBeVisible()
    // Whole, not "Website r…".
    const cut = await name.evaluate((e) => e.scrollWidth > e.clientWidth)
    expect(cut).toBe(false)
    // And inside the line.
    const line = await boxOf(item)
    const place = await boxOf(name)
    expect(place.x + place.width).toBeLessThanOrEqual(line.x + line.width)
  }
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
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
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

test("The superuser's account menu has Users, which lands on that section of Settings", async ({
  page,
}) => {
  await logInUser(page, firstSuperuser)
  await page.getByRole("button", { name: "Menu", exact: true }).tap()
  await page.getByRole("menuitem", { name: "Users" }).tap()

  await expect(page).toHaveURL(/\/settings#users$/)
  await expect(page.getByRole("region", { name: "Users" })).toBeVisible()
  // Admin is gone as an entry.
  await page.getByRole("button", { name: "Menu", exact: true }).tap()
  await expect(page.getByRole("menuitem", { name: "Admin" })).toHaveCount(0)
})

test("The task column's bar keeps the date whole beside the walk count, and its mark is a thumb's size", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tasks/", { title: "Pay the invoice" })
  await api.create("/tasks/", { title: "Book the vet" })
  await page.goto("/tasks")
  await page.getByRole("link", { name: "Pay the invoice" }).tap()
  const column = page.getByRole("complementary", { name: "Pay the invoice" })
  await expect(column).toBeVisible()

  // The date is whole and clear of the "1 of 1" beside it.
  const opened = column.getByText(/^opened by you, /)
  await expect(opened).toBeVisible()
  const date = await boxOf(opened)
  const count = await boxOf(column.getByText(/^\d of 2$/))
  expect(date.x + date.width).toBeLessThanOrEqual(count.x)
  // The project is left for a screen reader; the Project row says it.
  await expect(column.getByRole("combobox", { name: "Project" })).toContainText(
    "Inbox",
  )

  // The Created row's text is level with its label in a 44px row.
  const label = await boxOf(column.getByText("Created", { exact: true }))
  const created = await boxOf(
    column.getByRole("group", { name: "Created" }).locator("time"),
  )
  expect(
    Math.abs(label.y + label.height / 2 - (created.y + created.height / 2)),
  ).toBeLessThanOrEqual(2)

  // 44px target, named for what it does.
  const mark = column.getByRole("checkbox", { name: /^Mark done/ })
  const box = await boxOf(mark)
  expect(box.width).toBeGreaterThanOrEqual(44)
  expect(box.height).toBeGreaterThanOrEqual(44)

  // A saved field says so in the bar, in place of the context while it is up.
  await column.getByRole("combobox", { name: "Priority" }).tap()
  await page.getByRole("option", { name: /P2/ }).tap()
  const cue = column.locator("[data-save-cue]")
  await expect(cue).toHaveText("Saved")
  await expect(cue).toHaveText("", { timeout: 5_000 })
})

test("The draft says nothing of a keyboard chord on a phone", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks?capture=task")
  const draft = page.getByRole("complementary", { name: "New task" })
  await expect(draft).toBeVisible()
  await expect(draft.getByRole("button", { name: "Create task" })).toBeVisible()
  await expect(draft.getByText(/Enter/)).toBeHidden()
})
