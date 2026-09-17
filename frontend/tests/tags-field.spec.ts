import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

async function openTask(page: Page, tags: string[] = []) {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tags/", { name: "errands" })
  await api.create("/tags/", { name: "deploy" })
  const task = await api.create("/tasks/", { title: "Buy stamps", tags })
  await page.goto(`/tasks?task=${task.id}`)
  const panel = page.getByRole("dialog", { name: "Buy stamps" })
  const vocabulary = async () =>
    (await (await api.get("/tags/")).json()).data
      .map((tag: { name: string }) => tag.name)
      .sort()
  const onTask = async () =>
    ((await (await api.get(`/tasks/${task.id}`)).json()).tags as string[])
      .slice()
      .sort()
  const search = page.getByRole("combobox", { name: "Search or create a tag" })
  const openPicker = async () => {
    await panel.getByRole("button", { name: "Add tag" }).click()
    await expect(search).toBeFocused()
  }
  return { api, task, panel, search, openPicker, vocabulary, onTask }
}

const option = (page: Page, name: string | RegExp) =>
  page.getByRole("option", { name })

test("Tags sit on the property row as chips beside one Add tag button", async ({
  page,
}) => {
  const { panel } = await openTask(page, ["errands", "deploy"])

  await expect(
    panel.getByRole("button", { name: "Remove tag errands" }),
  ).toBeVisible()
  await expect(
    panel.getByRole("button", { name: "Remove tag deploy" }),
  ).toBeVisible()
  const add = panel.getByRole("button", { name: "Add tag" })
  await expect(add).toBeVisible()
  // No stacked field under the row any more.
  await expect(panel.getByRole("combobox", { name: "Tags" })).toHaveCount(0)

  // The label lines up with the first line of the value, not its middle.
  const label = panel.getByText("Tags", { exact: true })
  const labelBox = await label.boundingBox()
  const chipBox = await panel
    .getByRole("button", { name: "Remove tag errands" })
    .boundingBox()
  expect(labelBox && chipBox).toBeTruthy()
  if (labelBox && chipBox) {
    const labelMiddle = labelBox.y + labelBox.height / 2
    expect(
      Math.abs(labelMiddle - (chipBox.y + chipBox.height / 2)),
    ).toBeLessThan(8)
  }
})

test("Choosing rows toggles tags, and the popover stays open", async ({
  page,
}) => {
  const { search, openPicker, onTask } = await openTask(page)
  await openPicker()

  await option(page, /^errands/).click()
  await expect.poll(onTask).toEqual(["errands"])
  await option(page, /^deploy/).click()
  await expect.poll(onTask).toEqual(["deploy", "errands"])
  await expect(search).toBeVisible()
  await expect(page.getByText("deploy added")).toBeAttached()

  // The ✓ rows are the ones on the task; choosing one takes it off.
  await expect(option(page, "errands (on it)")).toBeVisible()
  await option(page, "errands (on it)").click()
  await expect.poll(onTask).toEqual(["deploy"])
  await expect(page.getByText("errands removed")).toBeAttached()
})

test("A new name is created from its own row, and a chip removes a tag", async ({
  page,
}) => {
  const { panel, search, openPicker, onTask, vocabulary } = await openTask(page)
  await openPicker()

  await search.fill("errands")
  // An exact match offers no create row.
  await expect(option(page, /^Create tag/)).toHaveCount(0)

  await search.fill("postage")
  await expect(option(page, 'Create tag "postage"')).toBeVisible()
  // Enter chooses the create row when nothing matches exactly.
  await search.press("Enter")
  await expect.poll(onTask).toEqual(["postage"])
  expect(await vocabulary()).toEqual(["deploy", "errands", "postage"])

  await page.keyboard.press("Escape")
  await panel.getByRole("button", { name: "Remove tag postage" }).click()
  await expect.poll(onTask).toEqual([])
})

