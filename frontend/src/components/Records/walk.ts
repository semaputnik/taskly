import { useEffect, useId, useSyncExternalStore } from "react"

/**
 * The list a record was opened from, so the column can walk it.
 *
 * A screen that lists tasks says so while it is on screen, in the order it
 * shows them; the column finds the open task in what has been said and offers
 * its neighbours. A task opened from somewhere that lists nothing — a link in
 * the activity log, a notice — is on no list, and the column has no next or
 * previous to offer. A page with several groups (the day page's bands) says
 * each group with its `rank`, and they are walked as one list in that order.
 */

interface Source {
  rank: number
  ids: readonly string[]
}

/** The groups on screen as one list, a record kept at its first place. */
export function joinLists(sources: readonly Source[]): string[] {
  const seen = new Set<string>()
  const joined: string[] = []
  for (const { ids } of [...sources].sort((a, b) => a.rank - b.rank)) {
    for (const id of ids) {
      if (seen.has(id)) continue
      seen.add(id)
      joined.push(id)
    }
  }
  return joined
}

export interface Neighbours {
  /** 1-based, for "3 of 12". */
  position: number
  count: number
  previous?: string
  next?: string
}

/** Where `id` stands in `list`; null when there is nowhere to walk to. */
export function neighbours(
  list: readonly string[],
  id: string | null,
): Neighbours | null {
  const index = id ? list.indexOf(id) : -1
  if (index < 0 || list.length < 2) return null
  return {
    position: index + 1,
    count: list.length,
    previous: list[index - 1],
    next: list[index + 1],
  }
}

const sources = new Map<string, Source>()
const listeners = new Set<() => void>()
let snapshot: readonly string[] = []

function publish() {
  snapshot = joinLists([...sources.values()])
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Say, while this is mounted, which records a group lists and in what order. */
export function useRecordList(rank: number, ids: readonly string[]) {
  const key = useId()
  const joined = ids.join(",")
  useEffect(() => {
    sources.set(key, { rank, ids: joined ? joined.split(",") : [] })
    publish()
    return () => {
      sources.delete(key)
      publish()
    }
  }, [key, rank, joined])
}

/** The task's place in the list it is open from, if there is one. */
export function useWalk(id: string | null): Neighbours | null {
  const list = useSyncExternalStore(
    subscribe,
    () => snapshot,
    () => snapshot,
  )
  return neighbours(list, id)
}
