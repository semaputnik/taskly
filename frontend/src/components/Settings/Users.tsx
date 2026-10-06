import { useSuspenseQuery } from "@tanstack/react-query"
import { Suspense } from "react"

import type { UserListed } from "@/client"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { formatDayOf } from "@/lib/dates"
import { usersQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"
import { IssueRecoveryCode } from "./IssueRecoveryCode"
import { Note, SettingsSection } from "./Section"

/**
 * Every account on this installation, for the superuser only (FR-09.2): who,
 * how many passkeys they hold, when one last signed them in, and the one
 * thing a superuser can do for them, issue a recovery code (FR-12.16). For
 * anyone else the section is not drawn and the list is not asked for.
 */
export function Users() {
  const { user } = useAuth()
  if (!user?.is_superuser) return null

  return (
    <Suspense fallback={<UsersPending />}>
      <UserLines currentId={user.id} />
    </Suspense>
  )
}

function UserLines({ currentId }: { currentId: string }) {
  const { data } = useSuspenseQuery(usersQuery())

  return (
    <SettingsSection
      id="users"
      title="Users"
      count={data.count}
      action={<span className="text-ink-3">You are the superuser</span>}
    >
      <ul aria-label="Users">
        {data.data.map((account) => (
          <UserLine
            key={account.id}
            account={account}
            isCurrentUser={account.id === currentId}
          />
        ))}
      </ul>
      <Note>
        A recovery code is shown once, works for 24 hours and burns after five
        wrong tries. Spending it signs that account out everywhere.
      </Note>
    </SettingsSection>
  )
}

function UserLine({
  account,
  isCurrentUser,
}: {
  account: UserListed
  isCurrentUser: boolean
}) {
  const name = account.full_name || account.email.split("@")[0]
  const none = account.passkey_count === 0

  return (
    <li className="border-rule grid grid-cols-[26px_minmax(0,1fr)] items-start gap-x-3 gap-y-1 border-b py-2.5 sm:grid-cols-[26px_minmax(0,1fr)_auto]">
      <span
        aria-hidden
        className={cn(
          "grid size-[26px] place-items-center rounded-full text-xs font-semibold",
          isCurrentUser ? "bg-ink text-page" : "bg-rule-strong text-ink-2",
        )}
      >
        {name.charAt(0).toUpperCase()}
      </span>
      <div className="min-w-0">
        <div className="truncate text-sm font-medium">{name}</div>
        <div className="text-ink-3 mt-0.5 flex flex-wrap gap-x-3 text-[12.5px]">
          <span className="break-all">{account.email}</span>
          {account.is_superuser && (
            <span>superuser{isCurrentUser ? " · you" : ""}</span>
          )}
          {none ? (
            <span className="text-late font-medium">no passkeys</span>
          ) : (
            <span>
              {account.passkey_count}{" "}
              {account.passkey_count === 1 ? "passkey" : "passkeys"}
            </span>
          )}
          <span>
            {account.last_sign_in_at
              ? `last signed in ${formatDayOf(account.last_sign_in_at)}`
              : "never signed in"}
          </span>
        </div>
      </div>
      <div className="col-start-2 text-[13px] sm:col-start-3">
        {isCurrentUser ? (
          // The superuser's own code comes from the server's command line
          // (FR-12.19).
          <span className="text-ink-3">Recovery: not for your own account</span>
        ) : (
          <IssueRecoveryCode user={account} />
        )}
      </div>
    </li>
  )
}

function UsersPending() {
  return (
    <section aria-hidden className="pt-[22px]">
      <div className="border-rule-strong border-b pb-2">
        <Skeleton className="h-4 w-16" />
      </div>
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="border-rule flex gap-3 border-b py-2.5">
          <Skeleton className="size-[26px] rounded-full" />
          <div className="flex flex-col gap-1.5">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-64 max-w-full" />
          </div>
        </div>
      ))}
    </section>
  )
}
