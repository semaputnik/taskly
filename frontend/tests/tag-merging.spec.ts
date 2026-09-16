import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

async function vocabulary(page: Page) {
  const api = await userApi(page)
  return (await (await api.get("/tags/")).json()).data
    .map((tag: { name: string; task_count: number }) => [
      tag.name,
      tag.task_count,
    ])
    .sort()
}

test("Merging from a tag's panel moves its tasks and removes it", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tasks/", { title: "Ship 1.2", tags: ["Deploy"] })
  await api.create("/tasks/", { title: "Ship 1.3", tags: ["Deploy", "deploy"] })
  await api.create("/tasks/", { title: "Ship 1.4", tags: ["deploy"] })
  const old = await api.create("/projects/", { name: "Old" })
  await api.create("/tasks/", {
    title: "Ship 0.9",
    project_id: old.id,
    tags: ["Deploy"],
  })
  await api.post(`/projects/${old.id}/archive`)

  await page.goto("/tags")
  await page.getByRole("row", { name: "Open Deploy", exact: true }).click()
  const panel = page.getByRole("dialog", { name: "Deploy", exact: true })
  await panel.getByRole("combobox", { name: "Merge" }).click()
  await page.getByRole("option", { name: "deploy", exact: true }).click()

  // The confirmation says what goes, what survives and how many tasks change,
  // archived ones included, before the button that does it.
  const confirm = page.getByRole("dialog", { name: "Merge into deploy?" })
  const description = confirm.locator("[data-slot=dialog-description]")
  await expect(description).toContainText("The tag “Deploy” is removed.")
  await expect(description).toContainText(
    "3 tasks change to carry “deploy” instead, 1 of them in an archived project.",
  )
  await expect(description).toContainText("can't be undone")
  await expect(
    confirm.getByRole("radio", { name: /deploy 2 tasks/ }),
  ).toBeChecked()

  // Nothing happens until it is confirmed.
  await confirm.getByRole("button", { name: "Cancel" }).click()
  expect(await vocabulary(page)).toEqual([
    ["Deploy", 2],
    ["deploy", 2],
  ])

  await panel.getByRole("combobox", { name: "Merge" }).click()
  await page.getByRole("option", { name: "deploy", exact: true }).click()
  await confirm.getByRole("button", { name: "Merge into deploy" }).click()

  // The panel moves onto the tag that now carries the tasks.
  const survivor = page.getByRole("dialog", { name: "deploy", exact: true })
  await expect(survivor).toBeVisible()
  await expect(survivor).toContainText("3 tasks")
  await expect(survivor).toContainText("+ 1 in archived projects")
  expect(await vocabulary(page)).toEqual([["deploy", 3]])

  await page.keyboard.press("Escape")
  await expect(
    page.getByRole("row", { name: "Open Deploy", exact: true }),
  ).toHaveCount(0)
  await page
    .getByRole("row", { name: "Open deploy", exact: true })
    .getByRole("link")
    .click()
  for (const title of ["Ship 1.2", "Ship 1.3", "Ship 1.4"]) {
    await expect(
      page.getByRole("row", { name: new RegExp(title) }),
    ).toBeVisible()
  }

  await page.goto("/activity")
  await expect(
    page.getByRole("row").filter({ hasText: "Merged “Deploy” into deploy" }),
  ).toContainText("moving 3 tasks onto it")
})

test("A refused rename offers a merge instead, as its own confirmed act", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tasks/", { title: "Ship 1.2", tags: ["deploys"] })
  const tag = await api.create("/tags/", { name: "deploy" })

  const deploys = (await (await api.get("/tags/")).json()).data.find(
    (t: { name: string }) => t.name === "deploys",
  )
  await page.goto(`/tags?tag_id=${deploys.id}`)
  const name = page.getByRole("textbox", { name: "Tag name" })
  await name.fill("deploy")
  await name.press("Enter")

  await expect(page.getByText("You already have a tag named")).toBeVisible()
  const confirm = page.getByRole("dialog", { name: "Merge into deploy?" })
  await expect(confirm).toContainText("The tag “deploys” is removed.")
  await confirm.getByRole("button", { name: "Cancel" }).click()
  expect(await vocabulary(page)).toEqual([
    ["deploy", 0],
    ["deploys", 1],
  ])
  expect(tag.name).toBe("deploy")
})
