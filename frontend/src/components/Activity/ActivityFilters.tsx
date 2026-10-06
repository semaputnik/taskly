import { useQuery } from "@tanstack/react-query"
import { ChevronDown } from "lucide-react"
import { useState } from "react"

import type { ActivityKind } from "@/client"
import {
  ChoiceFilter,
  control,
  PickSheet,
  SheetOption,
} from "@/components/Common/FilterRow"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Sheet, SheetTrigger } from "@/components/ui/sheet"
import { useIsPhone } from "@/hooks/useIsPhone"
import { botQuery, botsQuery, deletedBotsQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"
import type { ActivitySearch } from "./queries"
import { KIND_LABELS, KINDS, type LogOrder, ME, ORDER_LABELS } from "./words"

const ORDERS = Object.keys(ORDER_LABELS) as LogOrder[]

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
  const phone = useIsPhone()
  const [sheetOpen, setSheetOpen] = useState(false)
  const label = ORDER_LABELS[order]
  const button = (
    <button
      type="button"
      aria-label={`Order: ${label}`}
      className={cn(control, "-mr-1.5")}
    >
      {label}
      <ChevronDown aria-hidden className="size-2.5 opacity-70" />
    </button>
  )
  if (phone) {
    return (
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetTrigger asChild>{button}</SheetTrigger>
        <PickSheet title="Order" description="Choose how the log is ordered.">
          {ORDERS.map((value) => (
            <SheetOption
              key={value}
              selected={value === order}
              onClick={() => {
                onOrder(value)
                setSheetOpen(false)
              }}
            >
              {ORDER_LABELS[value]}
            </SheetOption>
          ))}
        </PickSheet>
      </Sheet>
    )
  }
  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>{button}</DropdownMenuTrigger>
      <DropdownMenuContent align="end" aria-label="Order">
        <DropdownMenuRadioGroup
          value={order}
          onValueChange={(next) => onOrder(next as LogOrder)}
        >
          {ORDERS.map((value) => (
            <DropdownMenuRadioItem key={value} value={value}>
              {ORDER_LABELS[value]}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
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

  const filtered = Boolean(search.kind || search.actor)

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
        {filtered && (
          <button
            type="button"
            aria-label="Clear all filters"
            onClick={() => onChange({ kind: undefined, actor: undefined })}
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
