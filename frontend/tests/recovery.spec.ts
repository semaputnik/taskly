import { expect, type Page, test } from "@playwright/test"
import { addVirtualAuthenticator } from "./utils/passkeys.ts"
import { createUser, recoveryCodeFor } from "./utils/privateApi.ts"
import { randomEmail } from "./utils/random"

test.use({ storageState: { cookies: [], origins: [] } })

async function recover(page: Page, email: string, code: string) {
  await page.goto("/login")
  await page.getByRole("link", { name: "Have a recovery code?" }).click()
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

  await expect(
    page.getByText("This email and recovery code do not match a live code."),
  ).toBeVisible()
  await expect(page).toHaveURL(/\/recover/)
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
  await admin.goto("/admin")
  const row = admin.getByRole("row").filter({ hasText: email })
  await row.getByRole("button", { name: "Issue recovery code" }).click()
  const code = await admin
    .getByRole("textbox", { name: "Recovery code" })
    .inputValue()
  expect(code).toMatch(/^[0-9A-Z]{4}(-[0-9A-Z]{4}){3}$/)
  await admin.getByRole("button", { name: "Done" }).click()

  // The user, on their own device.
  const user = await browser.newPage()
  await addVirtualAuthenticator(user)
  await recover(user, email, code)
  await user.waitForURL(/\/settings/)
  await expect(user.getByTestId("recovered-notice")).toBeVisible()
})
