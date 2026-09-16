import type { Locator, Page } from "@playwright/test"

type Rgba = [number, number, number, number]

/**
 * Colours as the page renders them, read back through a canvas so that any
 * CSS colour syntax — oklch, color-mix, rgb with alpha — comes out as sRGB.
 * `layers` are painted bottom first, so a translucent layer is composited the
 * way the browser composites it.
 */
async function paint(page: Page, layers: string[]): Promise<Rgba> {
  return page.evaluate((colours) => {
    const canvas = document.createElement("canvas")
    canvas.width = 1
    canvas.height = 1
    const context = canvas.getContext("2d")
    if (!context) throw new Error("no 2d context")
    for (const colour of colours) {
      context.fillStyle = colour
      context.fillRect(0, 0, 1, 1)
    }
    return Array.from(context.getImageData(0, 0, 1, 1).data) as Rgba
  }, layers)
}

function luminance([r, g, b]: Rgba): number {
  const linear = (channel: number) => {
    const c = channel / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
}

/** The WCAG contrast ratio between two opaque colours. */
function ratio(a: Rgba, b: Rgba): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (light + 0.05) / (dark + 0.05)
}

/** OKLab lightness, for how far a surface visibly moved. */
function lightness([r, g, b]: Rgba): number {
  const linear = (channel: number) => {
    const c = channel / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  const [lr, lg, lb] = [linear(r), linear(g), linear(b)]
  const l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb)
  const m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb)
  const s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb)
  return 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s
}

/** The ground the page itself is painted on. */
export async function pageGround(page: Page): Promise<string> {
  return page.evaluate(() => getComputedStyle(document.body).backgroundColor)
}

/** A theme token's value, e.g. `--card`, as the page resolves it. */
export async function token(page: Page, name: string): Promise<string> {
  return page.evaluate(
    (property) =>
      getComputedStyle(document.documentElement)
        .getPropertyValue(property)
        .trim(),
    name,
  )
}

/** Contrast of an element's text against its own background fill. */
export async function textOnFill(element: Locator): Promise<number> {
  const { color, background } = await element.evaluate((node) => {
    const style = getComputedStyle(node)
    return { color: style.color, background: style.backgroundColor }
  })
  const page = element.page()
  return ratio(await paint(page, [color]), await paint(page, [background]))
}

/** Contrast of an element's text against a given ground. */
export async function textOn(
  element: Locator,
  ground: string,
): Promise<number> {
  const color = await element.evaluate((node) => getComputedStyle(node).color)
  const page = element.page()
  return ratio(await paint(page, [ground, color]), await paint(page, [ground]))
}

/** How far a ground's lightness moves once a translucent layer covers it. */
export async function demotion(
  page: Page,
  ground: string,
  veil: string,
): Promise<number> {
  return (
    lightness(await paint(page, [ground])) -
    lightness(await paint(page, [ground, veil]))
  )
}
