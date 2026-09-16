import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

async function openTask(page: Page) {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tags/", { name: "errands" })
  const task = await api.create("/tasks/", { title: "Buy stamps" })
  await page.goto(`/tasks?task=${task.id}`)
  const panel = page.getByRole("dialog", { name: "Buy stamps" })
  const field = panel.getByRole("combobox", { name: "Tags" })
  const vocabulary = async () =>
    (await (await api.get("/tags/")).json()).data.map(
      (tag: { name: string }) => tag.name,
    )
  const onTask = async () =>
    (await (await api.get(`/tasks/${task.id}`)).json()).tags
  return { panel, field, vocabulary, onTask }
}

test("Tabbing past a half-typed tag adds nothing and creates nothing", async ({
  page,
}) => {
  const { panel, field, vocabulary, onTask } = await openTask(page)

  await field.fill("err")
  await field.press("Tab")

  // The typed text stays where it was, and says it was not added.
  await expect(field).toHaveValue("err")
  await expect(panel.getByText("Not added yet")).toBeVisible()
  // Give a save that should not happen the time to happen.
  await page.waitForTimeout(500)
  expect(await onTask()).toEqual([])
  expect(await vocabulary()).toEqual(["errands"])
})

test("The field says whether Enter attaches a tag or creates one", async ({
  page,
}) => {
  const { panel, field, vocabulary, onTask } = await openTask(page)

  await field.fill("errands")
  await expect(panel.getByText("Enter adds your tag errands")).toBeVisible()
  await field.press("Enter")
  await expect(
    panel.getByRole("button", { name: "Remove tag errands" }),
  ).toBeVisible()
  await expect.poll(onTask).toEqual(["errands"])

  await field.fill("Errands")
  await expect(
    panel.getByText("Enter creates a new tag, Errands"),
  ).toBeVisible()
  await field.press("Enter")
  await expect
    .poll(async () => (await onTask()).sort())
    .toEqual(["Errands", "errands"])
  expect((await vocabulary()).sort()).toEqual(["Errands", "errands"])
  await expect(field).toHaveValue("")
})
