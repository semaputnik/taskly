import { Check, ChevronDown, X } from "lucide-react"
import { type ReactNode, useState } from "react"

import { navItemFocus } from "@/components/Sidebar/styles"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { useIsPhone } from "@/hooks/useIsPhone"
import { cn } from "@/lib/utils"

/**
 * The pieces of a filter row, shared by every page that has one: the task
 * list and the activity log. Quiet text buttons that open a menu (a bottom
 * sheet on a phone), the value in ink with an × when set.
 */

// A radio group cannot hold an empty value, so "no filter" needs a name of
// its own. Everything offered here is an id or a fixed keyword, never free
// text, so nothing a user types can collide with it.
export const ANY = "any"

/**
 * One text button on the row, quiet until it is set: ink, a weight up, and an
 * × beside it that drops the filter. A button's focus is the navigation's
 * own: a 2px ink outline clear of it.
 */
export const control = cn(
  navItemFocus,
  "text-ink-3 hover:bg-hover hover:text-ink data-[state=open]:bg-hover data-[state=open]:text-ink inline-flex h-7 pointer-coarse:h-11 items-center gap-[5px] rounded-md px-1.5 whitespace-nowrap transition-colors",
)

export interface Choice {
  value: string
  label: string
  /** Drawn in the menu in place of the label, where the label needs a mark. */
  display?: ReactNode
}

/**
 * A filter as it sits on the row: its text, and when it is set the value in
 * place of "Any …" with the × that drops it. The two are separate buttons in
 * one pill, so the hover fill reads as one control.
 */
export function Filter({
  noun,
  anyLabel,
  value,
  onRemove,
  menu,
}: {
  /** What is filtered, for the button's name: "Project". */
  noun: string
  anyLabel: string
  /** What the filter is set to, in the reader's words; none when it is not. */
  value: string | undefined
  onRemove: () => void
  /** Wraps the button in what it opens. */
  menu: (button: ReactNode) => ReactNode
}) {
  // An empty value in a hand-edited URL is set but narrows nothing, so it is
  // not drawn as a filter.
  const set = Boolean(value)
  const button = (
    <button
      type="button"
      aria-label={set ? `${noun}: ${value}` : undefined}
      className={cn(
        control,
        set && "text-ink font-medium",
        // The pill is the hover target when there is an × beside the text.
        set && "hover:bg-transparent data-[state=open]:bg-transparent",
      )}
    >
      {set ? value : anyLabel}
      {!set && <ChevronDown aria-hidden className="size-2.5 opacity-70" />}
    </button>
  )
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md",
        set && "hover:bg-hover pr-1",
      )}
    >
      {menu(button)}
      {set && (
        <button
          type="button"
          aria-label={`Remove the ${noun.toLowerCase()} filter`}
          onClick={onRemove}
          className={cn(
            navItemFocus,
            // A finger needs more than 14px: the hit area grows past the mark
            // without moving anything.
            "text-ink-3 hover:bg-rule hover:text-ink relative grid size-3.5 place-items-center rounded-full transition-colors pointer-coarse:after:absolute pointer-coarse:after:-inset-3.5",
          )}
        >
          <X aria-hidden className="size-2.5" strokeWidth={2} />
        </button>
      )}
    </span>
  )
}

/**
 * A menu on a phone: a sheet that rises from the bottom, where a thumb is,
 * with rows 44px tall. The trigger is whatever button the caller wraps in
 * `SheetTrigger`; this is the sheet it opens.
 */
export function PickSheet({
  title,
  description,
  children,
  done,
}: {
  title: string
  description: string
  children: ReactNode
  /** A closing button at the foot, for a sheet that is used more than once. */
  done?: boolean
}) {
  return (
    <SheetContent
      side="bottom"
      className="bg-page max-h-[85svh] gap-0 rounded-t-xl pb-[env(safe-area-inset-bottom)] shadow-none"
    >
      <SheetHeader className="px-4 pt-4 pb-1">
        <SheetTitle className="text-[15px]">{title}</SheetTitle>
        <SheetDescription className="sr-only">{description}</SheetDescription>
      </SheetHeader>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain pb-2">
        {children}
      </div>
      {done && (
        <div className="border-rule border-t px-4 py-2">
          <SheetClose className="bg-ink text-page h-11 w-full rounded-md text-[15px] font-medium">
            Done
          </SheetClose>
        </div>
      )}
    </SheetContent>
  )
}

