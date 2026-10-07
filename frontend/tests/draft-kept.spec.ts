import { expect, type Page, test } from "@playwright/test"
import { newUser } from "./utils/account"
import { openDraft } from "./utils/capture"

test.use({ storageState: { cookies: [], origins: [] } })

const draftPanel = (page: Page) =>
  page.getByRole("complementary", { name: "New task" })
const titleField = (page: Page) =>
  page.getByRole("textbox", { name: "Task title" })

async function fillDraft(page: Page) {
  await openDraft(page)
  await expect(titleField(page)).toBeFocused()
  await titleField(page).fill("Renew the passport")
  const panel = draftPanel(page)
  await panel.getByRole("combobox", { name: "Priority" }).click()
  await page.getByRole("option", { name: "P2" }).click()
  await panel
    .getByRole("textbox", { name: "Task description" })
    .fill("Photos first")
}

test("A draft survives a reload, and Create clears it", async ({ page }) => {
  await newUser(page)
  await page.goto("/tasks")
  // Leaving with a draft open asks the browser to confirm; the reload is meant.
  page.on("dialog", (dialog) => void dialog.accept())
  const sent: string[] = []
  page.on("request", (request) => {
    if (request.method() !== "GET") sent.push(request.url())
  })

  await fillDraft(page)
  // Held by the browser alone: nothing was written anywhere.
  expect(sent).toEqual([])

  await page.goto("/tasks?capture=task")
  const panel = draftPanel(page)
  await expect(titleField(page)).toHaveValue("Renew the passport")
  await expect(panel.getByRole("combobox", { name: "Priority" })).toContainText(
    "P2",
  )
  await expect(
    panel.getByRole("textbox", { name: "Task description" }),
  ).toHaveValue("Photos first")

  await titleField(page).press("Enter")
  await expect(page.getByText("“Renew the passport” created")).toBeVisible()

  // Made: opening the draft again starts from nothing.
  await page.goto("/tasks?capture=task")
  await expect(titleField(page)).toHaveValue("")
  await expect(panel.getByRole("combobox", { name: "Priority" })).toContainText(
    "No priority",
  )
})

test("Discarding clears the kept draft, and keeping it does not", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks")
  await fillDraft(page)

  const confirm = page.getByRole("dialog", { name: "Discard this task?" })
  await page.keyboard.press("Escape")
  await expect(confirm).toBeVisible()
  await confirm.getByRole("button", { name: "Keep editing" }).click()
  await expect(titleField(page)).toHaveValue("Renew the passport")
  expect(
    await page.evaluate(() =>
      Object.keys(localStorage).filter((key) => key.includes("task-draft")),
    ),
  ).toHaveLength(1)

  await page.getByRole("button", { name: "Close" }).click()
  await confirm.getByRole("button", { name: "Discard" }).click()
  await expect(page.locator("[data-record-column]")).toHaveCount(0)
  expect(
    await page.evaluate(() =>
      Object.keys(localStorage).filter((key) => key.includes("task-draft")),
    ),
  ).toHaveLength(0)

  await page.goto("/tasks?capture=task")
  await expect(titleField(page)).toHaveValue("")
})

test("A draft still works where storage is refused", async ({ page }) => {
  await page.addInitScript(() => {
    const refuse = () => {
      throw new DOMException("denied", "SecurityError")
    }
    for (const method of ["getItem", "setItem", "removeItem"] as const) {
      const original = Storage.prototype[method]
      Storage.prototype[method] = function (this: Storage, ...args: [string]) {
        // The session itself still needs its token; only the draft is refused.
        if (String(args[0]).includes("task-draft")) return refuse()
        return (original as (...a: [string]) => unknown).apply(this, args)
      } as never
    }
  })
  await newUser(page)
  await page.goto("/tasks")
  await openDraft(page)
  await titleField(page).fill("Still here")
  await expect(titleField(page)).toHaveValue("Still here")
  await titleField(page).press("Enter")
  await expect(page.getByText("“Still here” created")).toBeVisible()
})
