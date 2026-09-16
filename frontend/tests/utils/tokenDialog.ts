import { expect, type Locator } from "@playwright/test"

/**
 * Leave a one-time token dialog the way a careful reader does: copy the
 * token, say it is stored, and close. The dialog refuses anything quicker.
 */
export async function storeTokenAndClose(dialog: Locator) {
  await dialog.getByRole("button", { name: "Copy" }).click()
  await expect(dialog.getByRole("button", { name: "Copied" })).toBeVisible()
  await dialog
    .getByRole("checkbox", { name: "I have stored this token" })
    .check()
  await dialog.getByRole("button", { name: "Done" }).click()
  await expect(dialog).toBeHidden()
}
