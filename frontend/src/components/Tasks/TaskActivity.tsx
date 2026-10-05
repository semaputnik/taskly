import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { useState } from "react"

import { CommentsService, type TaskPublic } from "@/client"
import { ActorLabel } from "@/components/Activity/ActorLabel"
import { recordLink } from "@/components/Records/panels"
import { RecordSection } from "@/components/Records/RecordPanel"
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth from "@/hooks/useAuth"
import { formatTimeOf } from "@/lib/dates"
import {
  commentsQuery,
  taskActivityQuery,
  useReportChange,
} from "@/lib/serverState"
import { toastError } from "@/lib/toasts"
import { cn } from "@/lib/utils"
import { chronology, type Day, type Moment } from "./chronology"
import { useCommentDeletion } from "./commentDeletion"
import { useCommentDraft } from "./commentDraft"

interface TaskActivityProps {
  task: TaskPublic
}

/**
 * A text action: quiet ink that darkens and underlines on hover, and grows to
 * a thumb on touch, where it also stays in view.
 */
const textAction =
  "text-ink-3 hover:text-ink focus-visible:ring-ring/50 rounded-sm underline-offset-4 outline-none hover:underline focus-visible:ring-[3px] pointer-coarse:min-h-11 pointer-coarse:min-w-11 disabled:opacity-50"

const isMac =
  typeof navigator !== "undefined" &&
  /Mac|iPhone|iPad/.test(navigator.userAgent)

/**
 * The task's own history, oldest first: what happened to it as muted lines
 * that name who did it, and the comments as what was said, by whom, in one
 * chronology (FR-03.1, FR-10.3). The composer closes the section, so what you
 * write lands where you are reading.
 *
 * The log arrives a page at a time, newest first, and the section goes back
 * for earlier pages when asked. A bot user's comment has no Edit or Delete,
 * for anyone (FR-03.2, FR-08.10).
 */
export const TaskActivity = ({ task }: TaskActivityProps) => {
  const events = useInfiniteQuery(taskActivityQuery(task.id))
  const thread = useQuery(commentsQuery(task.id))
  const deletion = useCommentDeletion(task.id)

  const entries = events.data?.pages.flatMap((page) => page.data) ?? []
  const comments = (thread.data?.data ?? []).filter(
    (comment) => !deletion.isHidden(comment),
  )
  const days = chronology(entries, comments)
  const moments = days.reduce((n, day) => n + day.moments.length, 0)
  const pending = events.isPending || thread.isPending

  return (
    <RecordSection title="Activity" count={pending ? undefined : moments}>
      {pending ? (
        <p className="text-ink-3 py-2.5 text-sm">Loading…</p>
      ) : (
        <>
          {events.isError && (
            <p role="alert" className="text-ink-3 py-2.5 text-sm">
              The history could not be loaded.{" "}
              <button
                type="button"
                className={textAction}
                onClick={() => void events.refetch()}
              >
                Try again
              </button>
            </p>
          )}
          {events.hasNextPage && (
            <button
              type="button"
              className={cn(textAction, "py-2.5 text-[13px]")}
              disabled={events.isFetchingNextPage}
              onClick={() => void events.fetchNextPage()}
            >
              Show earlier activity
            </button>
          )}
          {days.length > 0 ? (
            <ol className="m-0 list-none p-0">
              {days.map((day) => (
                <DayOfMoments key={day.heading} day={day} task={task} />
              ))}
            </ol>
          ) : (
            !events.isError && (
              <p className="text-ink-3 py-2.5 text-sm">
                Nothing has happened to this task yet.
              </p>
            )
          )}
        </>
      )}
      <Composer task={task} />
    </RecordSection>
  )
}

function DayOfMoments({ day, task }: { day: Day; task: TaskPublic }) {
  return (
    <>
      <li className="text-ink-3 pt-2.5 text-[12.5px]">{day.heading}</li>
      {day.moments.map((moment) => (
        <li
          key={`${moment.kind}-${moment.id}`}
          className="border-rule group grid grid-cols-[4.25rem_1fr] items-baseline gap-x-3 border-b py-[9px]"
        >
          <time
            dateTime={moment.at}
            className="text-ink-3 font-mono text-xs whitespace-nowrap tabular-nums"
          >
            {formatTimeOf(moment.at)}
          </time>
          {moment.kind === "event" ? (
            <Event moment={moment} />
          ) : (
            <CommentLine moment={moment} task={task} />
          )}
        </li>
      ))}
    </>
  )
}

/** What happened, as a muted line that starts with who did it. */
function Event({ moment }: { moment: Extract<Moment, { kind: "event" }> }) {
  const { user } = useAuth()
  return (
    <div className="text-ink-3 min-w-0 text-[13.5px] text-pretty">
      <span className="text-ink-2 font-medium">
        <ActorLabel
          entry={moment.entry}
          currentUserId={user?.id}
          showBadge={false}
          showIcon={false}
        />
      </span>{" "}
      {moment.text}
    </div>
  )
}

