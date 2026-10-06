import { createContext, type ReactNode, useContext, useState } from "react"
import { useReportChange } from "@/lib/serverState"
import TokenDialog, { type Secret, SecretDialog } from "./TokenDialog"

export interface Issued {
  botName: string
  token: string
  expiresAt?: string | null
}

const ShowIssuedToken = createContext<(issued: Issued) => void>(() => {})
const ShowWebhookSecret = createContext<
  (issued: { botName: string; secret: string }) => void
>(() => {})

/**
 * Holds a just-issued token, or a webhook secret, above the panels.
 *
 * The button that issues a token sits in the bot user's row, and the row
 * changes as soon as the list learns the token is out — which it can at any
 * moment, a refetch on window focus included. A dialog kept in the row would
 * vanish with it, taking a token that can never be shown again. A webhook's
 * secret is shown once for the same reason and held in the same place.
 */
export function IssuedTokenProvider({ children }: { children: ReactNode }) {
  const [issued, setIssued] = useState<Issued | null>(null)
  const [secret, setSecret] = useState<Secret | null>(null)
  const reportChange = useReportChange()

  return (
    <ShowIssuedToken.Provider
      value={(next) => {
        setIssued(next)
        reportChange({ type: "bot token changed" })
      }}
    >
      <ShowWebhookSecret.Provider
        value={({ botName, secret: value }) =>
          setSecret({
            title: `Webhook secret for ${botName}`,
            description:
              "Every delivery to this bot user's webhooks is signed with this secret. The receiver checks the signature with it.",
            noun: "secret",
            fieldLabel: "Webhook secret",
            consequence: "you would have to regenerate it",
            value,
          })
        }
      >
        {children}
        <TokenDialog
          botName={issued?.botName ?? ""}
          token={issued?.token ?? null}
          expiresAt={issued?.expiresAt}
          onClose={() => setIssued(null)}
        />
        <SecretDialog secret={secret} onClose={() => setSecret(null)} />
      </ShowWebhookSecret.Provider>
    </ShowIssuedToken.Provider>
  )
}

/** Shows a just-issued token, once, in the page's token dialog. */
export function useShowIssuedToken() {
  return useContext(ShowIssuedToken)
}

/** Shows a webhook secret, once, in the page's reveal dialog. */
export function useShowWebhookSecret() {
  return useContext(ShowWebhookSecret)
}
