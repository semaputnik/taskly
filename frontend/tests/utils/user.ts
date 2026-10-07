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
  // The way to add a task is the line on a wide screen and the bar's add
  // control on a phone (FR-06.15); either says the app has loaded.
  await expect(
    page
      .getByRole("combobox", { name: "Add a task" })
      .or(page.getByRole("button", { name: "Add a task" })),
  ).toBeVisible()
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

/**
 * Have the browser hold `token` in storage from the first page this tab opens,
 * for a test about what the app does with a credential the API refuses.
 *
 * Storing it from the test, with `page.evaluate` on a page that is already
 * running, is a race: that page is the app, and the next render of the
 * sign-in screen reads the token and asks the API who it belongs to. The
 * refusal then sends the reader away from the page the test is about to
 * leave, which aborts the test's own navigation and leaves the test waiting
 * for a URL it is already at. Seeded before any page exists, only the
 * navigation under test ever meets the token. The seed runs once per tab, so
 * the sign-in screen the reader is sent to is not given it back.
 */
export async function holdRefusedCredential(page: Page, token: string) {
  await page.addInitScript((token) => {
    if (sessionStorage.getItem("credential-held")) return
    sessionStorage.setItem("credential-held", "1")
    localStorage.setItem("access_token", token)
  }, token)
}
