import { expect, type Locator } from "@playwright/test"

/**
 * Leave a one-time reveal dialog the way a careful reader does: copy what it
 * shows, say it is stored, and close. The dialog refuses anything quicker.
 * `noun` is what the dialog calls the value: a token, or a webhook secret.
 */
export async function storeSecretAndClose(
  dialog: Locator,
  noun: "token" | "secret" = "token",
) {
  await dialog.getByRole("button", { name: "Copy" }).click()
  await expect(dialog.getByRole("button", { name: "Copied" })).toBeVisible()
  await dialog
    .getByRole("checkbox", { name: `I have stored this ${noun}` })
    .check()
  await dialog.getByRole("button", { name: "Done" }).click()
  await expect(dialog).toBeHidden()
}
