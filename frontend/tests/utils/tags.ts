import type { Locator, Page } from "@playwright/test"

/** The Tags page's list of lines, not the look-alike groups above it. */
export const tagLines = (page: Page) =>
  page.getByRole("list", { name: "All tags", exact: true })

/** A tag's name on its line: the link that opens its column. */
export const tagLink = (page: Page, name: string): Locator =>
  tagLines(page).getByRole("link", { name, exact: true })

/** The line that has this tag's name as its link. */
export const tagLine = (page: Page, name: string): Locator =>
  tagLines(page)
    .getByRole("listitem")
    .filter({ has: page.getByRole("link", { name, exact: true }) })

/** A look-alike group, found by the names it lists, in the order they are drawn. */
export const lookAlike = (page: Page, names: string): Locator =>
  page
    .getByRole("region", { name: "Look alike" })
    .getByRole("listitem", { name: `Look alike: ${names}` })
