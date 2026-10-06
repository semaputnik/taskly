import { useMutation, useQuery } from "@tanstack/react-query"
import { useState } from "react"

import { type BotPermissions, BotsService } from "@/client"
import { DayField } from "@/components/Common/DayField"
import { useCaptureFocus, useRecordPanels } from "@/components/Records/panels"
import {
  ghost,
  gutter,
  PropertyList,
  PropertyRow,
  titleFieldClass,
} from "@/components/Records/RecordPanel"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { scopeProjectsQuery, useReportChange } from "@/lib/serverState"
import { toastError } from "@/lib/toasts"
import { cn } from "@/lib/utils"
import { BotPlate } from "./BotLine"
import { useShowIssuedToken } from "./IssuedToken"
import { NO_PERMISSIONS } from "./permissions"
import { PermissionsSection, ProjectsSection } from "./ScopeSections"
import { expiryFromDate, today } from "./tokens"

/**
 * A bot user that does not exist yet, in the column it will be read in: its
 * name, the projects it reaches and what it may do there, all editable from
 * the first frame, in the order of the record's own sections.
 *
 * Nothing is written while the draft is filled in. There is one visible
 * commit — Create, or Enter in the name — and it makes the bot user with that
 * scope and issues its token in the same step, so the reader leaves with a
 * working credential. The token is shown once, over the column, by the page's
 * own reveal; should issuing fail, the bot user is there all the same and its
 * column offers to issue again.
 */
export function NewBotUser() {
  const panels = useRecordPanels()
  const showIssuedToken = useShowIssuedToken()
  const reportChange = useReportChange()
  const nameRef = useCaptureFocus<HTMLInputElement>()
  const { data: projects } = useQuery(scopeProjectsQuery())

  const [name, setName] = useState("")
  const [projectIds, setProjectIds] = useState<string[]>([])
  // Reading tasks is what nearly every bot user is for, so the draft starts
  // with it ticked and the reader takes it away.
  const [permissions, setPermissions] = useState<BotPermissions>({
    ...NO_PERMISSIONS,
    read_tasks: true,
  })
  const [expiresOn, setExpiresOn] = useState("")
  const [announcement, setAnnouncement] = useState("")

  const mutation = useMutation({
    mutationFn: async () => {
      const { data: bot } = await BotsService.createBotUser({
        body: {
          name: name.trim(),
          scope: { project_ids: projectIds, permissions },
        },
      })
      try {
        const { data: issued } = await BotsService.issueBotUserToken({
          path: { bot_user_id: bot.id },
          body: { expires_at: expiryFromDate(expiresOn) ?? null },
        })
        return { bot, issued, issueError: null }
      } catch (error) {
        return { bot, issued: null, issueError: error as Error }
      }
    },
    onSuccess: ({ bot, issued, issueError }) => {
      setAnnouncement("Bot user created")
      if (issued) {
        showIssuedToken({
          botName: bot.name,
          token: issued.token,
          expiresAt: issued.expires_at,
        })
      } else if (issueError) {
        toastError(issueError)
      }
      panels.openBot(bot.id)
    },
    onError: (error) => toastError(error),
    onSettled: () => reportChange({ type: "bot user changed" }),
  })

  const ready = name.trim() !== ""
  const create = () => {
    if (ready && !mutation.isPending) mutation.mutate()
  }

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <div
        className={cn(
          "grid grid-cols-[28px_minmax(0,1fr)] items-center gap-3 pt-2 pb-[18px]",
          gutter,
        )}
      >
        <BotPlate
          name={name || "Bot"}
          off={!ready}
          className="size-7 text-xs"
        />
        <Input
          ref={nameRef}
          aria-label="Bot name"
          placeholder="Name the bot user"
          value={name}
          onChange={(event) => setName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.nativeEvent.isComposing) {
              event.preventDefault()
              create()
            }
          }}
          className={cn(
            ghost,
            titleFieldClass,
            "-ml-2 border-transparent bg-transparent shadow-none dark:bg-transparent",
          )}
        />
      </div>

      <PropertyList>
        <PropertyRow label="Token" htmlFor="new-bot-expires">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <DayField
              id="new-bot-expires"
              label="Expires on"
              min={today()}
              value={expiresOn || null}
              onChange={(day) => setExpiresOn(day ?? "")}
              className="-ml-[9px] h-[30px] border-transparent px-2 text-[15px]"
            />
            <span
              id="new-bot-expires-hint"
              className="text-ink-3 text-[12.5px] text-pretty"
            >
              Expires on this day (optional). Left empty, it works until you
              revoke it.
            </span>
          </div>
        </PropertyRow>
      </PropertyList>

      <ProjectsSection
        idPrefix="new-bot"
        projects={projects ?? []}
        selected={projectIds}
        onToggle={(projectId, granted) =>
          setProjectIds((current) =>
            granted
              ? [...current, projectId]
              : current.filter((id) => id !== projectId),
          )
        }
      />
      <PermissionsSection
        idPrefix="new-bot"
        permissions={permissions}
        onToggle={(key, granted) =>
          setPermissions((current) => ({ ...current, [key]: granted }))
        }
      />

      {/* The one commit, pinned where a thumb reaches it. */}
      <div
        className={cn(
          "bg-page border-rule-strong sticky bottom-0 mt-auto flex items-center justify-end gap-3 border-t py-3",
          gutter,
        )}
      >
        <span className="text-ink-3 text-xs">
          Its token is shown once, right after.
        </span>
        <LoadingButton
          disabled={!ready}
          loading={mutation.isPending}
          onClick={create}
          className="pointer-coarse:h-11"
        >
          Create and issue token
        </LoadingButton>
      </div>

      <output aria-live="polite" className="sr-only">
        {announcement}
      </output>
    </div>
  )
}
