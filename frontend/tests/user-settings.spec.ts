import { expect, test } from "@playwright/test"
import { firstSuperuser } from "./config.ts"
import {
  addVirtualAuthenticator,
  registerWithPasskey,
} from "./utils/passkeys.ts"
import { createUser } from "./utils/privateApi.ts"
import { randomEmail } from "./utils/random"
import { logInUser, logOutUser } from "./utils/user"

const main = (page: import("@playwright/test").Page) => page.getByRole("main")

test.describe("The document", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Settings is one page of sections in order, with no tabs", async ({
    page,
  }) => {
    await logInUser(page, randomEmail())
    await page.goto("/settings")

    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible()
    await expect(page.getByRole("tab")).toHaveCount(0)
    // Users is the superuser's: another account never sees it.
    await expect(main(page).getByRole("heading", { level: 2 })).toHaveText([
      /^Profile/,
      /^Passkeys/,
      /^Sessions/,
      /^Account/,
    ])
  })

  test("The superuser's Settings adds Users before Account", async ({
    page,
  }) => {
    await logInUser(page, firstSuperuser)
    await page.goto("/settings")

    await expect(main(page).getByRole("heading", { level: 2 })).toHaveText([
      /^Profile/,
      /^Passkeys/,
      /^Sessions/,
      /^Users/,
      /^Account/,
    ])
  })
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
  })

  test("Edit user name with a valid name", async ({ page }) => {
    const updatedName = "Test User 2"

    await page.getByRole("button", { name: "Change name" }).click()
    await page.getByLabel("Name", { exact: true }).fill(updatedName)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User updated successfully")).toBeVisible()
    await expect(
      main(page).getByText(updatedName, { exact: true }),
    ).toBeVisible()
    // Saved in place: the field is a value again.
    await expect(page.getByRole("button", { name: "Save" })).toHaveCount(0)
  })

  test("Edit user email with an invalid email shows error", async ({
    page,
  }) => {
    await page.getByRole("button", { name: "Change email" }).click()
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

    await page.getByRole("button", { name: "Change email" }).click()
    await page.getByLabel("Email").fill(updatedEmail)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User updated successfully")).toBeVisible()
    await expect(
      main(page).getByText(updatedEmail, { exact: true }),
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
    await page.getByRole("button", { name: "Change name" }).click()
    await page.getByLabel("Name", { exact: true }).fill("Test User")
    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(
      main(page).getByText(user.full_name as string, { exact: true }),
    ).toBeVisible()
  })

  test("Cancel edit action restores original email", async ({ page }) => {
    const email = randomEmail()
    await createUser({ email })

    await logInUser(page, email)
    await page.goto("/settings")
    await page.getByRole("button", { name: "Change email" }).click()
    await page.getByLabel("Email").fill(randomEmail())
    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(main(page).getByText(email, { exact: true })).toBeVisible()
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

    const rows = page.getByTestId("passkey-list").getByRole("listitem")
    await expect(rows).toHaveCount(1)
    await expect(rows.first()).toContainText("added")
    // Registering signed in with it.
    await expect(rows.first()).toContainText("last used")
    // The last passkey cannot be removed (FR-12.8), and the page says so.
    await expect(
      rows.first().getByRole("button", { name: /Remove/ }),
    ).toBeDisabled()
    await expect(page.getByText("The last one cannot be removed")).toBeVisible()
  })

  test("A passkey is renamed in place, with no passkey confirmation", async ({
    page,
  }) => {
    await addVirtualAuthenticator(page)
    await registerWithPasskey(page, randomEmail())
    await page.goto("/settings")

    const rows = page.getByTestId("passkey-list").getByRole("listitem")
    await rows
      .first()
      .getByRole("button", { name: /^Rename/ })
      .click()
    await page.getByLabel("Name of this passkey").fill("Work laptop")
    await page.getByRole("button", { name: "Save" }).click()

    await expect(rows.first()).toContainText("Work laptop")
    await expect(page.getByLabel("Name of this passkey")).toHaveCount(0)

    // And it is the stored name, not only the shown one.
    await page.reload()
    await expect(rows.first()).toContainText("Work laptop")
  })

  test("Adding a passkey puts a second line in the list, and the first can go", async ({
    page,
  }) => {
    await addVirtualAuthenticator(page)
    await registerWithPasskey(page, randomEmail())
    await page.goto("/settings")
    // The first holds the passkey the browser would refuse to make again:
    // a second device takes the new one.
    await addVirtualAuthenticator(page, "usb")

    const rows = page.getByTestId("passkey-list").getByRole("listitem")
    await page.getByRole("button", { name: "Add a passkey" }).click()
    await expect(rows).toHaveCount(2)
    await expect(page.getByText("Passkey added")).toBeVisible()

    await rows
      .first()
      .getByRole("button", { name: /^Remove/ })
      .click()
    await expect(rows).toHaveCount(1)
    await expect(page.getByText(/Passkey removed/)).toContainText(
      "Devices it signed in stay signed in",
    )
  })

  test("Sign out everywhere ends this session too", async ({ page }) => {
    await logInUser(page, randomEmail())
    const token = await page.evaluate(() =>
      localStorage.getItem("access_token"),
    )

    await page.goto("/settings")
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

test("Appearance is chosen in Settings and is no longer in the account menu", async ({
  page,
}) => {
  await page.goto("/settings")
  const group = page.getByRole("radiogroup", { name: "Appearance" })
  await expect(group.getByRole("radio")).toHaveText(["System", "Light", "Dark"])

  await page.getByTestId("user-menu").click()
  await expect(page.getByRole("menuitem", { name: "Log out" })).toBeVisible()
  await expect(page.getByRole("menuitemradio")).toHaveCount(0)
})

test("User can switch between theme modes", async ({ page }) => {
  await page.goto("/settings")

  await page.getByTestId("dark-mode").click()
  await expect(page.locator("html")).toHaveClass(/dark/)
  // The chosen one is told apart by weight and by its state.
  await expect(page.getByTestId("dark-mode")).toHaveAttribute(
    "aria-checked",
    "true",
  )
  await expect(page.getByTestId("dark-mode")).toHaveCSS("font-weight", "600")

  await page.getByTestId("light-mode").click()
  await expect(page.locator("html")).toHaveClass(/light/)
  await expect(page.getByTestId("dark-mode")).toHaveAttribute(
    "aria-checked",
    "false",
  )
})

test("Selected mode is preserved across sessions", async ({ page }) => {
  await page.goto("/settings")

  await page.getByTestId("light-mode").click()
  await expect(page.locator("html")).toHaveClass(/light/)

  await page.getByTestId("dark-mode").click()
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
  await page.getByRole("button", { name: "Delete my account" }).click()
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
