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
    page.getByRole("dialog", { name: "Book the vet for Friday" }),
  ).toBeVisible()
  await page.reload()
  await expect(page.getByRole("textbox", { name: "Task title" })).toHaveValue(
    "Book the vet for Friday",
  )
})

test("A batch due date says a recurring task is in the way before sending", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tasks/", { title: "Water the plants" })
  await api.create("/tasks/", {
    title: "Take out the bins",
    due_date: "2030-01-07",
    recurrence: { frequency: "weekly" },
  })

  const batches: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/tasks/bulk")) batches.push(request.url())
  })

  await page.goto("/tasks")
  await page.getByRole("checkbox", { name: "Select Water the plants" }).check()
  await page.getByRole("checkbox", { name: "Select Take out the bins" }).check()
  await page.getByLabel("Set due date").fill("2030-02-01")

  await expect(page.getByText("Nothing was changed: 1 task")).toBeVisible()
  await expect(
    page.getByText(
      "“Take out the bins” repeats. Move its due date from the task itself",
    ),
  ).toBeVisible()
  expect(batches).toEqual([])
})
