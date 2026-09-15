import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { createRootRoute, HeadContent, Outlet } from "@tanstack/react-router"
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools"
import ErrorComponent from "@/components/Common/ErrorComponent"
import NotFound from "@/components/Common/NotFound"

/**
 * The devtools float over the bottom-right corner, which is where the task
 * panel keeps its primary action — their trigger swallows the click. They are
 * off unless asked for: set VITE_DEVTOOLS=true to bring them back.
 */
const devtools = import.meta.env.VITE_DEVTOOLS === "true"

export const Route = createRootRoute({
  component: () => (
    <>
      <HeadContent />
      <Outlet />
      {devtools && (
        <>
          <TanStackRouterDevtools position="bottom-right" />
          <ReactQueryDevtools initialIsOpen={false} />
        </>
      )}
    </>
  ),
  notFoundComponent: () => <NotFound />,
  errorComponent: () => <ErrorComponent />,
})
