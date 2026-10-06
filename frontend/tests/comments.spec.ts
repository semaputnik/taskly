import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

/**
 * A task carrying the user's own comment, open on the panel's Activity section. With
 * `clock`, time only moves when the test moves it.
 */
async function openComment(page: Page, { clock = true } = {}) {
  if (clock) await page.clock.install()
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", { title: "Renew the lease" })
  const comment = await api.create(`/tasks/${task.id}/comments/`, {
    body: "Landlord wants it signed by Friday",
  })

  await page.goto(`/tasks?task=${task.id}`)
  const panel = page.getByRole("complementary", { name: "Renew the lease" })
  const shown = panel
    .getByRole("listitem")
    .filter({ hasText: "Landlord wants it signed by Friday" })
  await expect(shown).toBeVisible()
  const stored = async () =>
    (await (await api.get(`/tasks/${task.id}/comments/`)).json()).data
  return { panel, shown, comment, stored }
}

test("A deleted comment can be brought back with Undo", async ({ page }) => {
  const { shown, comment, stored } = await openComment(page)

  await shown.getByRole("button", { name: "Delete comment" }).click()
  await expect(shown).toHaveCount(0)
  await page.getByRole("button", { name: "Undo" }).click()

  // It comes back as it was: nothing was deleted on the server.
  await expect(shown).toBeVisible()
  await page.clock.fastForward(30_000)
  await expect(shown).toBeVisible()
  expect(await stored()).toEqual([comment])
})

test("Undo is reachable from the keyboard", async ({ page }) => {
  const { shown, comment, stored } = await openComment(page, { clock: false })

  await shown.getByRole("button", { name: "Delete comment" }).press("Enter")
  await expect(shown).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Undo" })).toBeVisible()
  // The notifications region answers to its hotkey; Tab reaches the notice,
  // which is read out, and then its Undo.
  await page.keyboard.press("Alt+KeyT")
  await expect(page.locator("[data-sonner-toaster]")).toBeFocused()
  await page.keyboard.press("Tab")
  await expect(page.locator("[data-sonner-toast]")).toBeFocused()
  await page.keyboard.press("Tab")
  await expect(page.getByRole("button", { name: "Undo" })).toBeFocused()
  await page.keyboard.press("Enter")

  await expect(shown).toBeVisible()
  expect(await stored()).toEqual([comment])
})

test("A comment is deleted once the undo window lapses", async ({ page }) => {
  const { shown, stored } = await openComment(page)

  await shown.getByRole("button", { name: "Delete comment" }).click()
  await expect(page.getByRole("button", { name: "Undo" })).toBeVisible()
  // A pointer resting on a notice holds it open, so it is moved clear.
  await page.mouse.move(0, 0)

  // The window is long enough to notice: still open after a few seconds.
  await page.clock.fastForward(5_000)
  await expect(page.getByRole("button", { name: "Undo" })).toBeVisible()
  expect(await stored()).toHaveLength(1)

  await page.clock.fastForward(10_000)
  await expect.poll(stored).toEqual([])
  await expect(shown).toHaveCount(0)
})

test("Closing the panel leaves the notice, and the deletion waits for its window", async ({
  page,
}) => {
  const { shown, stored } = await openComment(page)

  await shown.getByRole("button", { name: "Delete comment" }).click()
  await expect(page.getByRole("button", { name: "Undo" })).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(page.locator("[data-record-column]")).toHaveCount(0)

  // No modal holds the notice back any more, so it outlives the panel it was
  // raised in, and Undo still returns the very same comment.
  await expect(page.getByRole("button", { name: "Undo" })).toBeVisible()
  expect(await stored()).toHaveLength(1)
  await page.mouse.move(0, 0)
  await page.clock.fastForward(15_000)
  await expect.poll(stored).toEqual([])
})

test("Undo after the panel has closed brings the comment back", async ({
  page,
}) => {
  const { shown, stored, comment } = await openComment(page)

  await shown.getByRole("button", { name: "Delete comment" }).click()
  await page.keyboard.press("Escape")
  await expect(page.locator("[data-record-column]")).toHaveCount(0)
  await page.getByRole("button", { name: "Undo" }).click()
  await page.clock.fastForward(30_000)
  expect(await stored()).toEqual([comment])
})

test("A failed deletion brings the comment back and says so", async ({
  page,
}) => {
  const { shown, stored } = await openComment(page)
  await page.route("**/api/v1/comments/*", (route) =>
    route.request().method() === "DELETE"
      ? route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ detail: "The server is busy" }),
        })
      : route.fallback(),
  )

  await shown.getByRole("button", { name: "Delete comment" }).click()
  await expect(shown).toHaveCount(0)
  await page.mouse.move(0, 0)
  await page.clock.fastForward(15_000)

  await expect(page.getByText("The server is busy")).toBeVisible()
  await expect(page.getByText("could not be deleted")).toBeVisible()
  await expect(shown).toBeVisible()
  expect(await stored()).toHaveLength(1)
})
