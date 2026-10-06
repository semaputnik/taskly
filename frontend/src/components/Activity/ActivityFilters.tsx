import { useQuery } from "@tanstack/react-query"

import type { ActivityKind } from "@/client"
import {
  ChoiceFilter,
  OrderMenu as CommonOrderMenu,
  control,
} from "@/components/Common/FilterRow"
import {
  botQuery,
  botsQuery,
  deletedBotsQuery,
  scopeProjectsQuery,
} from "@/lib/serverState"
import { cn } from "@/lib/utils"
import type { ActivitySearch } from "./queries"
import {
  KIND_LABELS,
  KINDS,
  type LogOrder,
  ME,
  ORDER_LABELS,
  ORDERS,
} from "./words"

/**
 * The order menu, at the row's right: newest or oldest first. The log reads
 * newest first, so that is what the button says until the reader turns it
 * around (FR-10.10).
 */
function OrderMenu({
  order,
  onOrder,
}: {
  order: LogOrder
  onOrder: (order: LogOrder) => void
}) {
  return (
    <CommonOrderMenu
      label={ORDER_LABELS[order]}
      description="Choose how the log is ordered."
      selected={order}
      choices={ORDERS.map((value) => ({
        key: value,
        label: ORDER_LABELS[value],
      }))}
      onChoose={(key) => onOrder(key as LogOrder)}
    />
  )
}

/**
 * The row of filters over the log, and the order menu at its end: the kind of
 * change and who made it, as quiet text buttons like the task list's. A set
 * one is said in ink in place of its "Anything …", with an × to drop it, and
 * "Clear" drops both and leaves the order alone. The bot users offered are
 * the live ones and the deleted ones: what a deleted bot user did stays
 * readable (FR-08.19).
 */
export function ActivityFilters({
  search,
  onChange,
  onOrder,
}: {
  search: ActivitySearch
  onChange: (next: Partial<ActivitySearch>) => void
  onOrder: (order: LogOrder) => void
}) {
  const { data: bots } = useQuery(botsQuery())
  const { data: deleted } = useQuery(deletedBotsQuery())
  const { actor } = search
  // Named from the bot user itself when the lists do not have it: a filter
  // that matches nothing still has to say whose nothing it is.
  const known = [...(bots?.data ?? []), ...(deleted?.data ?? [])]
  const { data: single } = useQuery({
    ...botQuery(actor),
    enabled:
      Boolean(actor && actor !== ME) && !known.some((b) => b.id === actor),
  })
  const actorName =
    actor === ME
      ? "By you"
      : actor
        ? `By ${known.find((b) => b.id === actor)?.name ?? single?.name ?? "a bot user"}`
        : undefined

  // Live and archived projects alike: a project's chronology reads after it
  // is archived too.
  const { data: projects } = useQuery(scopeProjectsQuery())
  const projectName = search.project_id
    ? (projects?.find((project) => project.id === search.project_id)?.name ??
      "A project")
    : undefined

  const filtered = Boolean(search.kind || search.actor || search.project_id)

  return (
    <fieldset className="border-rule-strong text-ink-3 m-0 min-w-0 border-0 border-b p-0 pb-2.5 text-[13.5px]">
      <legend className="sr-only">Filters</legend>
      <div className="-ml-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
        <ChoiceFilter
          noun="Kind of change"
          anyLabel="Anything that happened"
          value={search.kind && KIND_LABELS[search.kind]}
          selected={search.kind}
          choices={KINDS.map((value) => ({
            value,
            label: KIND_LABELS[value],
          }))}
          onChange={(kind) => onChange({ kind: kind as ActivityKind })}
        />
        <ChoiceFilter
          noun="Actor"
          anyLabel="By anyone"
          value={actorName}
          selected={actor}
          choices={[
            { value: ME, label: "You" },
            ...(bots?.data ?? []).map((bot) => ({
              value: bot.id,
              label: bot.name,
            })),
            ...(deleted?.data ?? []).map((bot) => ({
              value: bot.id,
              label: `${bot.name} (deleted)`,
              display: (
                <>
                  {bot.name} <span className="text-ink-3">deleted</span>
                </>
              ),
            })),
          ]}
          onChange={(next) => onChange({ actor: next })}
        />
        <ChoiceFilter
          noun="Project"
          anyLabel="In any project"
          value={projectName && `In ${projectName}`}
          selected={search.project_id}
          choices={(projects ?? []).map((project) => ({
            value: project.id,
            label: project.archived
              ? `${project.name} (archived)`
              : project.name,
          }))}
          onChange={(project_id) => onChange({ project_id })}
        />
        {filtered && (
          <button
            type="button"
            aria-label="Clear all filters"
            onClick={() =>
              onChange({
                kind: undefined,
                actor: undefined,
                project_id: undefined,
              })
            }
            className={cn(control, "-ml-1")}
          >
            Clear
          </button>
        )}
        <div className="ml-auto">
          <OrderMenu order={search.order ?? "newest"} onOrder={onOrder} />
        </div>
      </div>
    </fieldset>
  )
}
