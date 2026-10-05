import { expect, type Page, test } from "@playwright/test"
import { newUser } from "./utils/account"
import { demotion, pageGround, textOn, textOnFill, token } from "./utils/colour"

test.use({ storageState: { cookies: [], origins: [] } })

// Normal-weight text has to clear WCAG AA.
const AA = 4.5
// How far the page ground has to fall in OKLab lightness under a modal veil
// before the change reads as the page receding, not as noise.
const PERCEPTIBLE = 0.06

async function inTheme(page: Page, theme: "light" | "dark") {
  await page.addInitScript((chosen) => {
    localStorage.setItem("vite-ui-theme", chosen)
  }, theme)
}

for (const theme of ["light", "dark"] as const) {
  test.describe(`${theme} theme`, () => {
    test.beforeEach(async ({ page }) => {
      await inTheme(page, theme)
      await newUser(page)
    })

    test("The primary action is readable on its fill", async ({ page }) => {
      // The Projects page's own button is the filled one.
      await page.goto("/projects")
      const add = page
        .getByRole("main")
        .getByRole("button", { name: "Add Project" })
      expect(await textOnFill(add)).toBeGreaterThanOrEqual(AA)
    })

    test("The task list's quiet text is readable", async ({ page }) => {
      await page.goto("/tasks")
      const ground = await pageGround(page)
      // The filters and the order are text, quiet until set.
      for (const name of ["Any project", "Newest first"]) {
        const control = page.getByRole("button", { name }).first()
        await expect(control).toBeVisible()
        expect(await textOn(control, ground)).toBeGreaterThanOrEqual(AA)
      }
      // The muted half of the counts sentence.
      const counts = page.getByText("Nothing is open.")
      await expect(counts).toBeVisible()
      expect(await textOn(counts, ground)).toBeGreaterThanOrEqual(AA)
    })

    test("Page subtitles and text links are readable", async ({ page }) => {
      await page.goto("/")
      const ground = await pageGround(page)
      // The muted half of the sentence under the date.
      const subtitle = page.getByText(
        "Your bot users have made no changes yet.",
      )
      expect(await textOn(subtitle, ground)).toBeGreaterThanOrEqual(AA)

      // A text link is read on the page ground and on the sheets laid on it.
      // The empty Changes log points at the bot users in its sentence.
      const link = page.getByRole("link", { name: "bot users", exact: true })
      expect(await textOn(link, ground)).toBeGreaterThanOrEqual(AA)
      expect(
        await textOn(link, await token(page, "--card")),
      ).toBeGreaterThanOrEqual(AA)
    })

    test("A modal layer visibly demotes the page behind it", async ({
      page,
    }) => {
      // A record's column is no modal layer, so the one opened here is a
      // confirmation: the sort a reader must answer before going on.
      await page.goto("/settings")
      await page.getByRole("tab", { name: "Danger zone" }).click()
      const ground = await pageGround(page)
      await page.getByRole("button", { name: "Delete Account" }).click()
      const overlay = page.locator("[data-slot=dialog-overlay]")
      await expect(overlay).toBeVisible()
      await overlay.evaluate((node) =>
        Promise.all(node.getAnimations().map((a) => a.finished)),
      )
      const veil = await overlay.evaluate(
        (node) => getComputedStyle(node).backgroundColor,
      )
      expect(await demotion(page, ground, veil)).toBeGreaterThanOrEqual(
        PERCEPTIBLE,
      )
    })

    test("Native controls follow the theme", async ({ page }) => {
      await page.goto("/tasks")
      const scheme = await page.evaluate(
        () => getComputedStyle(document.documentElement).colorScheme,
      )
      expect(scheme).toBe(theme)
    })
  })
}
