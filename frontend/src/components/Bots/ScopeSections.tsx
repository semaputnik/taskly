import type { BotPermissions } from "@/client"
import { RecordSection } from "@/components/Records/RecordPanel"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import type { ScopeProject } from "@/lib/serverState"
import { cn } from "@/lib/utils"
import { FIXED_PERMISSIONS, PERMISSIONS } from "./permissions"

/**
 * What a bot user may reach and do, as the two sections that say it: the
 * projects it is scoped to, then the permissions it holds there. A bot user's
 * column and a draft of one are both made of these, so a scope is read and
 * set the same way before and after the record exists.
 *
 * The boxes sit in as many columns as the column has room for, 200px each.
 */
const grid = "grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-x-4"

function Box({
  id,
  label,
  note,
  checked,
  onCheckedChange,
}: {
  id: string
  label: string
  note?: string
  checked: boolean
  onCheckedChange: (checked: boolean) => void
}) {
  return (
    <div className="flex min-h-[30px] items-center gap-2.5 pointer-coarse:min-h-11">
      <Checkbox
        id={id}
        checked={checked}
        onCheckedChange={(value) => onCheckedChange(value === true)}
      />
      <Label
        htmlFor={id}
        className="min-h-[30px] flex-1 text-sm leading-snug font-normal pointer-coarse:min-h-11"
      >
        {label}
        {note && <small className="text-ink-3 ml-1.5 text-xs">{note}</small>}
      </Label>
    </div>
  )
}

/**
 * The projects it reaches. Each is ticked on its own: a project made later is
 * never added by itself. An archived project is offered only while it is
 * already in the scope, so it can be taken out; no other is, since a bot user
 * reaches nothing archived whatever its scope says.
 */
export function ProjectsSection({
  idPrefix,
  projects,
  selected,
  onToggle,
}: {
  idPrefix: string
  projects: ScopeProject[]
  selected: string[]
  onToggle: (projectId: string, granted: boolean) => void
}) {
  const offered = projects.filter(
    (project) => !project.archived || selected.includes(project.id),
  )
  const reached = offered.filter(({ id }) => selected.includes(id)).length

  return (
    <RecordSection title="Projects" count={`${reached} of ${offered.length}`}>
      <div className={cn(grid, "pt-2")}>
        {offered.map((project) => (
          <Box
            key={project.id}
            id={`${idPrefix}-project-${project.id}`}
            label={
              project.archived ? `${project.name} (archived)` : project.name
            }
            checked={selected.includes(project.id)}
            onCheckedChange={(granted) => onToggle(project.id, granted)}
          />
        ))}
      </div>
      {offered.length === 0 && (
        <p className="text-ink-3 pt-2 text-sm">No projects to grant yet</p>
      )}
      <p className="text-ink-3 pt-2 text-[12.5px] text-pretty">
        A bot user reaches only the projects ticked here, and never an archived
        one.
      </p>
    </RecordSection>
  )
}

/**
 * What it may do, with what no setting is behind drawn dashed after the
 * grants, so the list reads as the whole of it.
 */
export function PermissionsSection({
  idPrefix,
  permissions,
  onToggle,
}: {
  idPrefix: string
  permissions: BotPermissions
  onToggle: (key: keyof BotPermissions, granted: boolean) => void
}) {
  return (
    <RecordSection title="Permissions">
      <div className={cn(grid, "pt-2")}>
        {PERMISSIONS.map(({ key, label, note }) => (
          <Box
            key={key}
            id={`${idPrefix}-permission-${key}`}
            label={label}
            note={note}
            checked={Boolean(permissions[key])}
            onCheckedChange={(granted) => onToggle(key, granted)}
          />
        ))}
        {FIXED_PERMISSIONS.map(({ label, note }) => (
          // Not a control: nothing can be changed here, so nothing is tried.
          <div
            key={label}
            className="text-ink-3 flex min-h-[30px] items-center gap-2.5 pointer-coarse:min-h-11"
          >
            <span
              aria-hidden
              className="border-rule-strong size-4 shrink-0 rounded-[4px] border border-dashed"
            />
            <span className="text-sm leading-snug">
              {label}
              <span className="sr-only">: </span>
              <small className="ml-1.5 text-xs">{note}</small>
            </span>
          </div>
        ))}
      </div>
    </RecordSection>
  )
}
