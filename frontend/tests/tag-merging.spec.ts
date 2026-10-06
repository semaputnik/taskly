import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"
import { lookAlike, tagLine, tagLink } from "./utils/tags"

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

test("Folding another tag in from a tag's column moves its tasks and removes it", async ({
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
  await tagLink(page, "Deploy").click()
  const panel = page.getByRole("complementary", { name: "Deploy", exact: true })
  const startMerge = async () => {
    await expect(panel).toContainText("Fold another tag into this one:")
    await panel
      .getByRole("combobox", { name: "Choose a tag to fold in" })
      .click()
    await page.getByRole("option", { name: "deploy", exact: true }).click()
    // Choosing is the first step: the confirmation follows, with this tag
    // as the name that stays, and the reader free to pick the other.
    const start = page.getByRole("dialog", { name: "Merge into Deploy?" })
    await expect(start).toBeVisible()
    await page.getByRole("radio", { name: /^deploy 2 tasks/ }).check()
  }
  await startMerge()

  // The confirmation says what goes, what survives and how many tasks change,
  // archived ones included, before the button that does it.
  const confirm = page.getByRole("dialog", { name: "Merge into deploy?" })
  const description = confirm.locator("[data-slot=dialog-description]")
  await expect(description).toContainText("The tag “Deploy” is removed.")
  await expect(description).toContainText(
    "3 tasks change to carry “deploy” instead, 1 of them in an archived project.",
  )
  await expect(description).toContainText("can't be undone")

  // Nothing happens until it is confirmed.
  await confirm.getByRole("button", { name: "Cancel" }).click()
  expect(await vocabulary(page)).toEqual([
    ["Deploy", 2],
    ["deploy", 2],
  ])

  await startMerge()
  await confirm.getByRole("button", { name: "Merge into deploy" }).click()

  // The column moves onto the tag that now carries the tasks.
  const survivor = page.getByRole("complementary", {
    name: "deploy",
    exact: true,
  })
  await expect(survivor).toBeVisible()
  await expect(survivor).toContainText("3 open · 1 in an archived project")
  expect(await vocabulary(page)).toEqual([["deploy", 3]])

  await page.keyboard.press("Escape")
  await expect(tagLink(page, "Deploy")).toHaveCount(0)
  await tagLine(page, "deploy")
    .getByRole("link", { name: /3 open/ })
    .click()
  for (const title of ["Ship 1.2", "Ship 1.3", "Ship 1.4"]) {
    await expect(
      page.getByRole("link", { name: title, exact: true }),
    ).toBeVisible()
  }

  await page.goto("/activity")
  await expect(
    page
      .getByRole("listitem")
      .filter({ hasText: "Merged “Deploy” into deploy" }),
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

  // The reason is said under the name, which keeps what was typed.
  await expect(page.locator("[role=alert]")).toContainText(
    "You already have a tag named",
  )
  const confirm = page.getByRole("dialog", { name: "Merge into deploy?" })
  await expect(confirm).toContainText("The tag “deploys” is removed.")
  await confirm.getByRole("button", { name: "Cancel" }).click()
  await expect(name).toHaveValue("deploy")
  expect(await vocabulary(page)).toEqual([
    ["deploy", 0],
    ["deploys", 1],
  ])
  expect(tag.name).toBe("deploy")
})

test("The Tags page offers look-alike groups, and merges only on confirmation", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  for (const name of [
    "Deploy",
    "deploy",
    "deploy-bot",
    "deploy_bot",
    "deploy  bot",
    "report",
    "reports",
    "release",
  ]) {
    await api.create("/tags/", { name })
  }
  await api.create("/tasks/", { title: "Ship 1.2", tags: ["deploy", "report"] })

  await page.goto("/tags")
  const groups = page.getByRole("region", { name: "Look alike" })
  await expect(groups.getByRole("listitem")).toHaveCount(3)
  await expect(page.getByRole("main")).toContainText("8 tags. 7 look alike.")
  // Each group is one line: the names, their open counts, what can be done.
  await expect(lookAlike(page, "deploy, Deploy")).toContainText("0 and 1 tasks")
  await expect(
    lookAlike(page, "deploy bot, deploy-bot, deploy_bot"),
  ).toBeVisible()
  await expect(lookAlike(page, "report, reports")).toContainText(
    "Merge into report",
  )

  // Opening the merge is not merging: cancelling leaves every tag.
  await lookAlike(page, "report, reports")
    .getByRole("button", { name: "Merge into report" })
    .click()
  const confirm = page.getByRole("dialog", { name: "Merge into report?" })
  await expect(confirm).toContainText("The tag “reports” is removed.")
  await confirm.getByRole("button", { name: "Cancel" }).click()
  expect((await vocabulary(page)).map(([name]: [string]) => name)).toContain(
    "reports",
  )

  // Kept apart, a group is not offered again, and nothing was merged.
  await lookAlike(page, "deploy, Deploy")
    .getByRole("button", { name: "Keep apart" })
    .click()
  await expect(lookAlike(page, "deploy, Deploy")).toHaveCount(0)
  await page.reload()
  await expect(groups.getByRole("listitem")).toHaveCount(2)
  expect((await vocabulary(page)).map(([name]: [string]) => name)).toEqual(
    expect.arrayContaining(["Deploy", "deploy"]),
  )

  // Merging a group of three keeps the chosen spelling and removes the rest.
  await lookAlike(page, "deploy bot, deploy-bot, deploy_bot")
    .getByRole("button", { name: /^Merge into / })
    .click()
  const three = page.getByRole("dialog", { name: /^Merge into / })
  await three.getByRole("radio", { name: /deploy-bot/ }).check()
  await expect(three).toContainText(
    "The tags “deploy  bot” and “deploy_bot” are removed.",
  )
  await three.getByRole("button", { name: "Merge into deploy-bot" }).click()
  await expect(three).toBeHidden()
  await expect(groups.getByRole("listitem")).toHaveCount(1)
  const names = (await vocabulary(page)).map(([name]: [string]) => name)
  expect(names).toContain("deploy-bot")
  expect(names).not.toContain("deploy_bot")
  expect(names).not.toContain("deploy  bot")

  // A kept-apart group returns once one of its tags is renamed.
  await tagLink(page, "Deploy").click()
  const name = page
    .getByRole("complementary", { name: "Deploy", exact: true })
    .getByRole("textbox", { name: "Tag name" })
  await name.fill("Deploys")
  await name.press("Enter")
  await expect(page.getByRole("region", { name: "Look alike" })).toBeVisible()
  await expect(
    groups.getByRole("listitem", { name: "Look alike: deploy, Deploys" }),
  ).toBeVisible()
})

test("A tag a bot user created says which one", async ({ page }) => {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Releases" })
  const bot = await api.create("/bot-users/", {
    name: "Triage agent",
    scope: {
      project_ids: [project.id],
      permissions: { read_tasks: true, create_tags: true },
    },
  })
  const { token } = await api.create(`/bot-users/${bot.id}/token`)
  const created = await page.request.post(`${api.url}/tags/`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: "needs-triage" },
  })
  expect(created.ok()).toBe(true)
  await api.create("/tags/", { name: "mine" })

  await page.goto("/tags")
  await expect(tagLine(page, "needs-triage")).toContainText(
    "created by Triage agent",
  )
  await expect(tagLine(page, "mine")).toContainText("created by you")
  await tagLink(page, "needs-triage").click()
  await expect(
    page.getByRole("complementary", { name: "needs-triage" }),
  ).toContainText("created")
  await expect(
    page.getByRole("complementary", { name: "needs-triage" }),
  ).toContainText("by Triage agent")
})

