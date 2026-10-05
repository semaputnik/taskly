import { expect, type Page } from "@playwright/test"
import { createSession } from "./privateApi.ts"

/**
 * Sign in as `email` without the passkey ceremony, creating the user if there
 * is none. For tests about anything but signing in; `passkeys.ts` drives the
 * real ceremony through a virtual authenticator.
 */
export async function logInUser(page: Page, email: string) {
  const { access_token: token } = await createSession({ email })
  await page.goto("/login")
  await page.evaluate(
    (token) => localStorage.setItem("access_token", token),
    token,
  )
  await page.goto("/")
  await expect(
    page.getByText("What needs you now, and what changed without you"),
  ).toBeVisible()
}

export async function logOutUser(page: Page) {
  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log out" }).click()
  await page.goto("/login")
}
