import { expect, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

const SIGNED_OUT = ["/login", "/signup", "/recover"]
const SIGNED_IN = [
  "/",
  "/tasks",
  "/projects",
  "/tags",
  "/bots",
  "/activity",
  "/settings",
]

test("Every browser title names the product, not the template", async ({
  page,
}) => {
  for (const path of SIGNED_OUT) {
    await page.goto(path)
    await expect(page).toHaveTitle(/Taskly/)
    await expect(page).not.toHaveTitle(/template|fastapi/i)
  }
  await newUser(page)
  for (const path of SIGNED_IN) {
    await page.goto(path)
    await expect(page).toHaveTitle(/Taskly/)
    await expect(page).not.toHaveTitle(/template|fastapi/i)
  }
})

test("A failure says what failed, not that something went wrong", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tags/", { name: "errands" })

  await page.goto("/tags")
  await page.getByRole("button", { name: "New tag" }).click()
  const name = page.getByRole("textbox", { name: "Tag name" })
  await name.fill("errands")
  await name.press("Enter")

  // The refusal is said under the name, in the API's words.
  const refusal = page.getByRole("complementary").getByRole("alert")
  await expect(refusal).toContainText("You already have a tag named “errands”.")
  await expect(refusal).not.toContainText("Something went wrong")
  await expect(refusal).not.toContainText("Success!")
})

test("A name that is not set reads as prose", async ({ page }) => {
  await newUser(page)
  const api = await userApi(page)
  expect((await api.patch("/users/me", { full_name: "" })).ok()).toBe(true)

  await page.goto("/settings")
  const unset = page.getByText("Not set", { exact: true })
  await expect(unset).toBeVisible()
  await expect(unset).toHaveCSS("font-style", "italic")
  await expect(page.getByText("N/A")).toHaveCount(0)
})

test("Deleting an account names its button and what goes with it", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/settings")
  await page.getByRole("button", { name: "Delete my account" }).click()

  const dialog = page.getByRole("dialog")
  const description = dialog.locator("[data-slot=dialog-description]")
  const confirm = dialog.getByRole("button", { name: /^Delete/ })
  const label = (await confirm.textContent())?.trim() ?? ""
  // The instruction names the very button it refers to.
  await expect(description).toContainText(`“${label}”`)
  for (const lost of ["tasks", "projects", "bot users", "tokens"]) {
    await expect(description).toContainText(lost)
  }
  await expect(description).toContainText("cannot be undone")
})

test("A date in the panel's date field is said in words", async ({ page }) => {
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", {
    title: "Renew the lease",
    // A year that is not this one, so the year is said too.
    due_date: "2019-09-01",
  })
  await api.create(`/tasks/${task.id}/comments/`, { body: "Signed" })

  // The panel shows the day the way the product writes one, whatever
  // language the browser's own date picker speaks.
  await page.goto(`/tasks?task=${task.id}`)
  const field = page
    .getByRole("complementary", { name: "Renew the lease" })
    .getByRole("button", { name: /^Due date:/ })
  const shown = ((await field.textContent()) ?? "").trim()
  expect(shown).toMatch(/2019/)
  expect(shown).toMatch(/Sep/)
  expect(shown).not.toContain("2019-09-01")
  expect(shown).not.toMatch(/\d{1,2}[./]\d{1,2}[./]\d{2,4}/)

  // Moments in the panel are written to the minute and no further: the
  // Created row with its day, the history's time column with the time alone.
  await page.goto(`/tasks?task=${task.id}`)
  const panel = page.getByRole("complementary", { name: "Renew the lease" })
  const created = await panel.locator("time").first().textContent()
  const commented = await panel
    .getByRole("listitem")
    .filter({ hasText: "Signed" })
    .locator("time")
    .textContent()
  expect(commented).toMatch(/^\d{1,2}:\d\d/)
  expect(created).not.toMatch(/\d:\d\d:\d\d/)
  expect(commented).not.toMatch(/\d:\d\d:\d\d/)
})

test("Heading levels descend without skipping on every screen", async ({
  page,
}) => {
  const outline = () =>
    page.evaluate(() =>
      Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6"))
        .filter((heading) => (heading as HTMLElement).offsetParent !== null)
        .map((heading) => Number(heading.tagName[1])),
    )
  const check = async (path: string) => {
    await page.goto(path)
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
    await page.waitForLoadState("networkidle")
    const levels = await outline()
    expect(levels[0], path).toBe(1)
    levels.forEach((level, index) => {
      if (index > 0) {
        expect(level, `${path}: ${levels.join(" ")}`).toBeLessThanOrEqual(
          levels[index - 1] + 1,
        )
      }
    })
  }

  for (const path of SIGNED_OUT) await check(path)
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tasks/", { title: "Overdue", due_date: "2026-01-01" })
  for (const path of SIGNED_IN) await check(path)
  // A panel's title is the h2 under whatever opened it.
  const task = (await (await api.get("/tasks/")).json()).data[0]
  await page.goto(`/tasks?task=${task.id}`)
  const panel = page.locator("[data-record-column]")
  await expect(panel).toBeVisible()
  const inPanel = await panel.evaluate((node) =>
    Array.from(node.querySelectorAll("h1, h2, h3, h4, h5, h6")).map((h) =>
      Number(h.tagName[1]),
    ),
  )
  expect(inPanel[0]).toBe(2)
  inPanel.forEach((level, index) => {
    if (index > 0) expect(level).toBeLessThanOrEqual(inPanel[index - 1] + 1)
  })

  // Settings is one document: the heading, then Profile, Passkeys, Sessions,
  // Paperless and Account (this account is not the superuser's, so no Users).
  await page.goto("/settings")
  await expect(page.getByRole("heading", { name: "Account" })).toBeVisible()
  expect(await outline()).toEqual([1, 2, 2, 2, 2, 2])
})
