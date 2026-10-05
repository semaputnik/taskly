import { describe, expect, test } from "bun:test"
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs"
import { dirname, join, resolve } from "node:path"

/*
 * Playwright specs run in Node, where React does not load: a spec that
 * imports app source may only reach modules free of React, lucide and
 * components, or it fails to load and stops collection of every spec.
 */

const FRONTEND = resolve(import.meta.dir, "..")
const IMPORT = /(?:^|\n)\s*(?:import|export)\b[^;]*?\bfrom\s+["']([^"']+)["']/g
const FORBIDDEN = /^(react|react-dom|lucide-react)(\/|$)/

function resolveModule(from: string, spec: string): string | null {
  const base = spec.startsWith("@/")
    ? join(FRONTEND, "src", spec.slice(2))
    : spec.startsWith(".")
      ? resolve(dirname(from), spec)
      : null
  if (!base) return null
  for (const ext of ["", ".ts", ".tsx", "/index.ts", "/index.tsx"]) {
    const file = base + ext
    if (existsSync(file) && statSync(file).isFile()) return file
  }
  return null
}

/** Why loading `entry` would load React, or null if it would not. */
function reactPath(entry: string): string[] | null {
  const seen = new Set<string>()
  const walk = (file: string, trail: string[]): string[] | null => {
    if (seen.has(file)) return null
    seen.add(file)
    const here = [...trail, file.slice(FRONTEND.length + 1)]
    if (file.endsWith(".tsx")) return here
    const source = readFileSync(file, "utf8").replace(
      /import\s+type\b[^;]*?from\s+["'][^"']+["']/g,
      "",
    )
    for (const match of source.matchAll(IMPORT)) {
      const spec = match[1]
      if (FORBIDDEN.test(spec)) return [...here, spec]
      const next = resolveModule(file, spec)
      const found = next && walk(next, here)
      if (found) return found
    }
    return null
  }
  return walk(entry, [])
}

describe("Playwright specs", () => {
  const dir = join(FRONTEND, "tests")
  const specs = readdirSync(dir).filter((name) => name.endsWith(".spec.ts"))

  test("are found", () => {
    expect(specs.length).toBeGreaterThan(0)
  })

  for (const spec of specs) {
    test(`${spec} loads without React`, () => {
      expect(reactPath(join(dir, spec))).toBeNull()
    })
  }
})
