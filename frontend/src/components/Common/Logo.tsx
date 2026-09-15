import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface LogoProps {
  /** `icon` is the mark alone; `full` pairs it with the wordmark. */
  variant?: "full" | "icon"
  size?: "sm" | "lg"
  className?: string
  asLink?: boolean
}

const MARK_SIZE = {
  sm: "size-6 rounded-[7px]",
  lg: "size-12 rounded-[14px]",
} as const

const WORD_SIZE = {
  sm: "text-lg",
  lg: "text-4xl",
} as const

/**
 * The Taskly mark: the completion check, filled in the one accent the system
 * allows itself. Drawn inline rather than loaded as a file so it follows the
 * theme's primary token and stays crisp at any size.
 */
function Mark({ size }: { size: "sm" | "lg" }) {
  return (
    <span
      className={cn(
        "bg-primary text-primary-foreground grid shrink-0 place-content-center",
        MARK_SIZE[size],
      )}
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={3}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className={size === "lg" ? "size-7" : "size-3.5"}
      >
        <path d="M20 6 9 17l-5-5" />
      </svg>
    </span>
  )
}

export function Logo({
  variant = "full",
  size = "sm",
  className,
  asLink = true,
}: LogoProps) {
  const content = (
    <span
      className={cn(
        "flex items-center",
        size === "lg" ? "gap-3" : "gap-2",
        className,
      )}
    >
      <Mark size={size} />
      {variant === "full" ? (
        <span className={cn("font-bold tracking-tight", WORD_SIZE[size])}>
          Taskly
        </span>
      ) : (
        <span className="sr-only">Taskly</span>
      )}
    </span>
  )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
