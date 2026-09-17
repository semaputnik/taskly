import {
  type QueryClient,
  type QueryKey,
  queryOptions,
  useQueryClient,
} from "@tanstack/react-query"

import {
  ActivityService,
  AttachmentsService,
  BotsService,
  CommentsService,
  ProjectsService,
  type TagPublic,
  TagsService,
  TasksService,
  UsersService,
} from "@/client"

/**
 * The server state: what the app has read from the API, and what a change
 * makes stale.
 *
 * Every query key is built here and nowhere else, so two components asking
 * for the same data share one cache entry, and no key can collide with
 * another by accident. Every mutation reports the change it made in the
 * domain's words, and this module decides what that change makes stale:
 * a component never lists cache keys itself.
 */

type ReadTasksQuery = NonNullable<
  Parameters<typeof TasksService.readTasks>[0]
>["query"]
type ReadActivityQuery = NonNullable<
  Parameters<typeof ActivityService.readActivityLog>[0]
>["query"]
type ReadTagsQuery = NonNullable<
  Parameters<typeof TagsService.readTags>[0]
>["query"]

/** The first page of a list, which is all any screen asks for. */
const FIRST_PAGE = { skip: 0, limit: 100 }

// The roots of every key. Each record kind is its own root, so a change can
// make one kind stale without touching the rest.
const ROOT = {
  currentUser: "currentUser",
  users: "users",
  projects: "projects",
  project: "project",
  tasks: "tasks",
  task: "task",
  tags: "tags",
  tag: "tag",
  bots: "bots",
  bot: "bot",
  activity: "activity",
  comments: "comments",
  attachments: "attachments",
} as const

type Root = (typeof ROOT)[keyof typeof ROOT]

// Record queries

export const currentUserQuery = () =>
  queryOptions({
    queryKey: [ROOT.currentUser],
    queryFn: async () => (await UsersService.readUserMe()).data,
  })

export const usersQuery = () =>
  queryOptions({
    queryKey: [ROOT.users],
    queryFn: async () =>
      (await UsersService.readUsers({ query: FIRST_PAGE })).data,
  })

/** The user's projects: the live ones, or the archive. */
export const projectsQuery = ({ archived = false } = {}) => {
  const query = { archived, ...FIRST_PAGE }
  return queryOptions({
    queryKey: [ROOT.projects, query],
    queryFn: async () => (await ProjectsService.readProjects({ query })).data,
  })
}

export interface ScopeProject {
  id: string
  name: string
  archived: boolean
}

/**
 * Every project a bot user's scope can name: the live ones and the archived
 * ones. A deleted project is in neither list, and the API leaves it out of
 * scopes too.
 */
export const scopeProjectsQuery = () =>
  queryOptions({
    queryKey: [ROOT.projects, "bot-scope"],
    queryFn: async (): Promise<ScopeProject[]> => {
      const [live, archived] = await Promise.all(
        [false, true].map(
          async (archived) =>
            (
              await ProjectsService.readProjects({
                query: { archived, ...FIRST_PAGE },
              })
            ).data,
        ),
      )
      return [
        ...live.data.map((p) => ({ id: p.id, name: p.name, archived: false })),
        ...archived.data.map((p) => ({
          id: p.id,
          name: p.name,
          archived: true,
        })),
      ]
    },
  })

export const projectQuery = (projectId: string | null | undefined) =>
  queryOptions({
    queryKey: [ROOT.project, projectId],
    queryFn: async () =>
      (
        await ProjectsService.readProject({
          path: { project_id: projectId as string },
        })
      ).data,
    enabled: Boolean(projectId),
  })

/** The tasks a query asks for, as the key and the request both carry it. */
export const tasksQuery = (query: ReadTasksQuery = {}) =>
  queryOptions({
    queryKey: [ROOT.tasks, query],
    queryFn: async () => (await TasksService.readTasks({ query })).data,
  })

export const taskQuery = (taskId: string | null | undefined) =>
  queryOptions({
    queryKey: [ROOT.task, taskId],
    queryFn: async () =>
      (await TasksService.readTask({ path: { task_id: taskId as string } }))
        .data,
    enabled: Boolean(taskId),
  })

/** A page of the user's tags. */
export const tagsQuery = (query: ReadTagsQuery = FIRST_PAGE) =>
  queryOptions({
    queryKey: [ROOT.tags, "list", query],
    queryFn: async () => (await TagsService.readTags({ query })).data,
  })

