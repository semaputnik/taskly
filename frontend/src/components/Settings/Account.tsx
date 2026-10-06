import { PropertyRow } from "@/components/Records/RecordPanel"
import { cn } from "@/lib/utils"
import DeleteConfirmation from "./DeleteConfirmation"
import { act, SettingsSection } from "./Section"

/**
 * The one act with no way back: deleting the account. It asks again in a
 * dialog that says everything that goes with it.
 */
export function Account() {
  return (
    <SettingsSection id="account" title="Account">
      <PropertyRow label="Delete">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3">
          <DeleteConfirmation triggerClassName={cn(act, "hover:text-late")} />
          <span className="text-ink-3 min-w-0 text-[13px] text-pretty">
            removes your tasks, projects, bot users and passkeys
          </span>
        </div>
      </PropertyRow>
    </SettingsSection>
  )
}
