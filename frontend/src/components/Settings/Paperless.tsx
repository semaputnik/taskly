import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import type { PaperlessConnectionPublic } from "@/client"
import { PropertyRow } from "@/components/Records/RecordPanel"
import { paperlessQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"
import { DisconnectPaperless } from "./DisconnectPaperless"
import { ConnectionForm, TokenForm } from "./PaperlessForms"
import {
  pdfs,
  type TestOutcome,
  TestResult,
  useTestConnection,
} from "./paperlessTest"
import { act, Note, SettingsSection } from "./Section"

/**
 * The Paperless connection (F-04): where it points, whether it works, the
 * token that is kept and never shown, and how many PDFs are kept there. Each
 * of Change and Replace turns its line into a form in place, and
 * Disconnect asks first, saying how many PDFs would be out of reach.
 */
export function PaperlessSection() {
  const { data: connection } = useQuery(paperlessQuery())

  return (
    <SettingsSection id="paperless" title="Paperless">
      {connection &&
        (connection.connected ? (
          <Connected connection={connection} />
        ) : (
          <NotConnected connection={connection} />
        ))}
    </SettingsSection>
  )
}

function NotConnected({
  connection,
}: {
  connection: PaperlessConnectionPublic
}) {
  const [editing, setEditing] = useState(false)
  const kept = connection.documents_kept ?? 0

  return (
    <>
      {editing ? (
        <ConnectionForm
          connection={connection}
          onDone={() => setEditing(false)}
        />
      ) : (
        <PropertyRow label="Connection">
          <div className="flex min-w-0 flex-wrap items-center gap-x-3.5">
            <span className="text-ink-3 text-sm">Not connected</span>
            <button
              type="button"
              className={act}
              onClick={() => setEditing(true)}
            >
              Connect Paperless
            </button>
          </div>
        </PropertyRow>
      )}
      {kept > 0 && (
        <PropertyRow label="Kept there">
          <div className="flex min-w-0 flex-wrap items-center gap-x-3.5">
            <span className="text-ink text-sm">{pdfs(kept)}</span>
            <span className="text-ink-3 min-w-0 text-[13px] text-pretty">
              out of reach until Paperless is connected again
            </span>
          </div>
        </PropertyRow>
      )}
      <Note>
        Connect your own Paperless-ngx, and every PDF you attach from then on is
        kept there, with a link back to it from the task. Everything else stays
        in Taskly.
      </Note>
    </>
  )
}

function Connected({ connection }: { connection: PaperlessConnectionPublic }) {
  const [editing, setEditing] = useState<"connection" | "token" | null>(null)
  const [outcome, setOutcome] = useState<TestOutcome | null>(null)
  const test = useTestConnection(setOutcome)
  const kept = connection.documents_kept ?? 0

  const edit = (what: "connection" | "token") => {
    setOutcome(null)
    setEditing(what)
  }

  return (
    <div className="flex flex-col gap-0.5">
      {editing === "connection" ? (
        <ConnectionForm
          connection={connection}
          onDone={() => setEditing(null)}
        />
      ) : (
        <PropertyRow label="Connection">
          <div className="flex min-w-0 flex-col">
            <div className="flex min-h-[30px] min-w-0 flex-wrap items-center gap-x-3.5 pointer-coarse:min-h-11">
              <span className="text-done text-sm font-medium">Connected</span>
              <span className="min-w-0 font-mono text-[12.5px] break-all">
                {connection.url}
              </span>
              <button
                type="button"
                className={act}
                disabled={test.isPending}
                onClick={() => test.mutate(undefined)}
              >
                {test.isPending ? "Testing…" : "Test"}
              </button>
              <button
                type="button"
                className={act}
                // A test still out would write its answer under a form.
                disabled={test.isPending}
                onClick={() => edit("connection")}
              >
                Change
                <span className="sr-only"> the Paperless address</span>
              </button>
              <DisconnectPaperless
                kept={kept}
                triggerClassName={cn(act, "hover:text-late")}
                onDone={() => setOutcome(null)}
              />
            </div>
            <TestResult outcome={outcome} />
          </div>
        </PropertyRow>
      )}

      {editing === "token" ? (
        <TokenForm connection={connection} onDone={() => setEditing(null)} />
      ) : editing === "connection" ? null : (
        // The address form asks for the token itself while it is open.
        <PropertyRow label="Token">
          <div className="flex min-w-0 flex-wrap items-center gap-x-3.5">
            <span className="text-ink-3 text-sm">set, never shown again</span>
            <button
              type="button"
              className={act}
              disabled={test.isPending}
              onClick={() => edit("token")}
            >
              Replace
              <span className="sr-only"> the Paperless token</span>
            </button>
          </div>
        </PropertyRow>
      )}

      <PropertyRow label="Kept there">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3.5">
          <span className="text-ink text-sm">
            {kept > 0 ? pdfs(kept) : "No PDFs yet"}
          </span>
          <span className="text-ink-3 min-w-0 text-[13px] text-pretty">
            every PDF attached from now on goes to Paperless; everything else
            stays here
          </span>
        </div>
      </PropertyRow>
    </div>
  )
}
