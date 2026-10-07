import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"
import { openDraft } from "./utils/capture"
import { textOn, token } from "./utils/colour"

test.use({ storageState: { cookies: [], origins: [] } })

const AA = 4.5

/** A palette token as the `rgb(...)` string a computed colour reads as. */
async function rgbOf(page: Page, name: string) {
  return page.evaluate((property) => {
    const probe = document.createElement("span")
    probe.style.color = `var(${property})`
    document.body.append(probe)
    const colour = getComputedStyle(probe).color
    probe.remove()
    return colour
  }, name)
}

async function openTask(
  page: Page,
  fields: Record<string, unknown> = {},
  theme: "light" | "dark" = "light",
) {
  await page.addInitScript((chosen) => {
    localStorage.setItem("vite-ui-theme", chosen)
  }, theme)
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", {
    title: "Migrate the marketing pages",
    ...fields,
  })
  await page.goto(`/?task=${task.id}`)
  const panel = page.getByRole("complementary", {
    name: "Migrate the marketing pages",
  })
  await expect(panel).toBeVisible()
  return { api, task, panel }
}

test("One bar says where the task sits and who opened it, then the title and the list", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const { panel } = await openTask(page, {
    priority: "P2",
    description: "Four pages off the old template.",
  })

  // One bar: the context and the controls that act on the column share it.
  const close = panel.getByRole("button", { name: "Close" })
  await expect(close).toHaveCount(1)
  const bar = close.locator("xpath=../..")
  await expect(bar).toContainText("Inbox")
  await expect(bar).toContainText("opened by you")
  expect((await bar.boundingBox())?.height).toBe(52)

  const title = panel.getByRole("textbox", { name: "Task title" })
  const style = await title.evaluate((node) => {
    const computed = getComputedStyle(node)
    return { size: computed.fontSize, weight: computed.fontWeight }
  })
  expect(style).toEqual({ size: "22px", weight: "600" })

  // The labels are a 96px column of their own, and each names its value.
  const label = panel.getByText("Project", { exact: true })
  expect((await label.boundingBox())?.width).toBe(96)
  for (const [role, name] of [
    ["combobox", "Status"],
    ["combobox", "Project"],
    ["button", "Due date: not set"],
    ["combobox", "Priority"],
    ["combobox", "Assignee"],
    ["combobox", "Repeat"],
  ] as const) {
    const control = panel.getByRole(role, { name })
    await expect(control).toBeVisible()
    expect((await control.boundingBox())?.height).toBe(30)
  }
  await expect(panel.getByRole("group", { name: "Tags" })).toBeVisible()
  await expect(panel.getByRole("group", { name: "Created" })).toContainText(
    "by you",
  )
  await expect(
    panel.getByRole("heading", { name: "Description" }),
  ).toBeVisible()
  await expect(
    panel.getByRole("textbox", { name: "Task description" }),
  ).toHaveValue("Four pages off the old template.")
})

test("A value always shows its chevron, in Ink 3, darkening when it is reached for, and every one takes a visible ring from the keyboard", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const { panel } = await openTask(page, { tags: ["copy"] })
  const priority = panel.getByRole("combobox", { name: "Priority" })
  const chevron = priority.locator("svg").last()

  // At rest: there, in the quiet ink, with no hover to reveal it.
  await expect(chevron).toHaveCSS("opacity", "1")
  const quiet = await chevron.evaluate((node) => getComputedStyle(node).color)
  expect(quiet).toBe(await rgbOf(page, "--ink-3"))
  await priority.hover()
  await expect(chevron).toHaveCSS("color", await rgbOf(page, "--ink"))
  await expect(priority).not.toHaveCSS("background-color", "rgba(0, 0, 0, 0)")
  await page.mouse.move(0, 0)
  await expect(chevron).toHaveCSS("color", quiet)
  await priority.focus()
  await expect(chevron).toHaveCSS("color", await rgbOf(page, "--ink"))
  // Every property that can change carries one, the due date's calendar
  // glyph standing in its place.
  for (const name of ["Status", "Project", "Assignee", "Repeat"]) {
    await expect(
      panel.getByRole("combobox", { name }).locator("svg").last(),
    ).toHaveCSS("opacity", "1")
  }
  await expect(
    panel.getByRole("button", { name: "Due date: not set" }).locator("svg"),
  ).toHaveCSS("opacity", "1")

  // Tab from the status, down the list: each value is a control that is
  // reached and shows a ring where it has focus.
  await panel.getByRole("combobox", { name: "Status" }).focus()
  const reached: string[] = []
  for (let step = 0; step < 9; step++) {
    await page.keyboard.press("Tab")
    const focused = await page.evaluate(() => {
      const node = document.activeElement
      if (!node) return null
      const shadow = getComputedStyle(node).boxShadow
      const name =
        node.getAttribute("aria-label") ??
        (node as HTMLElement).innerText.trim().slice(0, 20)
      return { name, ring: shadow !== "none" }
    })
    if (focused) {
      expect(focused.ring, focused.name).toBe(true)
      reached.push(focused.name)
    }
  }
  expect(reached).toEqual(
    expect.arrayContaining([
      "Inbox",
      "Due date: not set",
      "No priority",
      "Assignee",
      "Remove tag copy",
      "Add tag",
      "Does not repeat",
    ]),
  )
})

