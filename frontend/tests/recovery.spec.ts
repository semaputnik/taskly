import { expect, type Page, test } from "@playwright/test"
import {
  addVirtualAuthenticator,
  withoutPasskeySupport,
} from "./utils/passkeys.ts"
import { createUser, recoveryCodeFor } from "./utils/privateApi.ts"
import { randomEmail } from "./utils/random"

test.use({ storageState: { cookies: [], origins: [] } })

async function recover(page: Page, email: string, code: string) {
  await page.goto("/login")
  await page.getByRole("link", { name: "Use a recovery code" }).click()
  // The sign-in screen has an email field too: fill the one on recovery.
  await expect(
    page.getByRole("heading", { name: "Recover your account" }),
  ).toBeVisible()
  await page.getByTestId("email-input").fill(email)
  await page.getByTestId("recovery-code-input").fill(code)
  await page.getByRole("button", { name: "Create a new passkey" }).click()
}

test("A recovery code makes a new passkey and lands on the passkey list", async ({
  page,
}) => {
  const authenticator = await addVirtualAuthenticator(page)
  const email = randomEmail()
  await createUser({ email })

  await recover(page, email, await recoveryCodeFor(email))

  await page.waitForURL(/\/settings/)
  await expect(page.getByTestId("recovered-notice")).toContainText(
    "Remove any passkey you don't recognise",
  )
  await expect(
    page.getByTestId("passkey-list").getByRole("listitem"),
  ).toHaveCount(1)
  expect(await authenticator.credentials()).toHaveLength(1)
})

test("A wrong code is refused", async ({ page }) => {
  await addVirtualAuthenticator(page)
  const email = randomEmail()
  await createUser({ email })
  await recoveryCodeFor(email)

  await recover(page, email, "AAAA-AAAA-AAAA-AAAA")

  // Said beside the code that was refused, not in a notice that fades.
  await expect(page.getByRole("alert")).toHaveText(
    "This email and recovery code do not match a live code.",
  )
  await expect(page).toHaveURL(/\/recover/)
})

test("The recovery screen sets the code in mono and offers the way back", async ({
  page,
}) => {
  await page.goto("/recover")

  await expect(page.getByRole("textbox", { name: "Code" })).toHaveCSS(
    "font-family",
    /mono/i,
  )
  await expect(page.getByRole("textbox", { name: "Email" })).toBeVisible()
  await page.getByRole("link", { name: "Back to sign in" }).click()
  await expect(page).toHaveURL(/\/login/)
})

test("A browser without passkeys cannot recover", async ({ page }) => {
  await withoutPasskeySupport(page)
  await page.goto("/recover")

  await expect(page.getByTestId("passkeys-unsupported")).toBeVisible()
  await expect(page.getByTestId("recovery-code-input")).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: "Create a new passkey" }),
  ).toHaveCount(0)
})

test("The superuser issues a code that gets a user back in", async ({
  browser,
}) => {
  // A superuser with a passkey of their own, to confirm with.
  const admin = await browser.newPage()
  await addVirtualAuthenticator(admin)
  const adminEmail = randomEmail()
  await createUser({ email: adminEmail, isSuperuser: true })
  await recover(admin, adminEmail, await recoveryCodeFor(adminEmail))
  await admin.waitForURL(/\/settings/)

  const email = randomEmail()
  await createUser({ email })
  await admin.goto("/settings")
  const line = admin
    .getByRole("region", { name: "Users" })
    .getByRole("listitem")
    .filter({ hasText: email })
  await line.getByRole("button", { name: /Issue a recovery code/ }).click()
  const code = await admin
    .getByRole("textbox", { name: "Recovery code" })
    .inputValue()
  expect(code).toMatch(/^[0-9A-Z]{4}(-[0-9A-Z]{4}){3}$/)
  // Shown once, as a token is: it closes on being said to be stored, and
  // asks again when it was never copied.
  await admin.getByLabel("I have stored this code somewhere safe").check()
  await admin.getByRole("button", { name: "Done" }).click()
  await admin.getByRole("button", { name: "Close without copying" }).click()
  await expect(admin.getByRole("dialog")).toHaveCount(0)
  // The line now offers another, which replaces this one.
  await expect(line.getByRole("button")).toContainText("Issue another")

  // The user, on their own device.
  const user = await browser.newPage()
  await addVirtualAuthenticator(user)
  await recover(user, email, code)
  await user.waitForURL(/\/settings/)
  await expect(user.getByTestId("recovered-notice")).toBeVisible()
})
