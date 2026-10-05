import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { z } from "zod"

import DeleteAccount from "@/components/UserSettings/DeleteAccount"
import Passkeys from "@/components/UserSettings/Passkeys"
import UserInformation from "@/components/UserSettings/UserInformation"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"

const TABS = ["my-profile", "passkeys", "danger-zone"] as const

const settingsSearch = z.object({
  tab: z.enum(TABS).optional(),
  // Set after a recovery code was spent (FR-12.17).
  recovered: z.boolean().optional(),
})

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
  validateSearch: settingsSearch,
  head: () => ({
    meta: [
      {
        title: "Settings - Taskly",
      },
    ],
  }),
})

function UserSettings() {
  const { user: currentUser } = useAuth()
  const { tab = "my-profile", recovered } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })

  if (!currentUser) {
    return null
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account settings and preferences
        </p>
      </div>

      <Tabs
        value={tab}
        onValueChange={(value) =>
          navigate({
            search: (prev) => ({
              ...prev,
              tab: value as (typeof TABS)[number],
              recovered: undefined,
            }),
          })
        }
        className="gap-4"
      >
        <TabsList>
          <TabsTrigger value="my-profile">My profile</TabsTrigger>
          <TabsTrigger value="passkeys">Passkeys</TabsTrigger>
          <TabsTrigger value="danger-zone">Danger zone</TabsTrigger>
        </TabsList>
        <TabsContent value="my-profile">
          <UserInformation />
        </TabsContent>
        <TabsContent value="passkeys">
          <Passkeys recovered={recovered} />
        </TabsContent>
        <TabsContent value="danger-zone">
          <DeleteAccount />
        </TabsContent>
      </Tabs>
    </div>
  )
}
