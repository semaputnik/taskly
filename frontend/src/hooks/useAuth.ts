import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"

import {
  type Body_login_login_access_token as AccessToken,
  LoginService,
  type UserRegister,
  UsersService,
} from "@/client"
import {
  clearServerState,
  currentUserQuery,
  useReportChange,
} from "@/lib/serverState"
import { toastError } from "@/lib/toasts"

const isLoggedIn = () => {
  return localStorage.getItem("access_token") !== null
}

const useAuth = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const reportChange = useReportChange()

  const { data: user } = useQuery({
    ...currentUserQuery(),
    enabled: isLoggedIn(),
  })

  const signUpMutation = useMutation({
    mutationFn: (data: UserRegister) =>
      UsersService.registerUser({ body: data }),
    onSuccess: () => {
      navigate({ to: "/login" })
    },
    onError: (error) => toastError(error),
    onSettled: () => {
      reportChange({ type: "users changed" })
    },
  })

  const login = async (data: AccessToken) => {
    const response = await LoginService.loginAccessToken({
      body: data,
    })
    localStorage.setItem("access_token", response.data.access_token)
  }

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: () => {
      navigate({ to: "/" })
    },
    onError: (error) => toastError(error),
  })

  const logout = () => {
    localStorage.removeItem("access_token")
    // The next account to sign in in this tab must not see this one's data.
    clearServerState(queryClient)
    navigate({ to: "/login" })
  }

  return {
    signUpMutation,
    loginMutation,
    logout,
    user,
  }
}

export { isLoggedIn }
export default useAuth
