import { expect, test } from "@playwright/test"
import {
  addVirtualAuthenticator,
  registerWithPasskey,
  withoutPasskeySupport,
} from "./utils/passkeys.ts"
import { createUser } from "./utils/privateApi.ts"
import { randomEmail } from "./utils/random"

test.use({ storageState: { cookies: [], origins: [] } })

test("Registering asks for an email and an optional name", async ({ page }) => {
  await page.goto("/signup")

  await expect(
    page.getByRole("heading", { name: "Create an account" }),
  ).toBeVisible()
  await expect(page.getByTestId("email-input")).toBeEditable()
  await expect(page.getByRole("textbox", { name: "Name" })).toBeEditable()
  await expect(
    page.getByRole("button", { name: "Create a passkey and sign in" }),
  ).toBeVisible()
  await expect(page.getByLabel(/password/i)).toHaveCount(0)
  await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible()
})

test("A name given when registering is the account's name", async ({
  page,
}) => {
  await addVirtualAuthenticator(page)
  const email = randomEmail()

  await page.goto("/signup")
  await page.getByTestId("email-input").fill(email)
  await page.getByRole("textbox", { name: "Name" }).fill("Mara Quill")
  await page
    .getByRole("button", { name: "Create a passkey and sign in" })
    .click()
  await page.waitForURL("/")

  await page.goto("/settings")
  await expect(page.getByRole("main").getByText("Mara Quill")).toBeVisible()
})

test("A name left empty leaves the account unnamed", async ({ page }) => {
  await addVirtualAuthenticator(page)
  await registerWithPasskey(page, randomEmail())

  await page.goto("/settings")
  await expect(page.getByRole("main").getByText("Not set")).toBeVisible()
})

test("Registering makes a passkey and signs in", async ({ page }) => {
  const authenticator = await addVirtualAuthenticator(page)

  await registerWithPasskey(page, randomEmail())

  const [passkey] = await authenticator.credentials()
  // Discoverable, so signing in can ask for nothing (FR-12.3).
  expect(passkey.isResidentCredential).toBe(true)
  await page.goto("/settings")
  await expect(
    page.getByTestId("passkey-list").getByRole("listitem"),
  ).toHaveCount(1)
})

test("Registering a taken email is refused", async ({ page }) => {
  await addVirtualAuthenticator(page)
  const email = randomEmail()
  await createUser({ email })

  await page.goto("/signup")
  await page.getByTestId("email-input").fill(email)
  await page
    .getByRole("button", { name: "Create a passkey and sign in" })
    .click()

  await expect(
    page.getByText("An account with this email already exists."),
  ).toBeVisible()
  await expect(page).toHaveURL(/\/signup/)
})

test("Registering with an invalid email", async ({ page }) => {
  await page.goto("/signup")
  await page.getByTestId("email-input").fill("invalid-email")
  await page
    .getByRole("button", { name: "Create a passkey and sign in" })
    .click()

  await expect(page.getByText("Invalid email address")).toBeVisible()
})

test("A browser without passkeys cannot register", async ({ page }) => {
  await withoutPasskeySupport(page)
  await page.goto("/signup")

  await expect(page.getByTestId("passkeys-unsupported")).toBeVisible()
  await expect(page.getByTestId("email-input")).toHaveCount(0)
})
