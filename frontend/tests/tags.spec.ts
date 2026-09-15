import { expect, test } from "@playwright/test"
import { createUser } from "./utils/privateApi.ts"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("A tag is created, renamed and deleted on the Tags page", async ({
  page,
  request,
}) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await logInUser(page, email, password)
  const api = `${process.env.VITE_API_URL}/api/v1`
  const userToken = await page.evaluate(() =>
    localStorage.getItem("access_token"),
  )
  const asUser = { Authorization: `Bearer ${userToken}` }

  await page.goto("/tags")
  await expect(page.getByRole("heading", { name: "Tags" })).toBeVisible()
  await page.getByRole("button", { name: "Add Tag" }).click()
  await page.getByPlaceholder("Tag name").fill("errnds")
  await page.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Tag created successfully")).toBeVisible()
  const row = page.getByRole("row").filter({ hasText: "errnds" })
  await expect(row).toContainText("No tasks")

  // Two tasks carry it; they are created over the API, the task form has its
  // own tests.
  for (const title of ["Buy stamps", "Return the parcel"]) {
    const created = await request.post(`${api}/tasks/`, {
      headers: asUser,
      data: { title, tags: ["errnds", "weekend"] },
    })
    expect(created.ok()).toBe(true)
  }
  await page.reload()
  await expect(row).toContainText("2 tasks")

  await page.getByRole("button", { name: "Actions for errnds" }).click()
  await page.getByRole("menuitem", { name: "Rename Tag" }).click()
  const renameDialog = page.getByRole("dialog", { name: "Rename Tag" })
  await renameDialog.getByPlaceholder("Tag name").fill("errands")
  await renameDialog.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Tag renamed successfully")).toBeVisible()

  const renamed = page.getByRole("row").filter({ hasText: "errands" })
  await expect(renamed).toContainText("2 tasks")
  await renamed.getByRole("link", { name: "2 tasks" }).click()
  await expect(page).toHaveURL(/tag=errands/)
  for (const title of ["Buy stamps", "Return the parcel"]) {
    await expect(
      page.getByRole("row", { name: new RegExp(title) }),
    ).toContainText("errands")
  }

  await page.goto("/tags")
  await page.getByRole("button", { name: "Actions for errands" }).click()
  await page.getByRole("menuitem", { name: "Delete Tag" }).click()
  const deleteDialog = page.getByRole("dialog", {
    name: "Delete the tag errands?",
  })
  await expect(deleteDialog).toContainText("taken off 2 tasks")
  await deleteDialog.getByRole("button", { name: "Delete" }).click()
  await expect(page.getByText("“errands” was deleted")).toBeVisible()
  await expect(renamed).toHaveCount(0)
  await expect(
    page.getByRole("row").filter({ hasText: "weekend" }),
  ).toBeVisible()

  await page.goto("/tasks")
  const task = page.getByRole("row", { name: /Buy stamps/ })
  await expect(task).toContainText("weekend")
  await expect(task).not.toContainText("errands")

  await page.goto("/activity")
  await expect(page.getByText("Created the tag errnds")).toBeVisible()
  await expect(
    page.getByText("Renamed the tag “errnds” to errands"),
  ).toBeVisible()
  await expect(
    page.getByText("Deleted the tag errands, taking it off 2 tasks"),
  ).toBeVisible()
})
