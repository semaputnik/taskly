import { expect, test } from "@playwright/test"
import { firstSuperuser } from "./config.ts"
import {
  addVirtualAuthenticator,
  registerWithPasskey,
} from "./utils/passkeys.ts"
import { createUser } from "./utils/privateApi.ts"
import { randomEmail } from "./utils/random"
import { logInUser, logOutUser } from "./utils/user"

const tabs = ["My profile", "Passkeys", "Danger zone"]

test("My profile tab is active by default", async ({ page }) => {
  await page.goto("/settings")
  await expect(page.getByRole("tab", { name: "My profile" })).toHaveAttribute(
    "aria-selected",
    "true",
  )
})

test("All tabs are visible", async ({ page }) => {
  await page.goto("/settings")
  for (const tab of tabs) {
    await expect(page.getByRole("tab", { name: tab })).toBeVisible()
  }
})

test.describe("Edit user profile", () => {
  test.use({ storageState: { cookies: [], origins: [] } })
  let email: string

  test.beforeAll(async () => {
    email = randomEmail()
    await createUser({ email })
  })

  test.beforeEach(async ({ page }) => {
    await logInUser(page, email)
    await page.goto("/settings")
    await page.getByRole("tab", { name: "My profile" }).click()
  })

  test("Edit user name with a valid name", async ({ page }) => {
    const updatedName = "Test User 2"

    await page.getByRole("button", { name: "Edit profile" }).click()
    await page.getByLabel("Full name").fill(updatedName)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User updated successfully")).toBeVisible()
    await expect(
      page.locator("form").getByText(updatedName, { exact: true }),
    ).toBeVisible()
  })

  test("Edit user email with an invalid email shows error", async ({
    page,
  }) => {
    await page.getByRole("button", { name: "Edit profile" }).click()
    await page.getByLabel("Email").fill("")
    // Validation runs on blur. Leave the field directly rather than clicking
    // the middle of the page for it: where that lands depends on the layout.
    await page.getByLabel("Email").blur()

    await expect(page.getByText("Invalid email address")).toBeVisible()
  })
})

test.describe("Edit user email", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Edit user email with a valid email", async ({ page }) => {
    const email = randomEmail()
    const updatedEmail = randomEmail()

    await createUser({ email })
    await logInUser(page, email)
    await page.goto("/settings")
    await page.getByRole("tab", { name: "My profile" }).click()

    await page.getByRole("button", { name: "Edit profile" }).click()
    await page.getByLabel("Email").fill(updatedEmail)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User updated successfully")).toBeVisible()
    await expect(
      page.locator("form").getByText(updatedEmail, { exact: true }),
    ).toBeVisible()
  })
})

test.describe("Cancel edit actions", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Cancel edit action restores original name", async ({ page }) => {
    const email = randomEmail()
    const user = await createUser({ email })

    await logInUser(page, email)
    await page.goto("/settings")
    await page.getByRole("tab", { name: "My profile" }).click()
    await page.getByRole("button", { name: "Edit profile" }).click()
    await page.getByLabel("Full name").fill("Test User")
    await page.getByRole("button", { name: "Cancel" }).first().click()

    await expect(
      page.locator("form").getByText(user.full_name as string, { exact: true }),
    ).toBeVisible()
  })

  test("Cancel edit action restores original email", async ({ page }) => {
    const email = randomEmail()
    await createUser({ email })

    await logInUser(page, email)
    await page.goto("/settings")
    await page.getByRole("tab", { name: "My profile" }).click()
    await page.getByRole("button", { name: "Edit profile" }).click()
    await page.getByLabel("Email").fill(randomEmail())
    await page.getByRole("button", { name: "Cancel" }).first().click()

    await expect(
      page.locator("form").getByText(email, { exact: true }),
    ).toBeVisible()
  })
})

test.describe("Passkeys", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Settings lists the account's passkeys, and the only one stays", async ({
    page,
  }) => {
    await addVirtualAuthenticator(page)
    await registerWithPasskey(page, randomEmail())

    await page.goto("/settings")
    await page.getByRole("tab", { name: "Passkeys" }).click()

    const rows = page.getByTestId("passkey-list").getByRole("listitem")
    await expect(rows).toHaveCount(1)
    await expect(rows.first()).toContainText("Created")
    // Registering signed in with it.
    await expect(rows.first()).toContainText("last used")
    // The last passkey cannot be removed (FR-12.8).
    await expect(
      rows.first().getByRole("button", { name: /Remove/ }),
    ).toBeDisabled()
  })

  test("Sign out everywhere ends this session too", async ({ page }) => {
    await logInUser(page, randomEmail())
    const token = await page.evaluate(() =>
      localStorage.getItem("access_token"),
    )

    await page.goto("/settings?tab=passkeys")
    await page.getByRole("button", { name: "Sign out everywhere" }).click()

    await page.waitForURL("/login")
    const r = await page.request.get(
      `${process.env.VITE_API_URL}/api/v1/users/me`,
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    )
    expect(r.status()).toBe(401)
  })
})

test("Appearance is offered in the account menu", async ({ page }) => {
  await page.goto("/settings")
  await page.getByTestId("user-menu").click()
  await expect(page.getByTestId("dark-mode")).toBeVisible()
})

test("User can switch between theme modes", async ({ page }) => {
  await page.goto("/settings")

  await page.getByTestId("user-menu").click()
  await page.getByTestId("dark-mode").click()
  await expect(page.locator("html")).toHaveClass(/dark/)

  await expect(page.getByTestId("dark-mode")).not.toBeVisible()

  await page.getByTestId("user-menu").click()
  await page.getByTestId("light-mode").click()
  await expect(page.locator("html")).toHaveClass(/light/)
})

test("Selected mode is preserved across sessions", async ({ page }) => {
  await page.goto("/settings")

  // Appearance is in the account menu, which closes on each choice: wait
  // for it to go before opening it again.
  const choose = async (mode: "light-mode" | "dark-mode") => {
    await page.getByTestId("user-menu").click()
    await page.getByTestId(mode).click()
    await expect(page.getByTestId(mode)).toBeHidden()
  }

  await choose("light-mode")
  await expect(page.locator("html")).toHaveClass(/light/)

  await choose("dark-mode")
  let isDarkMode = await page.evaluate(() =>
    document.documentElement.classList.contains("dark"),
  )
  expect(isDarkMode).toBe(true)

  await logOutUser(page)
  await logInUser(page, firstSuperuser)

  isDarkMode = await page.evaluate(() =>
    document.documentElement.classList.contains("dark"),
  )
  expect(isDarkMode).toBe(true)
})

test("A refused account deletion keeps the superuser signed in", async ({
  page,
}) => {
  await page.goto("/settings")
  await page.getByRole("tab", { name: "Danger zone" }).click()
  await page.getByRole("button", { name: "Delete Account" }).click()
  await page.getByRole("button", { name: "Delete my account" }).click()

  // A 403 refuses what was asked; it does not end the session.
  await expect(
    page.getByText("Super users are not allowed to delete themselves"),
  ).toBeVisible()
  await expect(page).toHaveURL(/\/settings/)
  await page.waitForTimeout(500)
  await expect(page).toHaveURL(/\/settings/)
  expect(
    await page.evaluate(() => localStorage.getItem("access_token")),
  ).not.toBeNull()
})
