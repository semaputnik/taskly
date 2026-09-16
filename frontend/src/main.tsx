import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import { AxiosError } from "axios"
import { StrictMode } from "react"
import ReactDOM from "react-dom/client"
import { client } from "./client/client.gen"
import { ThemeProvider } from "./components/theme-provider"
import { Toaster } from "./components/ui/sonner"
import "./index.css"
import { routeTree } from "./routeTree.gen"

client.setConfig({
  baseURL: import.meta.env.VITE_API_URL ?? "",
  auth: () => localStorage.getItem("access_token") || "",
})

/** Whether the API turned the request away for who the caller is. */
const isCredentialError = (error: Error): boolean =>
  error instanceof AxiosError &&
  [401, 403].includes(error.response?.status ?? 0)

// Every query on a screen is refused at once, and each fresh assignment to
// `location.href` aborts the navigation the previous one started.
let redirectingToLogin = false

const handleApiError = (error: Error) => {
  if (!isCredentialError(error) || redirectingToLogin) return
  redirectingToLogin = true
  localStorage.removeItem("access_token")
  window.location.href = "/login"
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A credential the API has turned away will be turned away again: it is
      // the one failure that retrying cannot mend. Retried like any other, it
      // costs four refusals and about eight seconds of a screen that neither
      // loads nor sends the reader to the login it needs — which is exactly
      // the stranding this handler exists to prevent.
      retry: (failureCount, error) =>
        !isCredentialError(error as Error) && failureCount < 3,
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
