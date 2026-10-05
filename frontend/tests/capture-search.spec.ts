import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

const line = (page: Page) => page.getByRole("combobox", { name: /^Add a task/ })
const matches = (page: Page) =>
  page.getByRole("listbox", { name: /^Open tasks matching/ })
const column = (page: Page, name: string) =>
  page.getByRole("complementary", { name })

/** A user with a project and a few tasks, on the task list. */
async function seed(page: Page) {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Website relaunch" })
  const make = (title: string, extra: Record<string, unknown> = {}) =>
    api.create("/tasks/", { title, project_id: project.id, ...extra })
  // Filed in this order, so the newest is the last.
  await make("Redirect the old URLs")
  await make("Check the redirect map", { status: "review" })
  await make("Rewrite the pricing copy")
  await make("Redirect archive (finished)", { status: "done" })
  await page.goto("/tasks")
  await expect(line(page)).toBeVisible()
  return { api, project }
}

test("Two characters offer the open tasks whose title has them, newest first", async ({
  page,
}) => {
  await seed(page)

  // One character searches nothing.
  await line(page).click()
  await line(page).pressSequentially("r")
  await page.waitForTimeout(400)
  await expect(matches(page)).toHaveCount(0)

  await line(page).pressSequentially("eD")
  const list = matches(page)
  await expect(list).toBeVisible()
  // Case does not matter; done work is not offered (ADR-0006); the newest
  // filed is first.
  await expect(list.getByRole("option")).toHaveText([
    /Check the redirect map.*Website relaunch/,
    /Redirect the old URLs.*Website relaunch/,
  ])
  // The matched text is bold, in the title's own case; the project is named.
  await expect(list.getByRole("option").first().locator("b")).toHaveText("red")
  await expect(list.getByRole("option").nth(1).locator("b")).toHaveText("Red")
  await expect(list.getByRole("option").first()).toContainText(
    "Website relaunch",
  )
  // The count is said aloud, and the field says what it controls.
  await expect(
    page.getByRole("status").filter({ hasText: "match" }),
  ).toHaveText("2 open tasks match")
  await expect(line(page)).toHaveAttribute("aria-expanded", "true")

  // Back under two characters, the matches go.
  await line(page).press("Backspace")
  await line(page).press("Backspace")
  await expect(line(page)).toHaveValue("r")
  await expect(matches(page)).toHaveCount(0)
})

test("A search that finds nothing says so, and still offers to create", async ({
  page,
}) => {
  await seed(page)
  await line(page).fill("zzzz")
  await expect(
    page.getByText("No open task has “zzzz” in its title"),
  ).toBeVisible()
  await expect(
    page.getByRole("status").filter({ hasText: "match" }),
  ).toHaveText("No open task matches")
  await expect(page.getByText("creates “zzzz” in Inbox")).toBeVisible()
})

test("At most eight are offered", async ({ page }) => {
  const { api, project } = await seed(page)
  for (let index = 0; index < 10; index++) {
    await api.create("/tasks/", {
      title: `Errand ${index}`,
      project_id: project.id,
    })
  }
  await page.reload()
  await line(page).fill("errand")
  await expect(matches(page).getByRole("option")).toHaveCount(8)
  // The newest eight: the first two filed are left out.
  await expect(matches(page)).not.toContainText("Errand 0")
  await expect(matches(page)).not.toContainText("Errand 1")
  await expect(matches(page)).toContainText("Errand 9")
})

test("Enter still creates a task from the typed text, whatever is offered", async ({
  page,
}) => {
  await seed(page)
  await line(page).fill("redirect")
  await expect(matches(page)).toBeVisible()

  await line(page).press("Enter")
  await expect(
    page.locator("[data-sonner-toast]").filter({ hasText: "created" }),
  ).toContainText("“redirect” created in Inbox")
  await expect(line(page)).toHaveValue("")
  await expect(matches(page)).toHaveCount(0)
  await expect(page.locator("[data-record-column]")).toHaveCount(0)
})

