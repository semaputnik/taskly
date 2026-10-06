import { textLink } from "@/components/Dashboard/shared"
import { PropertyRow } from "@/components/Records/RecordPanel"
import { type Theme, useTheme } from "@/components/theme-provider"
import { cn } from "@/lib/utils"

const THEMES: { value: Theme; label: string; testId?: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light", testId: "light-mode" },
  { value: "dark", label: "Dark", testId: "dark-mode" },
]

/**
 * How Taskly looks: System, Light or Dark, the chosen one by weight alone
 * (DESIGN.md: nothing but weight marks the current one). A radio group, so a
 * screen reader hears the three as one choice and the arrow keys walk them.
 */
export function Appearance() {
  const { theme, setTheme } = useTheme()

  return (
    <PropertyRow label="Appearance">
      <div
        role="radiogroup"
        aria-label="Appearance"
        className="flex gap-3.5 text-sm"
      >
        {THEMES.map(({ value, label, testId }) => {
          const on = theme === value
          return (
            // biome-ignore lint/a11y/useSemanticElements: a styled text choice, not a native radio
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={on}
              data-testid={testId}
              tabIndex={on ? 0 : -1}
              onClick={() => setTheme(value)}
              onKeyDown={(event) => {
                const keys = ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"]
                if (!keys.includes(event.key)) return
                event.preventDefault()
                const step =
                  event.key === "ArrowRight" || event.key === "ArrowDown"
                    ? 1
                    : -1
                const at = THEMES.findIndex((t) => t.value === value)
                const next = THEMES[(at + step + THEMES.length) % THEMES.length]
                setTheme(next.value)
                const group = event.currentTarget.parentElement
                group
                  ?.querySelectorAll<HTMLButtonElement>('[role="radio"]')
                  [THEMES.indexOf(next)]?.focus()
              }}
              className={cn(
                textLink,
                "pointer-coarse:-my-3 pointer-coarse:py-3",
                on ? "text-ink font-semibold" : "text-ink-3 hover:text-ink",
              )}
            >
              {label}
            </button>
          )
        })}
      </div>
    </PropertyRow>
  )
}
