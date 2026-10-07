import { describe, expect, test } from "bun:test"

import {
  clearKeptDraft,
  draftKey,
  emptyDraft,
  keepDraft,
  readKeptDraft,
  type TaskDraft,
} from "./draft"

/** A stand-in for localStorage that can also refuse, as a private window does. */
function memory(refuse = false) {
  const items = new Map<string, string>()
  const guard = () => {
    if (refuse) throw new DOMException("denied", "SecurityError")
  }
  return {
    items,
    getItem: (key: string) => {
      guard()
      return items.get(key) ?? null
    },
    setItem: (key: string, value: string) => {
      guard()
      items.set(key, value)
    },
    removeItem: (key: string) => {
      guard()
      items.delete(key)
    },
  }
}

const top = {}
const written: TaskDraft = {
  title: "Book the vet",
  description: "Ask about the vaccine",
  project_id: "p1",
  due_date: "2026-10-09",
  priority: "P1",
  assignee: "me",
  tags: ["home", "pets"],
  recurrence: { frequency: "every_n_days", interval_days: 3 },
}

describe("a kept task draft", () => {
  test("comes back as it was written", () => {
    const storage = memory()
    keepDraft(top, written, storage)
    expect(readKeptDraft(top, storage)).toEqual(written)
  })

  test("is absent until something is kept, and after it is cleared", () => {
    const storage = memory()
    expect(readKeptDraft(top, storage)).toBeNull()
    keepDraft(top, written, storage)
    clearKeptDraft(top, storage)
    expect(readKeptDraft(top, storage)).toBeNull()
    expect(storage.items.size).toBe(0)
  })

  test("is kept apart for a subtask and for a task of its own", () => {
    const storage = memory()
    keepDraft(top, written, storage)
    expect(readKeptDraft({ parentId: "t1" }, storage)).toBeNull()
    keepDraft({ parentId: "t1" }, { ...written, title: "Sub" }, storage)
    expect(readKeptDraft(top, storage)?.title).toBe("Book the vet")
    expect(readKeptDraft({ parentId: "t1" }, storage)?.title).toBe("Sub")
  })

  test("is kept apart for each project a list is narrowed to", () => {
    const storage = memory()
    keepDraft({ projectId: "p1" }, written, storage)
    expect(readKeptDraft({ projectId: "p2" }, storage)).toBeNull()
    expect(readKeptDraft(top, storage)).toBeNull()
    expect(readKeptDraft({ projectId: "p1" }, storage)?.title).toBe(
      "Book the vet",
    )
    expect(draftKey({ projectId: "p1" })).not.toBe(draftKey(top))
  })

  test("is ignored when what is stored is not a draft", () => {
    const storage = memory()
    keepDraft(top, written, storage)
    const [key] = [...storage.items.keys()]
    for (const junk of [
      "not json",
      "null",
      "[]",
      JSON.stringify({ title: 3 }),
      JSON.stringify({ ...written, tags: "home" }),
      JSON.stringify({ ...written, recurrence: "weekly" }),
    ]) {
      storage.items.set(key, junk)
      expect(readKeptDraft(top, storage)).toBeNull()
    }
  })

  test("fills what an older draft lacks from an empty one", () => {
    const storage = memory()
    keepDraft(top, written, storage)
    const [key] = [...storage.items.keys()]
    storage.items.set(key, JSON.stringify({ title: "Only a title" }))
    expect(readKeptDraft(top, storage)).toEqual({
      ...emptyDraft(top),
      title: "Only a title",
    })
  })

  test("never throws when storage is refused or missing", () => {
    const refusing = memory(true)
    expect(() => keepDraft(top, written, refusing)).not.toThrow()
    expect(readKeptDraft(top, refusing)).toBeNull()
    expect(() => clearKeptDraft(top, refusing)).not.toThrow()
    expect(() => keepDraft(top, written, null)).not.toThrow()
    expect(readKeptDraft(top, null)).toBeNull()
    expect(() => clearKeptDraft(top, null)).not.toThrow()
  })
})
