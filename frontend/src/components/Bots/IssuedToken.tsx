import { useQueryClient } from "@tanstack/react-query"
import { createContext, type ReactNode, useContext, useState } from "react"

import TokenDialog from "./TokenDialog"

export interface Issued {
  botName: string
  token: string
  expiresAt?: string | null
}

const ShowIssuedToken = createContext<(issued: Issued) => void>(() => {})

/**
 * Holds a just-issued token on the page itself, above the table.
 *
 * The button that issues a token sits in the bot user's row, and the row
 * changes as soon as the list learns the token is out — which it can at any
 * moment, a refetch on window focus included. A dialog kept in the row would
 * vanish with it, taking a token that can never be shown again.
 */
export function IssuedTokenProvider({ children }: { children: ReactNode }) {
  const [issued, setIssued] = useState<Issued | null>(null)
  const queryClient = useQueryClient()

  return (
    <ShowIssuedToken.Provider
      value={(next) => {
        setIssued(next)
        queryClient.invalidateQueries({ queryKey: ["bots"] })
      }}
    >
      {children}
      <TokenDialog
        botName={issued?.botName ?? ""}
        token={issued?.token ?? null}
        expiresAt={issued?.expiresAt}
        onClose={() => setIssued(null)}
      />
    </ShowIssuedToken.Provider>
  )
}

/** Shows a just-issued token, once, in the page's token dialog. */
export function useShowIssuedToken() {
  return useContext(ShowIssuedToken)
}
