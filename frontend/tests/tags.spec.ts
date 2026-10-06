import { expect, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"
import { randomEmail } from "./utils/random"
import { tagLine, tagLink } from "./utils/tags"
import { taskLine } from "./utils/tasks"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("A tag is created, renamed and deleted on the Tags page", async ({
  page,
  request,
}) => {
  const email = randomEmail()
  await logInUser(page, email)
  const api = `${process.env.VITE_API_URL}/api/v1`
  const userToken = await page.evaluate(() =>
    localStorage.getItem("access_token"),
  )
  const asUser = { Authorization: `Bearer ${userToken}` }

  await page.goto("/tags")
  await expect(page.getByRole("heading", { name: "Tags" })).toBeVisible()
  await page.getByRole("button", { name: "New tag" }).click()
  const newName = page.getByRole("textbox", { name: "Tag name" })
  await newName.fill("errnds")
  await newName.press("Enter")
  await expect(
    page.getByRole("complementary", { name: "errnds" }),
  ).toBeVisible()
  await page.keyboard.press("Escape")
  const row = tagLine(page, "errnds")
  await expect(row).toContainText("No open tasks")

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
  await expect(row).toContainText("2 open")

  await tagLink(page, "errnds").click()
  const panel = page.getByRole("complementary", { name: "errnds" })
  const name = panel.getByRole("textbox", { name: "Tag name" })
  await name.fill("errands")
  await name.press("Enter")
  await page.keyboard.press("Escape")

  const renamed = tagLine(page, "errands")
  await expect(renamed).toContainText("2 open")
  await renamed.getByRole("link", { name: /2 open/ }).click()
  await expect(page).toHaveURL(/tag=errands/)
  for (const title of ["Buy stamps", "Return the parcel"]) {
    await expect(
      page
        .getByRole("listitem")
        .filter({ has: page.getByRole("link", { name: title }) }),
    ).toContainText("errands")
  }

  await page.goto("/tags")
  await tagLink(page, "errands").click()
  await page
    .getByRole("complementary", { name: "errands" })
    .getByRole("button", { name: "Delete tag" })
    .click()
  const deleteDialog = page.getByRole("dialog", {
    name: "Delete the tag errands?",
  })
  await expect(deleteDialog).toContainText("taken off 2 tasks")
  await deleteDialog.getByRole("button", { name: "Delete" }).click()
  await expect(page.getByText("“errands” was deleted")).toBeVisible()
  await expect(renamed).toHaveCount(0)
  await expect(tagLine(page, "weekend")).toBeVisible()

  await page.goto("/tasks")
  const task = taskLine(page, "Buy stamps")
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

test("The arrow keys walk the tags as listed, and a refused name stays with its reason", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  for (const name of ["alpha", "beta", "gamma"]) {
    await api.create("/tags/", { name })
  }

  await page.goto("/tags")
  await tagLink(page, "alpha").click()
  const first = page.getByRole("complementary", { name: "alpha" })
  await expect(first).toContainText("1 of 3")
  await page.keyboard.press("ArrowDown")
  await expect(page.getByRole("complementary", { name: "beta" })).toBeVisible()
  await page.keyboard.press("ArrowUp")
  await expect(page.getByRole("complementary", { name: "alpha" })).toBeVisible()

  // A new tag is a draft in the column; a name in use is refused under the
  // field, which keeps what was typed.
  await page.getByRole("button", { name: "New tag" }).click()
  const draft = page.getByRole("textbox", { name: "Tag name" })
  await draft.fill("beta")
  await page.getByRole("button", { name: "Create tag" }).click()
  await expect(page.getByRole("alert")).toContainText(
    "You already have a tag named “beta”.",
  )
  await expect(draft).toHaveValue("beta")
  await draft.fill("delta")
  await draft.press("Enter")
  await expect(page.getByRole("complementary", { name: "delta" })).toBeVisible()
  await expect(tagLink(page, "delta")).toBeVisible()
})
