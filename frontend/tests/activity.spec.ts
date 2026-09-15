import { expect, test } from "@playwright/test"
import { createUser } from "./utils/privateApi.ts"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("A user's own changes appear on the Activity page, newest first", async ({
  page,
}) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await logInUser(page, email, password)

  await page.goto("/tasks")
  await page.getByRole("button", { name: "Add Task" }).click()
  await page.getByPlaceholder("Task title").fill("Renew the passport")
  await page.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Task created successfully")).toBeVisible()

  await page
    .getByRole("row", { name: /Renew the passport/ })
    .getByRole("checkbox", { name: "Mark as completed" })
    .click()
  await expect(
    page
      .getByRole("row", { name: /Renew the passport/ })
      .getByRole("checkbox", { name: "Mark as not completed" }),
  ).toBeVisible()

  await page.goto("/activity")
  const rows = page.getByRole("row").filter({ hasText: "Renew the passport" })
  await expect(rows).toHaveCount(2)
  await expect(rows.nth(0)).toContainText("Completed Renew the passport")
  await expect(rows.nth(1)).toContainText("Created Renew the passport in Inbox")
  await expect(rows.nth(0)).toContainText("You")

  // The task still exists, so its entry links to it.
  await rows.nth(1).getByRole("link", { name: "Renew the passport" }).click()
  await expect(page).toHaveURL(/\/tasks\?project_id=/)
  await expect(
    page.getByRole("row", { name: /Renew the passport/ }),
  ).toBeVisible()
})

test("A deleted task can be restored from the Activity page", async ({
  page,
}) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await logInUser(page, email, password)

  await page.goto("/tasks")
  await page.getByRole("button", { name: "Add Task" }).click()
  await page.getByPlaceholder("Task title").fill("Cancel the gym")
  await page.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Task created successfully")).toBeVisible()

  const taskRow = page.getByRole("row", { name: /Cancel the gym/ })
  await taskRow.getByRole("button").last().click()
  await page.getByRole("menuitem", { name: "Delete Task" }).click()
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Delete", exact: true })
    .click()
  await expect(page.getByText("Task deleted successfully")).toBeVisible()
  await expect(taskRow).toHaveCount(0)

  await page.goto("/activity")
  const deletion = page
    .getByRole("row")
    .filter({ hasText: "Deleted Cancel the gym" })
  await deletion.getByRole("button", { name: "Restore" }).click()
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Restore", exact: true })
    .click()
  await expect(page.getByText("“Cancel the gym” restored")).toBeVisible()
  await expect(
    page.getByRole("row").filter({ hasText: "Restored Cancel the gym" }),
  ).toBeVisible()
  // Its rows are back, so the deletion offers nothing more to restore.
  await expect(deletion.getByRole("button", { name: "Restore" })).toHaveCount(0)

  await page.goto("/tasks")
  await expect(page.getByRole("row", { name: /Cancel the gym/ })).toBeVisible()
})
