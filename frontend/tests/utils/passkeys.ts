import { expect, type Page } from "@playwright/test"

/**
 * A Chromium virtual authenticator attached to the page: a platform
 * authenticator that holds discoverable passkeys and verifies its user, as a
 * phone or laptop with a fingerprint reader does (FR-12.5). Every prompt is
 * answered at once.
 */
export async function addVirtualAuthenticator(page: Page) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send("WebAuthn.enable")
  const { authenticatorId } = await cdp.send(
    "WebAuthn.addVirtualAuthenticator",
    {
      options: {
        protocol: "ctap2",
        transport: "internal",
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
  await expect(
    page.getByText("What needs you now, and what changed without you"),
  ).toBeVisible()
}

/** Sign in from the sign-in screen with whichever passkey the browser holds. */
export async function signInWithPasskey(page: Page) {
  await page.goto("/login")
  await page.getByRole("button", { name: "Sign in with passkey" }).click()
  await page.waitForURL("/")
  await expect(
    page.getByText("What needs you now, and what changed without you"),
  ).toBeVisible()
}

/** Make the page's browser one without WebAuthn at all (FR-12.12). */
export async function withoutPasskeySupport(page: Page) {
  await page.addInitScript(() => {
    delete (window as any).PublicKeyCredential
  })
}
