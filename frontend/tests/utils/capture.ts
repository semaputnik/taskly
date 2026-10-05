import { expect, type Page } from "@playwright/test"

/**
 * Open the task a single capture just made, from the notice it leaves: the
 * panel closes on creation, and "Open" in the notice is the way to the record.
 */
export async function openCaptured(page: Page) {
  await page
    .locator("[data-sonner-toast]")
    .filter({ hasText: "created" })
    .getByRole("button", { name: "Open" })
    .first()
    .click()
}

/**
 * Open the full draft from the keyboard: the `c` key works from every screen,
 * and it is the only way into the draft from the page itself now that the
 * navigation has no entry for it (FR-06.15).
 */
export async function openDraft(page: Page) {
  // The shell has to be listening before a key means anything to it.
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible()
  await page.keyboard.press("c")
}
