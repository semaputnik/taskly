import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface LogoProps {
  size?: "sm" | "lg"
  className?: string
  asLink?: boolean
}

const WORD_SIZE = {
  sm: "text-[15px]",
  lg: "text-4xl",
} as const

/**
 * The brand is the wordmark alone, set in the UI face at semibold. The old
 * mark is retired; a new one waits until it is designed inside this world.
 */
export function Logo({ size = "sm", className, asLink = true }: LogoProps) {
  const word = (
    <span className={cn("font-semibold tracking-[-0.01em]", WORD_SIZE[size])}>
      Taskly
    </span>
  )

  if (!asLink) {
    return <span className={className}>{word}</span>
  }

  return (
    <Link to="/" className={cn("inline-flex min-h-6 items-center", className)}>
      {word}
    </Link>
  )
}
