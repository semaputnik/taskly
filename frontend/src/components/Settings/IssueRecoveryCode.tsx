import { useMutation } from "@tanstack/react-query"
import { useState } from "react"

import type { RecoveryCodeIssued, UserPublic } from "@/client"
import { SecretDialog } from "@/components/Bots/TokenDialog"
import { formatDateTime, inSentence } from "@/lib/dates"
import { issueRecoveryCode, reportUnlessDismissed } from "@/lib/passkeys"
import { act } from "./Section"

/**
 * Issue a recovery code for a user who has lost every passkey (FR-12.16).
 * It takes a fresh confirmation with the superuser's own passkey, and the
 * code is shown once, as a token is: only its digest is kept.
 */
export function IssueRecoveryCode({ user }: { user: UserPublic }) {
  const [issued, setIssued] = useState<RecoveryCodeIssued | null>(null)
  // Once one has been issued from this page the line offers another, which
  // replaces it.
  const [issuedBefore, setIssuedBefore] = useState(false)
  const issue = useMutation({
    mutationFn: () => issueRecoveryCode(user.id),
    onSuccess: (code) => {
      setIssued(code)
      setIssuedBefore(true)
    },
    onError: reportUnlessDismissed,
  })

  return (
    <>
      <button
        type="button"
        className={act}
        disabled={issue.isPending}
        onClick={() => issue.mutate()}
      >
        {issue.isPending
          ? "Confirm with your passkey…"
          : issuedBefore
            ? "Issue another"
            : "Issue a recovery code"}
        <span className="sr-only"> for {user.email}</span>
      </button>
      <SecretDialog
        onClose={() => setIssued(null)}
        secret={
          issued && {
            title: `Recovery code for ${user.email}`,
            description:
              "Give it to them yourself. They enter it with their email under “Use a recovery code” and make a new passkey.",
            noun: "code",
            fieldLabel: "Recovery code",
            consequence: "you would have to issue another",
            note: `It works once, until ${inSentence(formatDateTime(issued.expires_at))}, and replaces any code issued before.`,
            value: issued.code,
          }
        }
      />
    </>
  )
}
