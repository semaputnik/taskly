import { AppearanceChoice } from "@/components/Common/AppearanceChoice"
import { PropertyRow } from "@/components/Records/RecordPanel"

/**
 * How Taskly looks, as a row of Settings' Profile.
 */
export function Appearance() {
  return (
    <PropertyRow label="Appearance">
      <AppearanceChoice />
    </PropertyRow>
  )
}
