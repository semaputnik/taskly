import { createFileRoute, redirect } from "@tanstack/react-router"

/**
 * There is no Admin screen: the users' list is a section of the
 * superuser's Settings (FR-09.2). The old address lands on it.
 */
export const Route = createFileRoute("/_layout/admin")({
  beforeLoad: () => {
    throw redirect({ to: "/settings", hash: "users", replace: true })
  },
})
