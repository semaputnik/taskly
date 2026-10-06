import { expect, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"
import { tagLine, tagLink } from "./utils/tags"

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
  const line = tagLine(page, "outdoors")
  await expect(line).toContainText("created by you")
  await expect(line).toContainText("1 open")
  // What the count leaves out is said beside it, not folded into it.
  await expect(line).toContainText("+ 1 in archived projects")

  await line.getByRole("link", { name: /1 open/ }).click()
  await expect(page).toHaveURL(/tag=outdoors/)
  await expect(page.getByRole("link", { name: "Sweep the yard" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Mend the fence" })).toHaveCount(
    0,
  )
  await expect(page.getByText("1 task", { exact: true })).toBeVisible()

  // The column says the same, and deleting says it reaches the archived task
  // too, at its foot and again in the confirmation.
  await page.goto("/tags")
  await tagLink(page, "outdoors").click()
  const column = page.getByRole("complementary", { name: "outdoors" })
  await expect(column).toContainText("1 open · 1 in an archived project")
  await expect(column).toContainText(
    "Deleting takes it off 2 tasks, 1 of them in an archived project.",
  )
  await column.getByRole("link", { name: /Open the list/ }).click()
  await expect(page).toHaveURL(/tag=outdoors/)

  await page.goto("/tags")
  await tagLink(page, "outdoors").click()
  await page.getByRole("button", { name: "Delete tag" }).click()
  await expect(
    page.getByRole("dialog", { name: /Delete the tag outdoors/ }),
  ).toContainText("taken off 2 tasks, 1 of them in an archived project")
})

test("A tag with no open task says so in words, and the column lists the tasks it has", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tags/", { name: "website" })
  await api.create("/tasks/", { title: "Rewrite the copy", tags: ["copy"] })

  await page.goto("/tags")
  await expect(tagLine(page, "website")).toContainText("No open tasks")
  await expect(
    tagLine(page, "website").getByRole("link", { name: /open/ }),
  ).toHaveCount(0)

  await tagLink(page, "copy").click()
  const column = page.getByRole("complementary", { name: "copy" })
  const tasks = column.getByRole("region", { name: "Open tasks" })
  await expect(tasks).toContainText("Rewrite the copy")
  await expect(tasks).toContainText("Inbox")
})
