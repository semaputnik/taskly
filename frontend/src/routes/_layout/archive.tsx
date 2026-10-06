import { createFileRoute, redirect } from "@tanstack/react-router"

/**
 * The Archive had a screen of its own; it is now a section of Projects
 * (FR-05.14), so the old address, in a bookmark or a link, lands there.
 */
export const Route = createFileRoute("/_layout/archive")({
  beforeLoad: () => {
    throw redirect({ to: "/projects", replace: true })
  },
})
