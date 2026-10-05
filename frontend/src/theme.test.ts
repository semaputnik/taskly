import { describe, expect, test } from "bun:test"
import { readFileSync } from "node:fs"
import { join } from "node:path"

/**
 * The palette as `index.css` defines it, checked pair by pair.
 *
 * Every text colour is recorded here with every ground it is laid on, and
 * each pair has to clear WCAG AA for normal text in both themes. A token
 * recalibrated in one theme is re-checked in the other by the same list.
 */

const source = readFileSync(join(import.meta.dir, "index.css"), "utf8")
// The comments name tokens too, and are not declarations.
const css = source.replace(/\/\*[\s\S]*?\*\//g, "")

/** The custom properties declared in the first block opened by `selector`. */
function block(selector: string): Map<string, string> {
  const start = css.indexOf(`${selector} {`)
  if (start === -1) throw new Error(`no ${selector} block`)
  const body = css.slice(start, css.indexOf("\n}", start))
  const tokens = new Map<string, string>()
  for (const [, name, value] of body.matchAll(/(--[\w-]+):\s*([^;]+);/g)) {
    tokens.set(name, value.trim())
  }
  return tokens
}

const themes = {
  light: block(":root"),
  dark: block(".dark"),
}

/** A token's value, following `var()` references to the colour itself. */
function resolve(tokens: Map<string, string>, name: string): string {
  const value = tokens.get(name)
  if (value === undefined) throw new Error(`${name} is not defined`)
  const reference = value.match(/^var\((--[\w-]+)\)$/)
  return reference ? resolve(tokens, reference[1]) : value
}

function luminance(hex: string): number {
  const match = hex.match(/^#([0-9a-f]{6})$/i)
  if (!match) throw new Error(`${hex} is not a six-digit hex colour`)
  const [r, g, b] = [0, 2, 4].map((i) => {
    const c = Number.parseInt(match[1].slice(i, i + 2), 16) / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (light + 0.05) / (dark + 0.05)
}

// The grounds text is read on: the page, the sheets laid on it (cards,
// popovers, dialogs), and the quiet fill of a hovered or selected row.
const GROUNDS = ["--background", "--card", "--popover", "--muted", "--accent"]

// The text colours: ink, the two greys, and the state colours that are also
// read as text (overdue, done, priority, links).
const TEXT = [
  "--foreground",
  "--ink-2",
  "--muted-foreground",
  "--link",
  "--late",
  "--done",
  "--priority-p1",
  "--priority-p2",
  "--priority-p3",
]

// Labels laid on a fill of their own.
const ON_FILL: [string, string][] = [
  ["--primary-foreground", "--primary"],
  ["--secondary-foreground", "--secondary"],
  ["--accent-foreground", "--accent"],
  ["--destructive-foreground", "--destructive"],
  ["--card-foreground", "--card"],
  ["--popover-foreground", "--popover"],
]

const AA = 4.5

for (const [theme, tokens] of Object.entries(themes)) {
  describe(`${theme} theme`, () => {
    const pairs: [string, string][] = [
      ...TEXT.flatMap((text) =>
        GROUNDS.map((ground): [string, string] => [text, ground]),
      ),
      ...ON_FILL,
    ]

    for (const [text, ground] of pairs) {
      test(`${text} on ${ground} clears AA`, () => {
        const ratio = contrast(resolve(tokens, text), resolve(tokens, ground))
        expect(ratio).toBeGreaterThanOrEqual(AA)
      })
    }

    test("native controls follow the theme", () => {
      const start = css.indexOf(theme === "light" ? ":root {" : ".dark {")
      const body = css.slice(start, css.indexOf("\n}", start))
      expect(body).toContain(`color-scheme: ${theme};`)
    })
  })
}

test("the teal accent is retired", () => {
  // Signal Teal sat at hue 182 in OKLCH; no colour of that family remains.
  expect(css).not.toMatch(/oklch\([^)]*\b18\d(\.\d+)?\s*\)/)
  expect(css).not.toContain("teal")
})
