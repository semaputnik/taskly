import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"

import { Account } from "@/components/Settings/Account"
import { PaperlessSection } from "@/components/Settings/Paperless"
import { Passkeys } from "@/components/Settings/Passkeys"
import { Profile } from "@/components/Settings/Profile"
import { Sessions } from "@/components/Settings/Sessions"
import { Users } from "@/components/Settings/Users"
import useAuth from "@/hooks/useAuth"
import {
  currentUserQuery,
  passkeysQuery,
  usersQuery,
  warmQuery,
} from "@/lib/serverState"

const settingsSearch = z.object({
  // Set after a recovery code was spent (FR-12.17).
  recovered: z.boolean().optional(),
})

export const Route = createFileRoute("/_layout/settings")({
  component: Settings,
  validateSearch: settingsSearch,
  // The requests start as soon as the route is matched, beside the download
  // of the page's own code. The users' list is asked for only once the
  // account is known to be the superuser's.
  loader: ({ context }) => {
    const { queryClient } = context
    void warmQuery(queryClient, passkeysQuery())
    void warmQuery(queryClient, currentUserQuery()).then((user) => {
      if (user?.is_superuser) void warmQuery(queryClient, usersQuery())
    })
  },
  head: () => ({
    meta: [
      {
        title: "Settings - Taskly",
      },
    ],
  }),
})

/**
 * One document, in the order a person reaches for things: who I am, what
 * signs me in, what ends it, where my PDFs go, who else is here (the
 * superuser's only) and the one act with no way back. Each section saves in
 * place; there are no tabs.
 */
function Settings() {
  const { user } = useAuth()
  const { recovered } = Route.useSearch()

  if (!user) {
    return null
  }

  return (
    <div className="page-column">
      <h1 className="mb-1 text-[22px] leading-[1.2] font-semibold tracking-[-0.015em]">
        Settings
      </h1>
      <p className="text-ink-3">
        Your account on this installation, and what signs you in.
      </p>
      <Profile />
      <Passkeys recovered={recovered} />
      <Sessions />
      {/* Reserved for the Paperless connection (#211). */}
      <PaperlessSection />
      <Users />
      <Account />
    </div>
  )
}
