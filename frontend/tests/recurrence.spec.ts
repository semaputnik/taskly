import { expect, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

test("Every N days holds the same minimum in the panel and the API", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", {
    title: "Water the ferns",
    due_date: "2026-10-01",
    recurrence: { frequency: "every_n_days", interval_days: 3 },
  })

  // One day is refused by the API.
  const refused = await api.patch(`/tasks/${task.id}`, {
    recurrence: { frequency: "every_n_days", interval_days: 1 },
  })
  expect(refused.status()).toBe(422)

  await page.goto(`/tasks?view=table&task=${task.id}`)
  const panel = page.getByRole("dialog", { name: "Water the ferns" })
  const days = panel.getByRole("spinbutton", { name: "Days between repeats" })
  await expect(days).toHaveValue("3")

  // The panel refuses the same value, says why, and keeps the rule in force.
  await days.fill("1")
  await days.press("Enter")
  await expect(page.getByText("Every N days starts at 2 days")).toBeVisible()
  await expect(days).toHaveValue("3")
  const unchanged = await (await api.get(`/tasks/${task.id}`)).json()
  expect(unchanged.recurrence.interval_days).toBe(3)

  // And accepts the same value the API does.
  await days.fill("2")
  await days.press("Enter")
  await expect
    .poll(
      async () =>
        (await (await api.get(`/tasks/${task.id}`)).json()).recurrence,
    )
    .toEqual({ frequency: "every_n_days", interval_days: 2 })
  const accepted = await api.patch(`/tasks/${task.id}`, {
    recurrence: { frequency: "every_n_days", interval_days: 2 },
  })
  expect(accepted.ok()).toBe(true)
})
