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