test.describe("on a phone", () => {
  test.use({
    viewport: { width: 375, height: 812 },
    hasTouch: true,
    isMobile: true,
  })

  test("Several spellings are merged from a tag's column in one act", async ({
    page,
  }) => {
    await newUser(page)
    const api = await userApi(page)
    for (const name of ["ship", "Ship", "shipping", "ships"]) {
      await api.create("/tasks/", { title: `About ${name}`, tags: [name] })
    }
    const ship = (await (await api.get("/tags/?near=ship")).json()).data.find(
      (tag: { name: string }) => tag.name === "ship",
    )

    await page.goto(`/tags?tag_id=${ship.id}`)
    const panel = page.getByRole("complementary", { name: "ship", exact: true })
    await panel
      .getByRole("combobox", { name: "Choose a tag to fold in" })
      .click()
    await page.getByRole("option", { name: "Ship", exact: true }).click()
    const dialog = page.getByRole("dialog", { name: /^Merge / })
    for (const name of ["ships", "shipping"]) {
      await dialog.getByRole("combobox", { name: "Add a tag to merge" }).click()
      await page.getByRole("option", { name, exact: true }).click()
    }
    // One added by mistake is taken out again before confirming.
    await dialog.getByRole("button", { name: "Leave shipping out" }).click()

    await expect(dialog).toContainText(
      "The tags “Ship” and “ships” are removed. 2 tasks change to carry “ship” instead.",
    )
    await dialog.getByRole("button", { name: "Merge into ship" }).click()
    await expect(dialog).toBeHidden()
    expect(await vocabulary(page)).toEqual([
      ["ship", 3],
      ["shipping", 1],
    ])
  })
})