/**
 * The tags whose names contain what the reader typed. The text sits under
 * its own segment, so no name typed into a search can make up another key.
 */
export const tagSearchQuery = (text: string) =>
  queryOptions({
    queryKey: [ROOT.tags, "search", text],
    queryFn: async () =>
      (
        await TagsService.readTags({
          query: { q: text || undefined, ...FIRST_PAGE },
        })
      ).data,
  })

/** Spellings a new tag name would read the same as. */
export const nearTagsQuery = (text: string) =>
  queryOptions({
    queryKey: [ROOT.tags, "near", text],
    queryFn: async () =>
      (await TagsService.readTags({ query: { near: text, skip: 0, limit: 5 } }))
        .data,
  })

const VOCABULARY_PAGE = 500

/**
 * Every tag the user has, however many: what picking a tag to merge with
 * offers, so no spelling is out of reach for sitting past the first page.
 */
export const tagVocabularyQuery = () =>
  queryOptions({
    queryKey: [ROOT.tags, "vocabulary"],
    queryFn: async () => {
      const tags: TagPublic[] = []
      for (let skip = 0; ; skip += VOCABULARY_PAGE) {
        const page = (
          await TagsService.readTags({
            query: { skip, limit: VOCABULARY_PAGE },
          })
        ).data
        tags.push(...page.data)
        if (page.data.length < VOCABULARY_PAGE || tags.length >= page.count) {
          return tags
        }
      }
    },
  })

/** Groups of tags whose names read as the same word (FR-01.28). */
export const tagDuplicatesQuery = () =>
  queryOptions({
    queryKey: [ROOT.tags, "duplicates"],
    queryFn: async () => (await TagsService.readTagDuplicates()).data,
  })

/** What merging `sourceIds` into `targetId` would do. */
export const tagMergePreviewQuery = (
  targetId: string | undefined,
  sourceIds: string[],
) =>
  queryOptions({
    queryKey: [ROOT.tags, "merge-preview", targetId, sourceIds],
    queryFn: async () =>
      (
        await TagsService.previewTagMerge({
          path: { tag_id: targetId as string },
          query: { source_ids: sourceIds },
        })
      ).data,
    enabled: Boolean(targetId) && sourceIds.length > 0,
  })

export const tagQuery = (tagId: string | null | undefined) =>
  queryOptions({
    queryKey: [ROOT.tag, tagId],
    queryFn: async () =>
      (await TagsService.readTag({ path: { tag_id: tagId as string } })).data,
    enabled: Boolean(tagId),
  })

export const botsQuery = () =>
  queryOptions({
    queryKey: [ROOT.bots],
    queryFn: async () =>
      (await BotsService.readBotUsers({ query: FIRST_PAGE })).data,
  })

export const botQuery = (botId: string | null | undefined) =>
  queryOptions({
    queryKey: [ROOT.bot, botId],
    queryFn: async () =>
      (
        await BotsService.readBotUser({
          path: { bot_user_id: botId as string },
        })
      ).data,
    enabled: Boolean(botId),
  })

export const activityQuery = (query: ReadActivityQuery = {}) =>
  queryOptions({
    queryKey: [ROOT.activity, query],
    queryFn: async () =>
      (await ActivityService.readActivityLog({ query })).data,
  })

export const commentsQuery = (taskId: string) =>
  queryOptions({
    queryKey: [ROOT.comments, taskId],
    queryFn: async () =>
      (await CommentsService.readComments({ path: { task_id: taskId } })).data,
  })

export const attachmentsQuery = (taskId: string) =>
  queryOptions({
    queryKey: [ROOT.attachments, taskId],
    queryFn: async () =>
      (await AttachmentsService.readAttachments({ path: { task_id: taskId } }))
        .data,
  })

// Changes