/** What was said, by whom; the reader's own comments can be edited or deleted. */
function CommentLine({
  moment,
  task,
}: {
  moment: Extract<Moment, { kind: "comment" }>
  task: TaskPublic
}) {
  const { comment } = moment
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState("")
  const reportChange = useReportChange()
  const deletion = useCommentDeletion(task.id)
  const bot = comment.author_bot_user

  const save = useMutation({
    mutationFn: (body: string) =>
      CommentsService.updateComment({
        path: { comment_id: comment.id },
        body: { body },
      }),
    onSuccess: () => setEditing(false),
    onError: (error) => toastError(error),
    onSettled: () =>
      reportChange({ type: "comments changed", taskId: task.id }),
  })

  const startEditing = () => {
    setDraft(comment.body)
    setEditing(true)
  }

  return (
    <div className="min-w-0">
      <div className="flex items-baseline gap-2 font-medium">
        {bot ? (
          <>
            <Link
              {...recordLink("bot", bot.id)}
              className="underline-offset-4 hover:underline"
            >
              {bot.name}
            </Link>
            <small className="text-ink-3 text-xs font-normal">
              {bot.deleted ? "deleted bot user" : "bot user"}
            </small>
          </>
        ) : (
          <span className="text-ink-3">You</span>
        )}
      </div>

      {editing ? (
        <div className="mt-1 flex flex-col gap-1">
          <textarea
            aria-label="Edit comment"
            // The reader asked to edit this, so the caret belongs in it.
            // biome-ignore lint/a11y/noAutofocus: focus follows the Edit action
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setEditing(false)
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                if (draft.trim()) save.mutate(draft.trim())
              }
            }}
            className="border-rule-strong focus-visible:border-ring focus-visible:ring-ring/50 field-sizing-content min-h-11 w-full resize-none rounded-md border bg-transparent px-2 py-1.5 text-[15px] leading-normal outline-none focus-visible:ring-[3px]"
          />
          <div className="flex gap-3 text-[12.5px]">
            <LoadingButton
              variant="ghost"
              size="sm"
              loading={save.isPending}
              disabled={!draft.trim()}
              className="text-ink h-auto px-0 font-medium pointer-coarse:min-h-11"
              onClick={() => save.mutate(draft.trim())}
            >
              Save
            </LoadingButton>
            <button
              type="button"
              className={textAction}
              onClick={() => setEditing(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <>
          <p className="text-ink-2 mt-[3px] leading-normal break-words whitespace-pre-wrap">
            {comment.body}
          </p>
          {!bot && (
            // Edit and Delete show where the reader is looking: on hover or
            // focus, and always under a thumb, which has no hover.
            <div className="mt-1 flex gap-3 text-[12.5px] opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 pointer-coarse:opacity-100">
              <button
                type="button"
                aria-label="Edit comment"
                className={textAction}
                onClick={startEditing}
              >
                Edit
              </button>
              <button
                type="button"
                aria-label="Delete comment"
                className={textAction}
                onClick={() => deletion.remove(comment)}
              >
                Delete
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

/**
 * The comment being written, at the end of the history. Frameless, so it
 * reads as the next line rather than a form; ⌘ or Ctrl with Enter posts it.
 * The draft is kept per task, so closing the panel does not lose it.
 */
function Composer({ task }: { task: TaskPublic }) {
  const draft = useCommentDraft(task.id)
  const reportChange = useReportChange()

  const add = useMutation({
    mutationFn: (body: string) =>
      CommentsService.createComment({
        path: { task_id: task.id },
        body: { body },
      }),
    onSuccess: () => draft.clear(),
    onError: (error) => toastError(error),
    onSettled: () =>
      reportChange({ type: "comments changed", taskId: task.id }),
  })

  const post = () => {
    if (draft.text.trim() && !add.isPending) add.mutate(draft.text.trim())
  }

  return (
    <div className="border-rule-strong focus-within:border-ring mt-3.5 border-t pt-2.5">
      <textarea
        aria-label="New comment"
        placeholder="Write a comment…"
        {...draft.field}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault()
            post()
          }
        }}
        className="placeholder:text-ink-3 field-sizing-content min-h-11 w-full resize-none bg-transparent py-1.5 text-[15px] leading-normal outline-none"
      />
      <div className="text-ink-3 flex items-center gap-3.5 text-[13px]">
        <span className="pointer-coarse:hidden">
          <kbd className="border-rule-strong rounded-sm border px-[5px] font-mono text-[11px]">
            {isMac ? "⌘ Enter" : "Ctrl Enter"}
          </kbd>{" "}
          to post
        </span>
        <LoadingButton
          variant="ghost"
          loading={add.isPending}
          disabled={!draft.text.trim()}
          className="text-ink ml-auto h-auto px-0 font-medium hover:bg-transparent hover:underline pointer-coarse:min-h-11"
          onClick={post}
        >
          Comment
        </LoadingButton>
      </div>
    </div>
  )
}

export default TaskActivity
