import type { LucideIcon } from "lucide-react"

interface EmptyStateProps {
  icon: LucideIcon
  /** What is not here, said plainly. */
  title: string
  /** One line: what this screen is for, or why the list came back empty. */
  description: string
  /** The way out — the action that fills the screen, or clears the filter. */
  action?: React.ReactNode
}

/**
 * What a list shows when it has nothing to show.
 *
 * An empty list has two quite different causes, and they need different words:
 * nothing exists yet, which calls for an explanation of what the screen is
 * for, or a filter excluded everything, which calls for a way to undo it.
 * Callers pick; this only lays it out.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-16 text-center">
      <Icon className="text-muted-foreground size-6" aria-hidden />
      <p className="font-medium">{title}</p>
      <p className="text-muted-foreground max-w-sm text-sm text-pretty">
        {description}
      </p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
