import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface WordmarkProps {
  className?: string
  asLink?: boolean
}

/**
 * The brand is the wordmark alone, set in the UI face at semibold. The old
 * mark is retired; a new one waits until it is designed inside this world.
 */
export function Wordmark({ className, asLink = true }: WordmarkProps) {
  const word = (
    <span className="text-[15px] font-semibold tracking-[-0.01em]">Taskly</span>
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
