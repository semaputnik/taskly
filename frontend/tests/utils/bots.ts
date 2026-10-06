import { expect, type Locator, type Page } from "@playwright/test"
import { storeTokenAndClose } from "./tokenDialog"

/** A bot user's line on the Bots page, found by the name it is opened by. */
export const botLine = (page: Page, name: string): Locator =>
  page
    .getByRole("listitem")
    .filter({ has: page.getByRole("link", { name, exact: true }) })

/** Open a bot user's column from its line, as a reader does. */
export const openBot = (page: Page, name: string) =>
  page.getByRole("link", { name, exact: true }).click()

/** A bot user's column, named by the record. */
export const botColumn = (page: Page, name: string): Locator =>
  page.getByRole("complementary", { name, exact: true })

/**
 * Make a bot user the way a person does: draft it in the column, tick what it
 * may reach and do, and create it. Its token is shown once, and is returned
 * after the reveal has been stored and closed.
 */
export async function createBotInColumn(
  page: Page,
  {
    name,
    projects = [],
    permissions = [],
  }: { name: string; projects?: string[]; permissions?: string[] },
) {
  await page.getByRole("button", { name: "New bot user" }).click()
  const draft = page.getByRole("complementary", { name: "New bot user" })
  await draft.getByRole("textbox", { name: "Bot name" }).fill(name)
  for (const project of projects) {
    await draft.getByRole("checkbox", { name: project }).check()
  }
  for (const permission of permissions) {
    await draft.getByRole("checkbox", { name: permission }).check()
  }
  await draft.getByRole("button", { name: "Create and issue token" }).click()

  const dialog = page.getByRole("dialog", { name: `Token for ${name}` })
  await expect(dialog).toBeVisible()
  const token = await dialog
    .getByRole("textbox", { name: "Bot token" })
    .inputValue()
  await storeTokenAndClose(dialog)
  await expect(botColumn(page, name)).toBeVisible()
  return token
}
