import { createHmac } from "node:crypto"
import http from "node:http"
import type { AddressInfo } from "node:net"

export interface Received {
  headers: http.IncomingHttpHeaders
  body: string
}

/**
 * A webhook receiver of the spec's own: a small HTTP server in the test
 * process, answering with the status the test sets and keeping what it was
 * sent. It is not part of the product.
 *
 * It listens on the loopback address and picks its own port. Taskly's backend
 * reaches it there because the backend runs on the same host as the tests
 * locally and, in CI, shares a network with the Playwright container
 * (compose.override.yml). Taskly refuses loopback addresses unless
 * `OUTBOUND_ALLOW_PRIVATE_ADDRESSES` is on (FR-11.3), which the end-to-end
 * backend sets.
 */
export async function startReceiver(status = 200) {
  const received: Received[] = []
  let answer = status

  const server = http.createServer((request, response) => {
    const chunks: Buffer[] = []
    request.on("data", (chunk: Buffer) => chunks.push(chunk))
    request.on("end", () => {
      received.push({
        headers: request.headers,
        body: Buffer.concat(chunks).toString("utf8"),
      })
      response.writeHead(answer, { "content-type": "text/plain" })
      response.end(answer < 300 ? "ok" : "refused")
    })
  })
  await new Promise<void>((resolve) =>
    server.listen(0, "127.0.0.1", () => resolve()),
  )
  const { port } = server.address() as AddressInfo

  return {
    /** The address to give a webhook; `path` tells receivers apart. */
    url: (path = "/hook") => `http://127.0.0.1:${port}${path}`,
    received,
    /** Answer with this status from now on. */
    answerWith: (next: number) => {
      answer = next
    },
    close: () =>
      new Promise<void>((resolve) => {
        server.closeAllConnections()
        server.close(() => resolve())
      }),
  }
}

/**
 * Whether a delivery's signature is the one `secret` makes of it: HMAC-SHA256
 * over the timestamp, a dot and the body, as the API's contract describes.
 */
export function signedWith(secret: string, delivery: Received): boolean {
  const timestamp = String(delivery.headers["x-taskly-timestamp"])
  const expected = `sha256=${createHmac("sha256", secret)
    .update(`${timestamp}.${delivery.body}`)
    .digest("hex")}`
  return delivery.headers["x-taskly-signature"] === expected
}