/** One row of a sheet: 44px, the chosen one in ink with a check. */
export function SheetOption({
  selected,
  onClick,
  children,
}: {
  selected: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={cn(
        "hover:bg-hover flex min-h-11 w-full items-center gap-3 px-4 text-left text-[15px]",
        selected ? "text-ink font-medium" : "text-ink-2",
      )}
    >
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {selected && <Check aria-hidden className="size-4 shrink-0" />}
    </button>
  )
}

/** The choices of one filter as sheet rows, "any" first. */
export function ChoiceOptions({
  anyLabel,
  value,
  selected,
  choices,
  onChange,
}: {
  anyLabel: string
  value: string | undefined
  selected: string | undefined
  choices: Choice[]
  onChange: (value: string | undefined) => void
}) {
  const marked = selected ?? (value ? "" : ANY)
  return (
    <>
      <SheetOption
        selected={marked === ANY}
        onClick={() => onChange(undefined)}
      >
        {anyLabel}
      </SheetOption>
      {choices.map((choice) => (
        <SheetOption
          key={choice.value}
          selected={marked === choice.value}
          onClick={() => onChange(choice.value)}
        >
          {choice.display ?? choice.label}
        </SheetOption>
      ))}
    </>
  )
}

/** A filter that is one choice among a list: a menu of radio items. */
export function ChoiceFilter({
  noun,
  anyLabel,
  value,
  selected,
  choices,
  onChange,
}: {
  noun: string
  anyLabel: string
  /** The set filter in the reader's words; none when the filter is not set. */
  value: string | undefined
  /** The value of the choice to mark, which is none for an odd URL's set. */
  selected: string | undefined
  choices: Choice[]
  /** The chosen value, or undefined for "any". */
  onChange: (value: string | undefined) => void
}) {
  const phone = useIsPhone()
  const [sheetOpen, setSheetOpen] = useState(false)
  return (
    <Filter
      noun={noun}
      anyLabel={anyLabel}
      value={value}
      onRemove={() => onChange(undefined)}
      menu={(button) =>
        phone ? (
          // A phone's menu is a sheet; choosing a row closes it.
          <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
            <SheetTrigger asChild>{button}</SheetTrigger>
            <PickSheet title={noun} description="Choose what to filter by.">
              <ChoiceOptions
                anyLabel={anyLabel}
                value={value}
                selected={selected}
                choices={choices}
                onChange={(next) => {
                  onChange(next)
                  setSheetOpen(false)
                }}
              />
            </PickSheet>
          </Sheet>
        ) : (
          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>{button}</DropdownMenuTrigger>
            <DropdownMenuContent align="start" aria-label={noun}>
              <DropdownMenuRadioGroup
                value={selected ?? (value ? "" : ANY)}
                onValueChange={(next) =>
                  onChange(next === ANY ? undefined : next)
                }
              >
                <DropdownMenuRadioItem value={ANY}>
                  {anyLabel}
                </DropdownMenuRadioItem>
                {choices.map((choice) => (
                  <DropdownMenuRadioItem
                    key={choice.value}
                    value={choice.value}
                  >
                    {choice.display ?? choice.label}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        )
      }
    />
  )
}

/** One order the menu offers. `reverses` is set on the one in force when choosing it again turns it around. */
export interface OrderChoice {
  key: string
  label: string
  reverses?: boolean
}

/**
 * The order menu at the row's right: a quiet button saying the order in
 * force, over a radio menu on a wide screen and a bottom sheet on a phone.
 * Choosing acts on selection, not on the group's change, so choosing the one
 * in force again still reaches the page (the task list reverses it).
 */
export function OrderMenu({
  label,
  description,
  choices,
  selected,
  onChoose,
}: {
  /** The order in force, in words. */
  label: string
  /** What the phone sheet says it is for ("Choose how the list is ordered."). */
  description: string
  choices: OrderChoice[]
  selected: string
  onChoose: (key: string) => void
}) {
  const phone = useIsPhone()
  const [sheetOpen, setSheetOpen] = useState(false)
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
        <PickSheet title="Order" description={description}>
          {choices.map(({ key, label: name, reverses }) => (
            <SheetOption
              key={key}
              selected={key === selected}
              onClick={() => {
                onChoose(key)
                setSheetOpen(false)
              }}
            >
              {name}
              {reverses && (
                <span className="text-ink-3 ml-3 text-xs font-normal">
                  Choose again to reverse
                </span>
              )}
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
        <DropdownMenuRadioGroup value={selected}>
          {choices.map(({ key, label: name, reverses }) => (
            <DropdownMenuRadioItem
              key={key}
              value={key}
              onSelect={() => onChoose(key)}
              className="gap-6"
            >
              {name}
              {reverses && (
                <span className="text-ink-3 ml-auto text-xs">
                  Choose again to reverse
                </span>
              )}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
