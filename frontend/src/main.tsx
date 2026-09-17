import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import { StrictMode } from "react"
import ReactDOM from "react-dom/client"
import { client } from "./client/client.gen"
import { ThemeProvider } from "./components/theme-provider"
import { Toaster } from "./components/ui/sonner"
import { isRefusal, isSessionGone } from "./lib/apiErrors"
import { configureServerState } from "./lib/serverState"
import "./index.css"
import { routeTree } from "./routeTree.gen"

client.setConfig({
  baseURL: import.meta.env.VITE_API_URL ?? "",
  auth: () => localStorage.getItem("access_token") || "",
})

// Every query on a screen is refused at once, and each fresh assignment to
// `location.href` aborts the navigation the previous one started.
let redirectingToLogin = false

const handleApiError = (error: Error) => {
  // Only a session that is gone sends the reader to sign in: a 403 refuses
  // something the signed-in reader asked for, and is said where it happened.
  if (!isSessionGone(error) || redirectingToLogin) return
  redirectingToLogin = true
  localStorage.removeItem("access_token")
  window.location.href = "/login"
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A request the API has refused for what it asked — a credential it
      // turned away, a record that is not there or not yours — will be
      // refused again: retrying cannot mend it. Retried like any other
      // failure, it costs four refusals and about eight seconds of a screen
      // that neither shows anything nor says why, which is exactly the
      // stranding a failure message exists to prevent. Only a failure that
      // may pass is tried again.
      retry: (failureCount, error) => !isRefusal(error) && failureCount < 3,
    },
    mutations: { retry: false },
  },
  queryCache: new QueryCache({
    onError: handleApiError,
  }),
  mutationCache: new MutationCache({
    onError: handleApiError,
  }),
})

configureServerState(queryClient)

const router = createRouter({ routeTree })
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
        <Toaster richColors closeButton />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
)