for (const theme of ["light", "dark"] as const) {
  test(`Priority is a flag and a label in its hue, clearing 4.5:1 on the page and on a hovered value (${theme})`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    const { api, task, panel } = await openTask(page, { priority: "P1" }, theme)
    const priority = panel.getByRole("combobox", { name: "Priority" })
    const ground = await token(page, "--page")
    const hover = await token(page, "--hover")

    for (const level of ["P1", "P2", "P3", "P4"]) {
      await api.patch(`/tasks/${task.id}`, { priority: level })
      await page.reload()
      await expect(priority).toContainText(level)
      const word = priority.getByText(level, { exact: true })
      if (level === "P4") {
        // The ordinary case stays in ink, as the title is.
        const colour = (node: Element) => getComputedStyle(node).color
        expect(await word.evaluate(colour)).toBe(
          await panel
            .getByRole("textbox", { name: "Task title" })
            .evaluate(colour),
        )
        continue
      }
      expect(
        await textOn(word, ground),
        `${level} on the page`,
      ).toBeGreaterThan(AA)
      expect(await textOn(word, hover), `${level} on hover`).toBeGreaterThan(AA)
    }

    // No priority is said in the quiet grey, with no flag.
    await api.patch(`/tasks/${task.id}`, { priority: null })
    await page.reload()
    await expect(priority).toHaveText("No priority")
    expect(
      await textOn(priority.getByText("No priority"), ground),
    ).toBeGreaterThan(AA)
  })
}

test("The status mark beside the title closes the task", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const { api, task, panel } = await openTask(page)

  const mark = panel.getByRole("checkbox", { name: /^Mark done/ })
  await expect(mark).toBeVisible()
  await mark.click()
  await expect(panel.getByRole("combobox", { name: "Status" })).toContainText(
    "Done",
  )
  const stored = await (await api.get(`/tasks/${task.id}`)).json()
  expect(stored.status).toBe("done")
})

test("The description is edited where it is read, and is invited when empty", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const { api, task, panel } = await openTask(page)
  const description = panel.getByRole("textbox", { name: "Task description" })

  await expect(description).toHaveAttribute("placeholder", "Add a description")
  await description.fill("Pricing copy is a separate task.")
  await panel.getByRole("textbox", { name: "Task title" }).click()
  await expect
    .poll(
      async () =>
        (await (await api.get(`/tasks/${task.id}`)).json()).description,
    )
    .toBe("Pricing copy is a separate task.")
})

test("A long title wraps instead of scrolling, and Enter saves it rather than breaking the line", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const { api, task, panel } = await openTask(page)
  const title = panel.getByRole("textbox", { name: "Task title" })
  const long =
    "Migrate the marketing pages and then the pricing pages and the docs pages as well"

  const oneLine = (await title.boundingBox())?.height ?? 0
  await title.fill(long)
  await title.press("Enter")
  await expect
    .poll(async () => (await (await api.get(`/tasks/${task.id}`)).json()).title)
    .toBe(long)
  await expect(title).toHaveValue(long)
  expect((await title.boundingBox())?.height ?? 0).toBeGreaterThan(oneLine)
})

test("The draft is the same rows under the same title and heading", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await newUser(page)
  await page.goto("/")
  await openDraft(page)
  const panel = page.getByRole("complementary", { name: "New task" })
  await expect(panel).toBeVisible()

  await expect(panel.getByRole("button", { name: "Close" })).toHaveCount(1)
  await expect(panel.getByRole("textbox", { name: "Task title" })).toBeVisible()
  for (const name of ["Project", "Priority", "Assignee", "Repeat"]) {
    await expect(panel.getByRole("combobox", { name })).toBeVisible()
  }
  await expect(panel.getByRole("button", { name: /^Due date/ })).toBeVisible()
  await expect(panel.getByRole("group", { name: "Tags" })).toBeVisible()
  await expect(
    panel.getByRole("heading", { name: "Description" }),
  ).toBeVisible()
  // Its one commit stays pinned at the foot of the column.
  const create = panel.getByRole("button", { name: "Create task" })
  const column = await panel.boundingBox()
  const button = await create.boundingBox()
  expect(
    column &&
      button &&
      button.y + button.height > column.y + column.height - 80,
  ).toBe(true)
})

