import { expect, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

test("A tag's count on the Tags page matches the list it opens", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tasks/", { title: "Sweep the yard", tags: ["outdoors"] })
  const old = await api.create("/projects/", { name: "Old garden" })
  await api.create("/tasks/", {
    title: "Mend the fence",
    project_id: old.id,
    tags: ["outdoors"],
  })
  expect((await api.post(`/projects/${old.id}/archive`)).ok()).toBe(true)

  await page.goto("/tags")
  const row = page.getByRole("row", { name: "Open outdoors" })
  await expect(row).toContainText("1 task")
  // What the count leaves out is said beside it, not folded into it.
  await expect(row).toContainText("+ 1 in archived projects")

  await row.getByRole("link", { name: "1 task" }).click()
  await expect(page).toHaveURL(/tag=outdoors/)
  await expect(page.getByRole("row", { name: /Sweep the yard/ })).toBeVisible()
  await expect(page.getByRole("row", { name: /Mend the fence/ })).toHaveCount(0)
  await expect(page.getByText("1 task", { exact: true })).toBeVisible()

  // Deleting it says it reaches the archived task too.
  await page.goto("/tags")
  await page.getByRole("row", { name: "Open outdoors" }).click()
  await page.getByRole("button", { name: "Delete tag" }).click()
  await expect(
    page.getByRole("dialog", { name: /Delete the tag outdoors/ }),
  ).toContainText("taken off 2 tasks, 1 of them in an archived project")
})