/** Something the reader did that the server now knows, in the domain's words. */
export type Change =
  /** A task's fields, status, assignee or project changed. */
  | { type: "task changed"; taskId: string }
  | { type: "task created" }
  | { type: "task deleted"; taskId: string }
  /** A batch changed or deleted a selection of tasks. */
  | { type: "tasks changed in bulk" }
  | { type: "tag created" }
  /** A tag was renamed, merged or deleted. */
  | { type: "tag changed" }
  /** A group of near-duplicate tags was kept apart. */
  | { type: "tag duplicates dismissed" }
  | { type: "project created" }
  /** A project was edited, archived, unarchived or deleted. */
  | { type: "project changed"; projectId: string }
  /** A bot user was created, renamed, rescoped or deleted. */
  | { type: "bot user changed"; botId?: string }
  | { type: "bot token changed"; botId?: string }
  | { type: "deletion restored" }
  | { type: "comments changed"; taskId: string }
  | { type: "attachments changed"; taskId: string }
  /** The signed-in account itself changed: everything read may be stale. */
  | { type: "account changed" }
  | { type: "users changed" }

// What each change makes stale. A root on its own stands for every key under
// it. Task counts ride on projects and tags, and every change is logged, so
// most changes reach both of those and the activity log.
const COUNTS: Root[] = [ROOT.projects, ROOT.project, ROOT.tags, ROOT.tag]

/** The query keys a change makes stale, as prefixes of the keys they cover. */
export function staleKeys(change: Change): QueryKey[] {
  const roots = (...roots: Root[]): QueryKey[] => roots.map((root) => [root])
  switch (change.type) {
    case "task changed":
    case "task deleted":
      return [
        ...roots(ROOT.tasks, ROOT.activity, ...COUNTS),
        [ROOT.task, change.taskId],
      ]
    case "task created":
      return roots(ROOT.tasks, ROOT.activity, ...COUNTS)
    case "tasks changed in bulk":
    case "deletion restored":
      return roots(ROOT.tasks, ROOT.task, ROOT.activity, ...COUNTS)
    case "tag created":
      return roots(ROOT.tags, ROOT.activity)
    case "tag changed":
      // A tag's name shows on every task carrying it (FR-01.24).
      return roots(ROOT.tags, ROOT.tag, ROOT.tasks, ROOT.task, ROOT.activity)
    case "tag duplicates dismissed":
      return [tagDuplicatesQuery().queryKey]
    case "project created":
      return roots(ROOT.projects, ROOT.activity)
    case "project changed":
      // Archiving a project freezes every task in it (FR-05.11).
      return [
        ...roots(ROOT.projects, ROOT.tasks, ROOT.task, ROOT.activity),
        [ROOT.project, change.projectId],
      ]
    case "bot user changed":
      // A bot user is named on the tasks assigned to it and in the log.
      return [
        ...roots(ROOT.bots, ROOT.tasks, ROOT.task, ROOT.activity),
        change.botId ? [ROOT.bot, change.botId] : [ROOT.bot],
      ]
    case "bot token changed":
      return [[ROOT.bots], change.botId ? [ROOT.bot, change.botId] : [ROOT.bot]]
    case "comments changed":
      return [[ROOT.comments, change.taskId], [ROOT.activity]]
    case "attachments changed":
      return [[ROOT.attachments, change.taskId], [ROOT.activity]]
    case "account changed":
      return [[]]
    case "users changed":
      return [[ROOT.users]]
  }
}

/** Mark everything a change makes stale, refetching what is on screen. */
export function reportChange(
  queryClient: QueryClient,
  change: Change,
): Promise<void> {
  return Promise.all(
    staleKeys(change).map((queryKey) =>
      queryClient.invalidateQueries({ queryKey }),
    ),
  ).then(() => undefined)
}

/** `reportChange`, bound to the app's query client. */
export function useReportChange() {
  const queryClient = useQueryClient()
  return (change: Change) => reportChange(queryClient, change)
}

/**
 * Forget everything read: what one account read must never be shown to the
 * next one to sign in in the same tab.
 */
export function clearServerState(queryClient: QueryClient) {
  queryClient.clear()
}

/** How long each kind of data may be served from the cache. */
export function configureServerState(queryClient: QueryClient) {
  // The signed-in account changes only through its own settings, which
  // report it, so every screen that mounts does not have to ask again. The
  // project list is shorter-lived: its task counts move when a bot user
  // files work. A few seconds still spare the burst of requests a panel or a
  // screen makes as its parts mount one after another.
  queryClient.setQueryDefaults([ROOT.currentUser], {
    staleTime: 5 * 60 * 1000,
  })
  queryClient.setQueryDefaults([ROOT.projects], { staleTime: 10 * 1000 })
}
