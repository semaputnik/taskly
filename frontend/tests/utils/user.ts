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
  await expect(page.getByRole("textbox", { name: "Add a task" })).toBeVisible()
}

export async function logOutUser(page: Page) {
  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log out" }).click()
  await page.goto("/login")
}

/**
 * Open a page that the app is about to send the reader away from. A refused
 * credential is answered with a full-page redirect to the sign-in screen
 * (`main.tsx`), and when it lands before the page has loaded it aborts the
 * navigation that opened it: that is the app working, so the abort is not an
 * error here. What the test is about is where the reader ends up, which the
 * caller asserts.
 */
export async function gotoAndBeSentAway(page: Page, url: string) {
  await page.goto(url, { waitUntil: "commit" }).catch((error: unknown) => {
    if (!String(error).includes("ERR_ABORTED")) throw error
  })
}
