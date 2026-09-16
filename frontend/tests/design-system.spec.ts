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
      await page.goto("/tasks")
      const add = page.getByRole("button", { name: "Add Task" }).first()
      expect(await textOnFill(add)).toBeGreaterThanOrEqual(AA)
    })

    test("Page subtitles and text links are readable", async ({ page }) => {
      await page.goto("/")
      const ground = await pageGround(page)
      const subtitle = page.getByText(
        "What needs you now, and what changed without you",
      )
      expect(await textOn(subtitle, ground)).toBeGreaterThanOrEqual(AA)

      // A text link is read on the page ground and on the sheets laid on it.
      const link = page.getByRole("link", { name: "Connect a bot user" })
      expect(await textOn(link, ground)).toBeGreaterThanOrEqual(AA)
      expect(
        await textOn(link, await token(page, "--card")),
      ).toBeGreaterThanOrEqual(AA)
    })

    test("A modal layer visibly demotes the page behind it", async ({
      page,
    }) => {
      await page.goto("/tasks")
      const ground = await pageGround(page)
      await page.getByRole("button", { name: "Add Task" }).first().click()
      const overlay = page.locator("[data-slot=sheet-overlay]")
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