test.describe("On a phone", () => {
  test.use({
    viewport: { width: 375, height: 812 },
    hasTouch: true,
    isMobile: true,
  })

  test("The list keeps 16px gutters and every value is a 44px target", async ({
    page,
  }) => {
    const { panel } = await openTask(page, { priority: "P1" })

    const label = await panel
      .getByText("Project", { exact: true })
      .boundingBox()
    expect(label?.x).toBe(16)
    for (const name of ["Project", "Priority", "Assignee", "Repeat"]) {
      const box = await panel.getByRole("combobox", { name }).boundingBox()
      expect(box?.height, name).toBeGreaterThanOrEqual(44)
    }
    const title = await panel
      .getByRole("textbox", { name: "Task title" })
      .boundingBox()
    expect(title && title.x + title.width <= 375 - 16 + 1).toBe(true)
  })
})

test("Dates in the column are said in words", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const { panel } = await openTask(page, { due_date: "2019-09-24" })

  // Filed just now: the bar and the Created row both say so in words.
  const bar = panel
    .getByRole("button", { name: "Close" })
    .locator("xpath=../..")
  await expect(bar).toContainText("opened by you, today")
  await expect(panel.getByRole("group", { name: "Created" })).toContainText(
    /^Today, \d{1,2}[:.]\d{2}/,
  )
  // A day in another year carries its year, and a month is a word.
  const due = panel.getByRole("button", { name: /^Due date:/ })
  await expect(due).toContainText("2019")
  await expect(due).toContainText(/Sep/)
  await expect(due).not.toContainText(/\d{1,2}[./]\d{1,2}[./]\d{2,4}/)
})

test("The Created row is on the type scale of the rows above it", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const { panel } = await openTask(page)
  const size = (name: string) =>
    panel
      .getByRole("group", { name })
      .evaluate(
        (node) => getComputedStyle(node.firstElementChild ?? node).fontSize,
      )
  expect(await size("Created")).toBe("15px")
  const label = panel.getByText("Created", { exact: true })
  // The text itself, not its box: a short value in a tall row must be level.
  const value = panel.getByRole("group", { name: "Created" }).locator("time")
  const [labelBox, valueBox] = await Promise.all([
    label.boundingBox(),
    value.boundingBox(),
  ])
  // Level with its label, not sunk below it.
  expect(
    Math.abs(
      (labelBox?.y ?? 0) +
        (labelBox?.height ?? 0) / 2 -
        ((valueBox?.y ?? 0) + (valueBox?.height ?? 0) / 2),
    ),
  ).toBeLessThanOrEqual(2)
})

test("A saved field says Saved in the bar, which fades by itself", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const { panel } = await openTask(page)
  const bar = panel
    .getByRole("button", { name: "Close" })
    .locator("xpath=../..")
  // The region that says it is there before there is anything to say.
  await expect(bar.getByRole("status")).toHaveCount(1)
  await expect(bar.getByRole("status")).toHaveAttribute("aria-live", "polite")
  await expect(bar.getByRole("status")).toHaveText("")

  await panel.getByRole("combobox", { name: "Priority" }).click()
  await page.getByRole("option", { name: /P2/ }).click()
  await expect(bar.getByRole("status")).toHaveText("Saved")
  await expect(bar.getByRole("status")).toHaveText("", { timeout: 5_000 })
})

test("A blank title is refused: the old one comes back and the field says why", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const { api, task, panel } = await openTask(page)
  let patches = 0
  await page.route(`**/api/v1/tasks/${task.id}`, (route) => {
    if (route.request().method() === "PATCH") patches += 1
    return route.fallback()
  })

  const title = panel.getByRole("textbox", { name: "Task title" })
  await title.fill("   ")
  await title.press("Enter")
  await expect(title).toHaveValue("Migrate the marketing pages")
  const reason = panel.getByText("A task needs a title")
  await expect(reason).toBeVisible()
  await expect(reason).toHaveAttribute("aria-live", "polite")
  await expect(title).toHaveAttribute("aria-describedby", /.+/)
  expect(patches).toBe(0)
  expect((await (await api.get(`/tasks/${task.id}`)).json()).title).toBe(
    "Migrate the marketing pages",
  )

  // Typing again takes the reason away.
  await title.fill("Migrate the pages")
  await expect(reason).toBeHidden()
})

test("An empty Files section says so in a sentence", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const { panel } = await openTask(page)
  await expect(
    panel.getByRole("region", { name: "Files" }).getByText(/^No files yet/),
  ).toBeVisible()
})
