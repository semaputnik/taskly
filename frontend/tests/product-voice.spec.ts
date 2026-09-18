import { expect, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

const SIGNED_OUT = ["/login", "/signup", "/recover-password", "/reset-password"]
const SIGNED_IN = [
  "/",
  "/tasks",
  "/projects",
  "/tags",
  "/archive",
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
  await page.getByRole("button", { name: "Add Tag" }).click()
  const name = page.getByRole("textbox", { name: "Tag name" })
  await name.fill("errands")
  await name.press("Enter")

  const toast = page.locator("[data-sonner-toast]").first()
  await expect(toast).toContainText("You already have a tag named “errands”.")
  await expect(toast).not.toContainText("Something went wrong")
  await expect(toast).not.toContainText("Success!")
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
  await page.getByRole("tab", { name: "Danger zone" }).click()
  await page.getByRole("button", { name: "Delete Account" }).click()

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

test("A date reads the same in the table and in the panel's date field", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", {
    title: "Renew the lease",
    due_date: "2026-09-01",
  })
  await api.create(`/tasks/${task.id}/comments/`, { body: "Signed" })

  // The panel shows the day the same way the table does, whatever language
  // the browser's own date picker speaks.
  await page.goto(`/tasks?view=table&task=${task.id}`)
  const field = page
    .getByRole("dialog", { name: "Renew the lease" })
    .getByRole("button", { name: /^Due date:/ })
  const shown = ((await field.textContent()) ?? "").trim()
  expect(shown).toMatch(/2026/)
  await page.keyboard.press("Escape")
  const row = page.getByRole("row", { name: /Renew the lease/ })
  await expect(row).toContainText(shown)
  await expect(row).not.toContainText("2026-09-01")

  // Moments in the panel share one format, to the minute and no further.
  await page.goto(`/tasks?view=table&task=${task.id}`)
  const panel = page.getByRole("dialog", { name: "Renew the lease" })
  const created = await panel.locator("time").first().textContent()
  const commented = await panel
    .locator("div.rounded-md")
    .filter({ hasText: "Signed" })
    .locator("span.text-xs")
    .textContent()
  const shape = (text: string | null) =>
    (text ?? "").replace(/\d/g, "0").replace(/\b(AM|PM)\b/, "XM")
  expect(shape(created)).toBe(shape(commented))
  expect(created).not.toMatch(/\d:\d\d:\d\d/)
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
  await page.goto(`/tasks?view=table&task=${task.id}`)
  const panel = page.getByRole("dialog")
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

  await page.goto("/settings")
  for (const tab of ["Password", "Danger zone"]) {
    await page.getByRole("tab", { name: tab }).click()
    const levels = await outline()
    expect(levels, tab).toEqual([1, 2])
  }
})
