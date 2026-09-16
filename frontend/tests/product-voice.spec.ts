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
