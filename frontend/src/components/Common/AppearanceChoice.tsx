import { textLink } from "@/components/Dashboard/shared"
import { type Theme, useTheme } from "@/components/theme-provider"
import { cn } from "@/lib/utils"

const THEMES: { value: Theme; label: string; testId?: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light", testId: "light-mode" },
  { value: "dark", label: "Dark", testId: "dark-mode" },
]

/**
 * System, Light or Dark, the chosen one by weight alone (DESIGN.md: nothing
 * but weight marks the current one). A radio group, so a screen reader hears
 * the three as one choice and the arrow keys walk them.
 *
 * Used by Settings' Profile and at the foot of the sign-in screens, where
 * there is no account to keep a preference on. Both write the theme
 * provider's own storage, so a choice made at either carries to the other.
 *
 * In a module of its own, apart from Settings and the record panel's rows,
 * so the sign-in screens load it without loading those.
 */
export function AppearanceChoice({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme()

  return (
    <div
      role="radiogroup"
      aria-label="Appearance"
      className={cn("flex gap-3.5 text-sm", className)}
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
                event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : -1
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
  )
}
