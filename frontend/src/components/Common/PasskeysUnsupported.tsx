import { TriangleAlert } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

/**
 * What the sign-in screens say in a browser without passkey support. There is
 * no other way in, so it says so plainly rather than offering one (FR-12.12).
 */
export function PasskeysUnsupported() {
  return (
    <Alert variant="destructive" data-testid="passkeys-unsupported">
      <TriangleAlert />
      <AlertTitle>This browser can't use passkeys</AlertTitle>
      <AlertDescription>
        Taskly signs you in with a passkey and nothing else. Open it in a
        browser that supports passkeys, such as a current Chrome, Safari,
        Firefox or Edge.
      </AlertDescription>
    </Alert>
  )
}