test("Enter on an exact match adds that tag", async ({ page }) => {
  const { search, openPicker, onTask, vocabulary } = await openTask(page)
  await openPicker()

  await search.fill("errands")
  await expect(option(page, /^errands/)).toHaveAttribute(
    "data-selected",
    "true",
  )
  await search.press("Enter")
  await expect.poll(onTask).toEqual(["errands"])
  expect(await vocabulary()).toEqual(["deploy", "errands"])
})

test("A near-duplicate name is steered to the tag the user already has", async ({
  page,
}) => {
  const { search, openPicker, onTask, vocabulary } = await openTask(page)
  await openPicker()

  await search.fill("Deploys")
  const group = page.getByRole("group", { name: "You already have" })
  await expect(group).toBeVisible()
  await expect(group.getByRole("option", { name: "deploy" })).toBeVisible()
  await expect(option(page, 'Create tag "Deploys"')).toBeVisible()

  await group.getByRole("option", { name: "deploy" }).click()
  // The pick keeps its own casing, and nothing new is minted.
  await expect.poll(onTask).toEqual(["deploy"])
  expect(await vocabulary()).toEqual(["deploy", "errands"])
})

test("Escape or a click outside with typed text adds nothing, and the panel stays", async ({
  page,
}) => {
  const { panel, search, openPicker, onTask, vocabulary } = await openTask(page)
  await openPicker()

  await search.fill("err")
  await page.keyboard.press("Escape")
  await expect(search).toBeHidden()
  await expect(panel).toBeVisible()

  await openPicker()
  // The query was not kept.
  await expect(search).toHaveValue("")
  await search.fill("fragment")
  await panel.getByRole("textbox", { name: "Task title" }).click()
  await expect(search).toBeHidden()

  await page.waitForTimeout(500)
  expect(await onTask()).toEqual([])
  expect(await vocabulary()).toEqual(["deploy", "errands"])
})

test("The capture shortcut stands down while the popover is open", async ({
  page,
}) => {
  const { search, openPicker } = await openTask(page)
  await openPicker()
  await search.press("c")
  await expect(search).toHaveValue("c")
  await expect(page).not.toHaveURL(/capture=/)
})

test("Bulk Add tag adds each chosen tag to every selected task", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tags/", { name: "errands" })
  const first = await api.create("/tasks/", { title: "One", tags: ["deploy"] })
  const second = await api.create("/tasks/", { title: "Two" })
  await page.goto("/tasks")

  await page
    .getByRole("checkbox", { name: "Select every task on this page" })
    .check()
  await page.getByRole("button", { name: "Add tag" }).click()
  // The tasks' own tags are not marked: they differ from task to task.
  await expect(option(page, "deploy")).toBeVisible()
  await option(page, "errands").click()
  await expect(option(page, "errands (on it)")).toBeVisible()
  await page
    .getByRole("combobox", { name: "Search or create a tag" })
    .fill("urgent")
  await option(page, 'Create tag "urgent"').click()

  const tagsOf = async (id: string) =>
    ((await (await api.get(`/tasks/${id}`)).json()).tags as string[])
      .slice()
      .sort()
  await expect
    .poll(() => tagsOf(first.id))
    .toEqual(["deploy", "errands", "urgent"])
  await expect.poll(() => tagsOf(second.id)).toEqual(["errands", "urgent"])
})

test.describe("on a phone", () => {
  test.use({
    viewport: { width: 375, height: 812 },
    hasTouch: true,
    isMobile: true,
  })

  test("The popover fits the panel and its rows are thumb-sized", async ({
    page,
  }) => {
    const { openPicker } = await openTask(page)
    await openPicker()

    // Measured once the opening animation has settled.
    const list = page.locator('[data-slot="popover-content"]')
    await expect
      .poll(async () => (await list.boundingBox())?.width)
      .toBeGreaterThan(300)
    const box = await list.boundingBox()
    expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(375)
    await expect
      .poll(async () => (await option(page, /^errands/).boundingBox())?.height)
      .toBeGreaterThanOrEqual(44)
  })
})
