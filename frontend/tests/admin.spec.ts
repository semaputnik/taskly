import { expect, test } from "@playwright/test"
import { firstSuperuser, firstSuperuserPassword } from "./config.ts"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test("Admin page lists registered users", async ({ page }) => {
  const email = randomEmail()
  await createUser({ email, password: randomPassword() })

  await page.goto("/admin")
  await expect(page.getByRole("heading", { name: "Users" })).toBeVisible()

  const userRow = page.getByRole("row").filter({ hasText: email })
  await expect(userRow).toBeVisible()
  // Newest accounts come first, so this one is on the first page however many
  // other test runs have registered before it.
  await expect(userRow.getByText("User", { exact: true })).toBeVisible()
})

test("Admin page offers no way to change anyone's account", async ({
  page,
}) => {
  const email = randomEmail()
  await createUser({ email, password: randomPassword() })

  await page.goto("/admin")
  const userRow = page.getByRole("row").filter({ hasText: email })
  await expect(userRow).toBeVisible()

  // Listing accounts is all a superuser can do with them (FR-09.3).
  await expect(page.getByRole("button", { name: "Add User" })).toHaveCount(0)
  await expect(userRow.getByRole("button")).toHaveCount(0)
})

test.describe("Admin page access control", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Non-superuser cannot access admin page", async ({ page }) => {
    const email = randomEmail()
    const password = randomPassword()

    await createUser({ email, password })
    await logInUser(page, email, password)

    await page.goto("/admin")

    await expect(page.getByRole("heading", { name: "Users" })).not.toBeVisible()
    await expect(page).not.toHaveURL(/\/admin/)
  })

  test("Superuser can access admin page", async ({ page }) => {
    await logInUser(page, firstSuperuser, firstSuperuserPassword)

    await page.goto("/admin")

    await expect(page.getByRole("heading", { name: "Users" })).toBeVisible()
  })
})
