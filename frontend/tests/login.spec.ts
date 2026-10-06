import { expect, test } from "@playwright/test"
import {
  addVirtualAuthenticator,
  registerWithPasskey,
  signInWithPasskey,
  withoutPasskeyAutofill,
  withoutPasskeySupport,
} from "./utils/passkeys.ts"
import { randomEmail } from "./utils/random.ts"
import { gotoAndBeSentAway, logInUser, logOutUser } from "./utils/user.ts"

test.use({ storageState: { cookies: [], origins: [] } })

test("The sign-in screen asks for nothing but a passkey", async ({ page }) => {
  await page.goto("/login")

  await expect(
    page.getByRole("button", { name: "Sign in with passkey" }),
  ).toBeVisible()
  // The email field is there for the browser's passkey suggestions only.
  await expect(page.getByTestId("email-input")).toHaveAttribute(
    "autocomplete",
    "username webauthn",
  )
  await expect(page.getByRole("link", { name: "Create account" })).toBeVisible()
  await expect(
    page.getByRole("link", { name: "Have a recovery code?" }),
  ).toBeVisible()
  await expect(page.getByLabel(/password/i)).toHaveCount(0)
})

test("Sign in with a passkey made when registering", async ({ page }) => {
  await withoutPasskeyAutofill(page)
  const authenticator = await addVirtualAuthenticator(page)
  const email = randomEmail()
  await registerWithPasskey(page, email)
  expect(await authenticator.credentials()).toHaveLength(1)
  await logOutUser(page)

  await signInWithPasskey(page)

  await page.goto("/settings")
  await expect(page.getByRole("main").getByText(email)).toBeVisible()
})

test("The email field's autofill offers the passkey and signs in", async ({
  page,
}) => {
  await addVirtualAuthenticator(page)
  const email = randomEmail()
  await registerWithPasskey(page, email)
  await logOutUser(page)

  // Nothing is clicked: the virtual authenticator answers the autofill
  // ceremony the sign-in screen starts on its own (FR-12.3).
  await page.goto("/login")
  await page.waitForURL("/")

  await page.goto("/settings")
  await expect(page.getByRole("main").getByText(email)).toBeVisible()
})

test("A passkey this installation does not know is refused", async ({
  page,
}) => {
  await withoutPasskeyAutofill(page)
  const authenticator = await addVirtualAuthenticator(page)
  await registerWithPasskey(page, randomEmail())
  await logOutUser(page)
  await authenticator.remove()
  // A passkey on the device that was never registered here.
  const stranger = await addVirtualAuthenticator(page)
  await page.goto("/signup")
  await page.evaluate(async () => {
    const credential = await navigator.credentials.create({
      publicKey: {
        rp: { id: location.hostname, name: "Elsewhere" },
        user: {
          id: new Uint8Array([1, 2, 3]),
          name: "someone",
          displayName: "someone",
        },
        challenge: new Uint8Array(32),
        pubKeyCredParams: [{ type: "public-key", alg: -7 }],
        authenticatorSelection: { residentKey: "required" },
      },
    })
    return credential?.id
  })
  expect(await stranger.credentials()).toHaveLength(1)

  await page.goto("/login")
  await page.getByRole("button", { name: "Sign in with passkey" }).click()

  await expect(
    page.getByText("This passkey could not sign you in. Try again."),
  ).toBeVisible()
  await expect(page).toHaveURL(/\/login/)
})

test("A browser without passkeys is told there is no way in", async ({
  page,
}) => {
  await withoutPasskeySupport(page)
  await page.goto("/login")

  await expect(page.getByTestId("passkeys-unsupported")).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Sign in with passkey" }),
  ).toHaveCount(0)
})

test("Successful log out", async ({ page }) => {
  await logInUser(page, randomEmail())

  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log out" }).click()
  await page.waitForURL("/login")
})

test("Logged-out user cannot access protected routes", async ({ page }) => {
  await logInUser(page, randomEmail())

  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log out" }).click()
  await page.waitForURL("/login")

  await page.goto("/settings")
  await page.waitForURL("/login")
})

test("Redirects to /login when token is wrong", async ({ page }) => {
  await page.goto("/settings")
  await page.evaluate(() => {
    localStorage.setItem("access_token", "invalid_token")
  })
  await gotoAndBeSentAway(page, "/settings")
  await page.waitForURL("/login")
  await expect(page).toHaveURL("/login")
})

test("A refused credential sends the reader on at once, not after retries", async ({
  page,
}) => {
  await page.goto("/login")
  await page.evaluate(() => {
    localStorage.setItem("access_token", "stale_token")
  })

  const started = Date.now()
  await gotoAndBeSentAway(page, "/tasks")
  await page.waitForURL("/login", { timeout: 5000 })
  // Retried like any other failure, a refused credential costs four refusals
  // and about eight seconds of a screen that neither loads nor moves on.
  expect(Date.now() - started).toBeLessThan(5000)
  await expect(
    page.evaluate(() => localStorage.getItem("access_token")),
  ).resolves.toBeNull()
})
