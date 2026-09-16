import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"
import { storeTokenAndClose } from "./utils/tokenDialog"

test.use({ storageState: { cookies: [], origins: [] } })

/** A fresh token for a bot user of the test's own, on screen once. */
async function revealToken(page: Page) {
  await newUser(page)
  const api = await userApi(page)
  const bot = await api.create("/bot-users/", {
    name: "Nightly sync",
    scope: { project_ids: [], permissions: {} },
  })
  await page.goto(`/bots?bot=${bot.id}`)
  const panel = page.getByRole("dialog", { name: "Nightly sync", exact: true })
  await panel.getByRole("button", { name: "Issue token" }).click()
  await page
    .getByRole("dialog", { name: /Issue token for Nightly sync/ })
    .getByRole("button", { name: "Issue" })
    .click()
  const dialog = page.getByRole("dialog", { name: "Token for Nightly sync" })
  await expect(dialog).toBeVisible()
  const token = await dialog
    .getByRole("textbox", { name: "Bot token" })
    .inputValue()
  return { dialog, token }
}

test("The token dialog holds against Escape and a click outside", async ({
  page,
}) => {
  const { dialog, token } = await revealToken(page)

  await page.keyboard.press("Escape")
  await expect(dialog).toBeVisible()
  await page.mouse.click(5, 5)
  await expect(dialog).toBeVisible()
  // And there is no corner control to dismiss it with either.
  await expect(dialog.getByRole("button", { name: "Close" })).toHaveCount(0)
  await expect(dialog).toContainText("stays open until")
  await expect(dialog.getByRole("textbox", { name: "Bot token" })).toHaveValue(
    token,
  )
})

test("Leaving needs the token stored, and warns when it was never copied", async ({
  page,
}) => {
  const { dialog } = await revealToken(page)

  // What it already said stays: once only, and when it expires.
  await expect(dialog).toContainText("It won't be shown again")
  await expect(dialog).toContainText("It works until you revoke it.")

  const done = dialog.getByRole("button", { name: "Done" })
  await expect(done).toBeDisabled()
  await dialog
    .getByRole("checkbox", { name: "I have stored this token" })
    .check()
  await done.click()

  // Not copied: warned first, and going back keeps the token on screen.
  await expect(dialog).toContainText("You have not copied the token")
  await dialog.getByRole("button", { name: "Back to the token" }).click()
  await expect(dialog.getByRole("textbox", { name: "Bot token" })).toBeVisible()

  // Leaving anyway is a deliberate second step.
  await done.click()
  await dialog.getByRole("button", { name: "Close without copying" }).click()
  await expect(dialog).toBeHidden()
})

test("A copied and stored token closes without a warning", async ({ page }) => {
  const { dialog } = await revealToken(page)
  await storeTokenAndClose(dialog)
})

test("Copying from the field by keyboard counts as copied", async ({
  page,
}) => {
  const { dialog } = await revealToken(page)

  const field = dialog.getByRole("textbox", { name: "Bot token" })
  await field.focus()
  await page.keyboard.press("ControlOrMeta+KeyC")
  await dialog
    .getByRole("checkbox", { name: "I have stored this token" })
    .check()
  await dialog.getByRole("button", { name: "Done" }).click()
  await expect(dialog).toBeHidden()
})

test("Every other dialog still closes on Escape and a click outside", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/bots")
  const dialog = page.getByRole("dialog", { name: "Add Bot" })

  await page.getByRole("button", { name: "Add Bot" }).click()
  await expect(dialog).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(dialog).toBeHidden()

  await page.getByRole("button", { name: "Add Bot" }).click()
  await expect(dialog).toBeVisible()
  await page.mouse.click(5, 5)
  await expect(dialog).toBeHidden()
})