test("The arrow keys move through the matches and Enter opens the chosen one", async ({
  page,
}) => {
  await seed(page)
  await line(page).fill("redirect")
  const options = matches(page).getByRole("option")
  await expect(options).toHaveCount(2)
  await expect(options.first()).toHaveAttribute("aria-selected", "false")

  await line(page).press("ArrowDown")
  await expect(options.first()).toHaveAttribute("aria-selected", "true")
  await expect(line(page)).toHaveAttribute(
    "aria-activedescendant",
    (await options.first().getAttribute("id")) ?? "",
  )
  await line(page).press("ArrowDown")
  await expect(options.nth(1)).toHaveAttribute("aria-selected", "true")
  await expect(options.first()).toHaveAttribute("aria-selected", "false")
  await line(page).press("ArrowUp")
  await expect(options.first()).toHaveAttribute("aria-selected", "true")

  await line(page).press("ArrowDown")
  await line(page).press("Enter")
  await expect(column(page, "Redirect the old URLs")).toBeVisible()
  // Opening found the task, so nothing was created and the line is free.
  await expect(line(page)).toHaveValue("")
  await expect(matches(page)).toHaveCount(0)
  const tasks = (await (await (await userApi(page)).get("/tasks/")).json()).data
  expect(tasks).toHaveLength(4)
})

test("The arrows move through the matches without walking the open task's list", async ({
  page,
}) => {
  await seed(page)
  // The list's second line opens in the column, with a neighbour each way.
  await page.getByRole("link", { name: "Check the redirect map" }).click()
  await expect(column(page, "Check the redirect map")).toBeVisible()
  const opened = new URL(page.url()).searchParams.get("task")

  await line(page).click()
  await line(page).fill("redirect")
  await expect(matches(page)).toBeVisible()
  await line(page).press("ArrowDown")
  await line(page).press("ArrowDown")

  await expect(matches(page).getByRole("option").nth(1)).toHaveAttribute(
    "aria-selected",
    "true",
  )
  // The column stayed on the task it was on.
  expect(new URL(page.url()).searchParams.get("task")).toBe(opened)
  await expect(column(page, "Check the redirect map")).toBeVisible()
})

test("A click opens a match", async ({ page }) => {
  await seed(page)
  await line(page).fill("pricing")
  await matches(page)
    .getByRole("option", { name: /Rewrite the pricing copy/ })
    .click()
  await expect(column(page, "Rewrite the pricing copy")).toBeVisible()
  await expect(line(page)).toHaveValue("")
})

test("Escape closes the matches and keeps the text", async ({ page }) => {
  await seed(page)
  await line(page).fill("redirect")
  await expect(matches(page)).toBeVisible()

  await line(page).press("Escape")
  await expect(matches(page)).toHaveCount(0)
  await expect(line(page)).toHaveValue("redirect")
  await expect(line(page)).toBeFocused()
  await expect(line(page)).toHaveAttribute("aria-expanded", "false")

  // Typing on brings them back, for the new text.
  await line(page).pressSequentially("s")
  await expect(line(page)).toHaveValue("redirects")
  await page.waitForTimeout(400)
  await expect(matches(page)).toHaveCount(0)
  await line(page).press("Backspace")
  await expect(matches(page)).toBeVisible()
})

test("A fast typist makes few requests, and a late answer never replaces a newer one", async ({
  page,
}) => {
  await seed(page)

  const asked: string[] = []
  await page.route(/\/tasks\/\?.*title=/, async (route) => {
    const title = new URL(route.request().url()).searchParams.get("title")
    asked.push(title ?? "")
    // The answer to "re" is slow: it lands after the one to "red".
    if (title === "re") await new Promise((done) => setTimeout(done, 1200))
    await route.continue()
  })

  await line(page).click()
  await line(page).pressSequentially("re")
  // Past the pause, so "re" is asked; then on to "red" while it is awaited.
  await expect.poll(() => asked).toEqual(["re"])
  await line(page).pressSequentially("d")
  await expect(matches(page).getByRole("option")).toHaveCount(2)
  await expect(matches(page)).not.toContainText("Rewrite the pricing copy")

  // Once the slow answer has landed it is not shown.
  await page.waitForTimeout(1500)
  await expect(matches(page).getByRole("option")).toHaveCount(2)
  await expect(matches(page)).not.toContainText("Rewrite the pricing copy")
  expect(asked).toEqual(["re", "red"])

  // Typing quickly asks once, for where the typing stopped.
  asked.length = 0
  await line(page).fill("")
  await line(page).pressSequentially("redirect", { delay: 10 })
  await expect.poll(() => asked.at(-1)).toBe("redirect")
  await expect(matches(page).getByRole("option")).toHaveCount(2)
  // Eight keystrokes, at most two requests, never one per key.
  expect(asked.length).toBeLessThanOrEqual(2)
})

test("The day page offers the same matches", async ({ page }) => {
  await seed(page)
  await page.goto("/")
  await line(page).fill("pricing")
  await expect(matches(page).getByRole("option")).toHaveText([
    /Rewrite the pricing copy.*Website relaunch/,
  ])
})
