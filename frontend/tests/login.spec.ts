import { expect, test } from "@playwright/test"
import { pageGround, textOn, textOnFill } from "./utils/colour.ts"
import {
  addVirtualAuthenticator,
  registerWithPasskey,
  signInWithPasskey,
  withoutPasskeyAutofill,
  withoutPasskeySupport,
} from "./utils/passkeys.ts"
import { randomEmail } from "./utils/random.ts"
import {
  gotoAndBeSentAway,
  holdRefusedCredential,
  logInUser,
  logOutUser,
} from "./utils/user.ts"

test.use({ storageState: { cookies: [], origins: [] } })

test("The sign-in screen offers the passkey in an email field and by a button", async ({
  page,
}) => {
  await page.goto("/login")

  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Sign in with a passkey" }),
  ).toBeVisible()
  // One frameless email field above the button: it is where the browser's
  // passkey suggestions are offered (FR-12.3), and it is reachable.
  const email = page.getByLabel("Email")
  await expect(email).toBeVisible()
  await expect(email).toHaveAttribute("autocomplete", "username webauthn")
  await expect(email).toHaveCSS("border-top-width", "0px")
  await email.focus()
  await expect(email).toBeFocused()
  await expect(
    page.getByRole("link", { name: "Use a recovery code" }),
  ).toBeVisible()
  await expect(
    page.getByRole("link", { name: "Create an account" }),
  ).toBeVisible()
  await expect(page.getByLabel(/password/i)).toHaveCount(0)
})

test("The sign-in screen is one card-less column with its host at the foot", async ({
  page,
}) => {
  await page.goto("/login")

  // No split layout, no logo mark: the wordmark, the heading and the action
  // in a column no wider than 420px, centred.
  const main = page.getByRole("main")
  const box = await main.boundingBox()
  const viewport = page.viewportSize()
  expect(box?.width).toBeLessThanOrEqual(420)
  const centre = (box?.x ?? 0) + (box?.width ?? 0) / 2
  expect(Math.abs(centre - (viewport?.width ?? 0) / 2)).toBeLessThan(2)
  await expect(main.getByText("Taskly", { exact: true })).toBeVisible()
  await expect(main.locator("img")).toHaveCount(0)
  // The page's own host, since every passkey is bound to it.
  await expect(
    main.getByText(`Self-hosted at ${new URL(page.url()).host}`),
  ).toBeVisible()
})

test("The appearance chosen on the sign-in screen carries into the app", async ({
  page,
}) => {
  await page.goto("/login")
  const group = page.getByRole("radiogroup", { name: "Appearance" })

  await group.getByRole("radio", { name: "Light" }).click()
  await expect(page.locator("html")).toHaveClass(/light/)
  await expect(group.getByRole("radio", { name: "Light" })).toHaveCSS(
    "font-weight",
    "600",
  )
  await expect(group.getByRole("radio", { name: "Dark" })).toHaveAttribute(
    "aria-checked",
    "false",
  )

  // It is the theme provider's own storage, the one Settings writes.
  await addVirtualAuthenticator(page)
  await registerWithPasskey(page, randomEmail())
  await page.goto("/settings")
  await expect(page.locator("html")).toHaveClass(/light/)
  await expect(
    page
      .getByRole("radiogroup", { name: "Appearance" })
      .getByRole("radio", { name: "Light" }),
  ).toHaveAttribute("aria-checked", "true")
})

test("The sign-in screen is keyboard complete and readable", async ({
  page,
}) => {
  await withoutPasskeyAutofill(page)
  await page.goto("/login")
  await expect(
    page.getByRole("button", { name: "Sign in with a passkey" }),
  ).toBeVisible()

  // The email field, the action, the two links, then the appearance choice.
  await page.keyboard.press("Tab")
  await expect(page.getByLabel("Email")).toBeFocused()
  await page.keyboard.press("Tab")
  await expect(
    page.getByRole("button", { name: "Sign in with a passkey" }),
  ).toBeFocused()
  await page.keyboard.press("Tab")
  await expect(
    page.getByRole("link", { name: "Use a recovery code" }),
  ).toBeFocused()
  await page.keyboard.press("Tab")
  await expect(
    page.getByRole("link", { name: "Create an account" }),
  ).toBeFocused()
  await page.keyboard.press("Tab")
  // The three are one stop; the arrow keys walk them.
  await expect(page.getByRole("radio", { checked: true })).toBeFocused()

  const ground = await pageGround(page)
  for (const quiet of [
    page.getByText("Your browser will offer the passkeys"),
    page.getByText(/^Self-hosted at/),
  ]) {
    expect(await textOn(quiet, ground)).toBeGreaterThanOrEqual(4.5)
  }
  expect(
    await textOnFill(
      page.getByRole("button", { name: "Sign in with a passkey" }),
    ),
  ).toBeGreaterThanOrEqual(4.5)
})

test("The sign-in screen fits a phone", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 })
  await page.goto("/login")

  await expect(
    page.getByRole("button", { name: "Sign in with a passkey" }),
  ).toBeVisible()
  await expect(page.getByText(/^Self-hosted at/)).toBeVisible()
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(0)
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
  await page.getByRole("button", { name: "Sign in with a passkey" }).click()

  // Said under the button as an alert, not in a notice that fades.
  await expect(page.getByRole("alert")).toHaveText(
    "This passkey could not sign you in. Try again.",
  )
  const button = page.getByRole("button", { name: "Sign in with a passkey" })
  const alertBox = await page.getByRole("alert").boundingBox()
  const buttonBox = await button.boundingBox()
  expect(alertBox?.y).toBeGreaterThan(
    (buttonBox?.y ?? Infinity) + (buttonBox?.height ?? 0) - 1,
  )
  await expect(page.locator("[data-sonner-toast]")).toHaveCount(0)
  await expect(page).toHaveURL(/\/login/)
})

test("A browser without passkeys is told there is no way in", async ({
  page,
}) => {
  await withoutPasskeySupport(page)
  await page.goto("/login")

  await expect(page.getByTestId("passkeys-unsupported")).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Sign in with a passkey" }),
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
  await holdRefusedCredential(page, "invalid_token")
  await gotoAndBeSentAway(page, "/settings")
  await page.waitForURL("/login")
  await expect(page).toHaveURL("/login")
})

test("A refused credential sends the reader on at once, not after retries", async ({
  page,
}) => {
  await holdRefusedCredential(page, "stale_token")

  const started = Date.now()
  await gotoAndBeSentAway(page, "/tasks")
  await page.waitForURL("/login", { timeout: 5000 })
  // Retried like any other failure, a refused credential costs four refusals
  // and about eight seconds of a screen that neither loads nor moves on.
  expect(Date.now() - started).toBeLessThan(5000)
  // The sign-in screen is up; the credential went with the redirect.
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible()
  await expect(
    page.evaluate(() => localStorage.getItem("access_token")),
  ).resolves.toBeNull()
})
