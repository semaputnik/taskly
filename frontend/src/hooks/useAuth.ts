import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"

import {
  recoverAccount,
  registerAccount,
  reportUnlessDismissed,
  signInWithPasskey,
} from "@/lib/passkeys"
import { clearServerState, currentUserQuery } from "@/lib/serverState"

const isLoggedIn = () => {
  return localStorage.getItem("access_token") !== null
}

const useAuth = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: user } = useQuery({
    ...currentUserQuery(),
    enabled: isLoggedIn(),
  })

  const startSession = (token: string) => {
    // Whatever another account read in this tab must not show for this one.
    clearServerState(queryClient)
    localStorage.setItem("access_token", token)
  }

  const signInMutation = useMutation({
    mutationFn: (options: { autofill?: boolean } = {}) =>
      signInWithPasskey(options),
    onSuccess: (token) => {
      startSession(token)
      navigate({ to: "/" })
    },
    onError: reportUnlessDismissed,
  })

  const registerMutation = useMutation({
    mutationFn: (email: string) => registerAccount(email),
    onSuccess: (token) => {
      startSession(token)
      navigate({ to: "/" })
    },
    onError: reportUnlessDismissed,
  })

  const recoverMutation = useMutation({
    mutationFn: ({ email, code }: { email: string; code: string }) =>
      recoverAccount(email, code),
    onSuccess: (token) => {
      startSession(token)
      // Straight to the passkeys, to remove any the user does not recognise
      // (FR-12.17).
      navigate({
        to: "/settings",
        search: { tab: "passkeys", recovered: true },
      })
    },
    onError: reportUnlessDismissed,
  })

  const logout = () => {
    localStorage.removeItem("access_token")
    // The next account to sign in in this tab must not see this one's data.
    clearServerState(queryClient)
    navigate({ to: "/login" })
  }

  return {
    signInMutation,
    registerMutation,
    recoverMutation,
    logout,
    user,
  }
}

export { isLoggedIn }
export default useAuth
