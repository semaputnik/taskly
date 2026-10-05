import { expect, type Locator, type Page } from "@playwright/test"

/** The task list's own list of lines, not the subtasks list in a panel. */
export const taskLines = (page: Page) =>
  page.getByRole("list", { name: "Tasks", exact: true })

/**
 * One line of the task list, found by the title it carries. The title is a
 * link, so a line is the list item that has one; a string matches the whole
 * title, a pattern matches as it is written.
 */
export const taskLine = (page: Page, title: string | RegExp): Locator =>
  taskLines(page)
    .getByRole("listitem")
    .filter({
      has: page.getByRole("link", {
        name: title,
        exact: typeof title === "string",
      }),
    })

/** The titles of the lines on screen, in the order they are drawn. */
export const lineTitles = (page: Page) =>
  taskLines(page).getByRole("listitem").getByRole("link")

/**
 * Choose in one of the menus on the row over the list: the button that says
 * what it is now, then the choice in the menu it opens.
 *
 * The menu is waited out when it has closed. One that is still on its way out
 * takes the next click on its button for a click outside itself, which no
 * reader's hand is quick enough to do.
 */
export async function chooseFilter(
  page: Page,
  button: string | RegExp,
  choice: string | RegExp,
) {
  await page
    .getByRole("button", { name: button, exact: typeof button === "string" })
    .click()
  await page
    .getByRole("menuitemradio", {
      name: choice,
      exact: typeof choice === "string",
    })
    .click()
  await expect(page.getByRole("menu")).toHaveCount(0)
}

/** Choose an order from the menu at the row's end, whatever it says now. */
export async function chooseOrder(page: Page, choice: string | RegExp) {
  await chooseFilter(page, /^Order:/, choice)
}
