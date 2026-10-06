/**
 * Wording shared by the pages that say their counts in a sentence (Projects,
 * Tags). Plain functions, so they can be read and tested apart from a page.
 */

/** "1 tag", "3 tags", "2 open tasks": the count and its noun. */
export const plural = (count: number, one: string, many = `${one}s`) =>
  `${count} ${count === 1 ? one : many}`

/** "urgent", "urgent and Urgent", "a, b and c". */
export function nameList(names: string[]): string {
  if (names.length < 2) return names.join("")
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`
}

/** Where tasks sit that no list shows: "an archived project", "archived projects". */
export const archivedProjects = (count: number) =>
  count === 1 ? "an archived project" : "archived projects"
