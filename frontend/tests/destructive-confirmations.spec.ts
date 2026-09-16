import { expect, type Locator, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

/**
 * A confirmation says what is lost — and what is not — before the button that
 * does it: its description is read first, and is more than a restatement of
 * the title.
 */
async function expectConsequenceFirst(
  dialog: Locator,
  button: string,
  consequence: string | RegExp,
) {
  await expect(dialog).toBeVisible()
  const description = dialog.locator("[data-slot=dialog-description]")
  await expect(description).toContainText(consequence)
  const act = dialog.getByRole("button", { name: button, exact: true })
  const before = await description.evaluate(
    (text, target) =>
      Boolean(
        text.compareDocumentPosition(target as Node) &
          Node.DOCUMENT_POSITION_FOLLOWING,
      ),
    await act.elementHandle(),
  )
  expect(before).toBe(true)
  await dialog.getByRole("button", { name: "Cancel" }).click()
  await expect(dialog).toBeHidden()
}

async function scene(page: Page) {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Garden" })
  await api.create("/tags/", { name: "outdoors" })
  await api.create("/tasks/", {
    title: "Prune the roses",
    project_id: project.id,
    tags: ["outdoors"],
  })
  const bot = await api.create("/bot-users/", {
    name: "Garden bot",
    scope: { project_ids: [project.id], permissions: { read_tasks: true } },
  })
  await api.create(`/bot-users/${bot.id}/token`)
  return { project, bot }
}

test("Every destructive confirmation names its consequence before its button", async ({
  page,
}) => {
  const { project, bot } = await scene(page)

  await page.goto(`/projects?project=${project.id}`)
  await page.getByRole("button", { name: "Delete project" }).click()
  await expectConsequenceFirst(
    page.getByRole("dialog", { name: "Delete Garden?" }),
    "Delete",
    "can be restored",
  )

  await page.goto("/tags")
  await page.getByRole("row", { name: "Open outdoors" }).click()
  await page.getByRole("button", { name: "Delete tag" }).click()
  await expectConsequenceFirst(
    page.getByRole("dialog", { name: /Delete the tag outdoors/ }),
    "Delete",
    "the task stays as it is",
  )

  await page.goto(`/bots?bot=${bot.id}`)
  await page.getByRole("button", { name: "Revoke" }).click()
  await expectConsequenceFirst(
    page.getByRole("dialog", { name: /Revoke the token/ }),
    "Revoke",
    "you can issue it a new token later",
  )
  await page.getByRole("button", { name: "Delete bot user" }).click()
  await expectConsequenceFirst(
    page.getByRole("dialog", { name: "Delete Garden bot?" }),
    "Delete",
    "Tasks assigned to it stay assigned",
  )

  await page.goto("/tasks")
  await page.getByRole("checkbox", { name: "Select Prune the roses" }).check()
  await page.getByRole("button", { name: "Delete", exact: true }).click()
  await expectConsequenceFirst(
    page.getByRole("dialog", { name: "Delete 1 task?" }),
    "Delete",
    "can be restored",
  )

  await page.goto("/settings")
  await page.getByRole("tab", { name: "Danger zone" }).click()
  await page.getByRole("button", { name: "Delete Account" }).click()
  await expectConsequenceFirst(
    page.getByRole("dialog"),
    "Delete",
    "permanently deleted",
  )
})
