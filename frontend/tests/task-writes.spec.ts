import { expect, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

test("A refused title keeps what was typed, and leaving again retries", async ({
  page,
}) => {
  await newUser(page)
  const task = await (await userApi(page)).create("/tasks/", {
    title: "Book the vet",
  })

  let refusing = true
  const patches: string[] = []
  await page.route(`**/api/v1/tasks/${task.id}`, (route) => {
    if (route.request().method() !== "PATCH") return route.fallback()
    patches.push(route.request().postDataJSON().title)
    return refusing
      ? route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({ detail: "The title could not be saved." }),
        })
      : route.fallback()
  })

  await page.goto(`/tasks?task=${task.id}`)
  const title = page.getByRole("textbox", { name: "Task title" })
  await title.fill("Book the vet for Friday")
  await title.press("Enter")

  await expect(page.getByText("The title could not be saved.")).toBeVisible()
  await expect(title).toHaveValue("Book the vet for Friday")
  expect(patches).toEqual(["Book the vet for Friday"])

  // Still unsaved, so leaving the field again sends it again.
  refusing = false
  await title.focus()
  await title.press("Enter")
  await expect.poll(() => patches.length).toBe(2)
  await expect(
    page.getByRole("complementary", { name: "Book the vet for Friday" }),
  ).toBeVisible()
  await page.reload()
  await expect(page.getByRole("textbox", { name: "Task title" })).toHaveValue(
    "Book the vet for Friday",
  )
})
