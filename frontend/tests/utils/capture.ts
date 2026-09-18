import type { Page } from "@playwright/test"

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
