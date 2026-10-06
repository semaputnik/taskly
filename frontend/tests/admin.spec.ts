import { expect, test } from "@playwright/test"
import { firstSuperuser } from "./config.ts"
import { addVirtualAuthenticator } from "./utils/passkeys.ts"
import { createUser } from "./utils/privateApi"
import { randomEmail } from "./utils/random"
import { logInUser } from "./utils/user"

const usersOf = (page: import("@playwright/test").Page) =>
  page.getByRole("region", { name: "Users" })

test("Users is a section of the superuser's Settings and lists every account", async ({
  page,
}) => {
  const email = randomEmail()
  await createUser({ email })

  await page.goto("/settings")
  const users = usersOf(page)
  await expect(users).toBeVisible()

  // Newest accounts come first, so this one is on the first page however many
  // other test runs have registered before it.
  const line = users.getByRole("listitem").filter({ hasText: email })
  await expect(line).toBeVisible()
  // This account has no passkey yet, and the line says so.
  await expect(line.getByText("no passkeys")).toBeVisible()
  await expect(line.getByText("never signed in")).toBeVisible()
})

test.describe("The superuser's own line", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("says a code cannot be issued for it (FR-12.19)", async ({ page }) => {
    // A superuser made now is newest, so it is on the first page however many
    // accounts the shared database holds.
    const email = randomEmail()
    await createUser({ email, isSuperuser: true })
    await logInUser(page, email)

    await page.goto("/settings")
    const own = usersOf(page).getByRole("listitem").filter({ hasText: email })
    await expect(own).toContainText("superuser · you")
    await expect(own).toContainText("not for your own account")
    await expect(own.getByRole("button")).toHaveCount(0)
  })
})

test("Users offers no way to change anyone's account but recovery", async ({
  page,
}) => {
  const email = randomEmail()
  await createUser({ email })

  await page.goto("/settings")
  const line = usersOf(page).getByRole("listitem").filter({ hasText: email })
  await expect(line).toBeVisible()

  // Listing accounts and issuing a recovery code are all a superuser can do
  // with them (FR-09.3, FR-12.16).
  await expect(page.getByRole("button", { name: "Add User" })).toHaveCount(0)
  await expect(line.getByRole("button")).toHaveText([
    `Issue a recovery code for ${email}`,
  ])
})

test("The superuser's Settings reaches Users by its address", async ({
  page,
}) => {
  await page.goto("/settings#users")
  await expect(usersOf(page)).toBeInViewport()
})

test.describe("Users access control", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Another account's Settings has no Users", async ({ page }) => {
    await logInUser(page, randomEmail())

    await page.goto("/settings")

    await expect(page.getByRole("heading", { name: "Account" })).toBeVisible()
    await expect(page.getByRole("heading", { name: /^Users/ })).toHaveCount(0)
  })

  test("The old Admin address lands on Settings, for the superuser and for anyone", async ({
    page,
  }) => {
    await logInUser(page, firstSuperuser)
    await page.goto("/admin")
    await expect(page).toHaveURL(/\/settings#users$/)
    await expect(usersOf(page)).toBeVisible()
  })

  test("A non-superuser sent to /admin ends on Settings without Users", async ({
    page,
  }) => {
    await logInUser(page, randomEmail())

    await page.goto("/admin")

    await expect(page).toHaveURL(/\/settings/)
    await expect(page.getByRole("heading", { name: /^Users/ })).toHaveCount(0)
  })

  test("A line says how many passkeys an account holds", async ({
    page,
    browser,
  }) => {
    // An account with a passkey of its own, made by registering.
    const holder = await browser.newPage()
    await addVirtualAuthenticator(holder)
    const email = randomEmail()
    const { registerWithPasskey } = await import("./utils/passkeys.ts")
    await registerWithPasskey(holder, email)

    await logInUser(page, firstSuperuser)
    await page.goto("/settings")
    const line = usersOf(page).getByRole("listitem").filter({ hasText: email })
    await expect(line).toContainText("1 passkey")
    await expect(line).toContainText("last signed in")
    await holder.close()
  })
})
