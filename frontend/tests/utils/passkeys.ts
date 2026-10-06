import { expect, type Page } from "@playwright/test"

/**
 * A Chromium virtual authenticator attached to the page: a platform
 * authenticator that holds discoverable passkeys and verifies its user, as a
 * phone or laptop with a fingerprint reader does (FR-12.5). Every prompt is
 * answered at once.
 */
export async function addVirtualAuthenticator(
  page: Page,
  /** Chrome allows one internal authenticator; a second device is a USB key. */
  transport: "internal" | "usb" = "internal",
) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send("WebAuthn.enable")
  const { authenticatorId } = await cdp.send(
    "WebAuthn.addVirtualAuthenticator",
    {
      options: {
        protocol: "ctap2",
        transport,
        hasResidentKey: true,
        hasUserVerification: true,
        isUserVerified: true,
        automaticPresenceSimulation: true,
      },
    },
  )
  return {
    /** The passkeys this authenticator holds. */
    credentials: async () =>
      (await cdp.send("WebAuthn.getCredentials", { authenticatorId }))
        .credentials,
    remove: () =>
      cdp.send("WebAuthn.removeVirtualAuthenticator", { authenticatorId }),
  }
}

/** Register an account through the sign-up screen, with a new passkey. */
export async function registerWithPasskey(page: Page, email: string) {
  await page.goto("/signup")
  await page.getByTestId("email-input").fill(email)
  await page.getByRole("button", { name: "Create account" }).click()
  await page.waitForURL("/")
  await expect(page.getByRole("combobox", { name: "Add a task" })).toBeVisible()
}

/**
 * Make the browser one that offers no passkeys in autofill. A virtual
 * authenticator answers the sign-in screen's autofill ceremony on its own,
 * signing in before anything is clicked; without autofill, the button is the
 * only way in.
 */
export async function withoutPasskeyAutofill(page: Page) {
  await page.addInitScript(() => {
    PublicKeyCredential.isConditionalMediationAvailable = async () => false
  })
}

/**
 * Sign in from the sign-in screen with the "Sign in with passkey" button and
 * whichever passkey the browser holds. Call `withoutPasskeyAutofill` first.
 */
export async function signInWithPasskey(page: Page) {
  await page.goto("/login")
  await page.getByRole("button", { name: "Sign in with passkey" }).click()
  await page.waitForURL("/")
  await expect(page.getByRole("combobox", { name: "Add a task" })).toBeVisible()
}

/** Make the page's browser one without WebAuthn at all (FR-12.12). */
export async function withoutPasskeySupport(page: Page) {
  await page.addInitScript(() => {
    delete (window as any).PublicKeyCredential
  })
}
