import { createHash, randomUUID } from "node:crypto"
import http from "node:http"
import type { AddressInfo } from "node:net"

export interface StubDocument {
  id: number
  title: string
  checksum: string
  tags: number[]
  notes: string[]
  bytes: Buffer
}

/** The token the stub accepts, unless a test asks for another. */
export const STUB_TOKEN = "stub-paperless-token"

interface Part {
  name: string
  filename?: string
  body: Buffer
}

/** The parts of a multipart body: enough for the one upload Taskly makes. */
function multipart(body: Buffer, contentType: string): Part[] {
  const boundary = /boundary=(?:"([^"]+)"|([^;]+))/.exec(contentType)
  if (!boundary) return []
  const delimiter = Buffer.from(`--${boundary[1] ?? boundary[2]}`)
  const parts: Part[] = []
  let at = body.indexOf(delimiter)
  while (at !== -1) {
    const start = at + delimiter.length
    // The closing delimiter is `--` after the boundary.
    if (body.subarray(start, start + 2).toString() === "--") break
    const next = body.indexOf(delimiter, start)
    if (next === -1) break
    // Between the delimiters: CRLF, headers, a blank line, the content, CRLF.
    const part = body.subarray(start + 2, next - 2)
    const split = part.indexOf("\r\n\r\n")
    const headers = part.subarray(0, split).toString()
    const name = /name="([^"]*)"/.exec(headers)?.[1]
    if (name) {
      parts.push({
        name,
        filename: /filename="([^"]*)"/.exec(headers)?.[1],
        body: part.subarray(split + 4),
      })
    }
    at = next
  }
  return parts
}

/**
 * A stand-in for a Paperless-ngx of the spec's own: a small HTTP server in the
 * test process that answers the few calls Taskly makes, and keeps what it was
 * given so a test can say what Paperless now holds. It is not part of the
 * product.
 *
 * The calls are the ones `backend/app/paperless.py` makes: a look for a
 * document by checksum, the `Taskly` tag, the upload, the consumption task,
 * the tag and the note on the document, and the download of the original. A
 * file uploaded is consumed at once, so the document exists by the first look.
 *
 * It listens on the loopback address and picks its own port. Taskly's backend
 * reaches it there because the backend runs on the same host as the tests
 * locally and, in CI, shares a network with the Playwright container
 * (compose.override.yml). Taskly refuses loopback addresses unless
 * `OUTBOUND_ALLOW_PRIVATE_ADDRESSES` is on (FR-04.4), which the end-to-end
 * backend sets.
 */
export async function startPaperlessStub(token = STUB_TOKEN) {
  const documents: StubDocument[] = []
  const tags: { id: number; name: string }[] = []
  const consumed = new Map<string, number>()
  const requests: string[] = []

  const server = http.createServer((request, response) => {
    const chunks: Buffer[] = []
    request.on("data", (chunk: Buffer) => chunks.push(chunk))
    request.on("end", () => {
      const body = Buffer.concat(chunks)
      const url = new URL(request.url ?? "/", "http://stub")
      requests.push(`${request.method} ${url.pathname}`)

      const send = (
        status: number,
        data: unknown,
        type = "application/json",
      ) => {
        const payload = Buffer.isBuffer(data) ? data : JSON.stringify(data)
        response.writeHead(status, { "content-type": type })
        response.end(payload)
      }
      const json = () => JSON.parse(body.toString() || "{}")
      const results = (list: unknown[]) =>
        send(200, { count: list.length, results: list })

      if (request.headers.authorization !== `Token ${token}`) {
        return send(401, { detail: "Invalid token." })
      }

      const path = url.pathname
      const method = request.method
      const document = /^\/api\/documents\/(\d+)\/(.*)$/.exec(path)

      if (path === "/api/documents/" && method === "GET") {
        const checksum = url.searchParams.get("checksum__iexact")
        return results(
          checksum
            ? documents.filter(
                (d) => d.checksum.toLowerCase() === checksum.toLowerCase(),
              )
            : documents,
        )
      }
      if (path === "/api/tags/" && method === "GET") {
        const name = url.searchParams.get("name__iexact")?.toLowerCase()
        return results(
          tags.filter((tag) => !name || tag.name.toLowerCase() === name),
        )
      }
      if (path === "/api/tags/" && method === "POST") {
        const tag = { id: tags.length + 1, name: json().name as string }
        tags.push(tag)
        return send(201, tag)
      }
      if (path === "/api/documents/post_document/" && method === "POST") {
        const parts = multipart(body, request.headers["content-type"] ?? "")
        const file = parts.find((part) => part.name === "document")
        if (!file) return send(400, { detail: "No document." })
        const id = documents.length + 1
        documents.push({
          id,
          title:
            parts.find((part) => part.name === "title")?.body.toString() ??
            file.filename ??
            "",
          checksum: createHash("md5").update(file.body).digest("hex"),
          tags: parts
            .filter((part) => part.name === "tags")
            .map((part) => Number(part.body.toString())),
          notes: [],
          bytes: file.body,
        })
        const task = randomUUID()
        consumed.set(task, id)
        return send(200, task)
      }
      if (path === "/api/tasks/" && method === "GET") {
        const id = consumed.get(url.searchParams.get("task_id") ?? "")
        return results(
          id === undefined
            ? []
            : [
                {
                  status: "SUCCESS",
                  result: `Success. New document id ${id} created`,
                  related_document: String(id),
                },
              ],
        )
      }
      if (document) {
        const found = documents.find((d) => d.id === Number(document[1]))
        if (!found) return send(404, { detail: "Not found." })
        const rest = document[2]
        if (rest === "" && method === "GET") {
          return send(200, {
            id: found.id,
            title: found.title,
            tags: found.tags,
          })
        }
        if (rest === "" && method === "PATCH") {
          found.tags = json().tags
          return send(200, { id: found.id, tags: found.tags })
        }
        if (rest === "notes/" && method === "GET") {
          return results(found.notes.map((note) => ({ note })))
        }
        if (rest === "notes/" && method === "POST") {
          found.notes.push(json().note)
          return results(found.notes.map((note) => ({ note })))
        }
        if (rest === "download/" && method === "GET") {
          return send(200, found.bytes, "application/pdf")
        }
      }
      return send(404, { detail: `The stub has no ${method} ${path}.` })
    })
  })
  await new Promise<void>((resolve) =>
    server.listen(0, "127.0.0.1", () => resolve()),
  )
  const { port } = server.address() as AddressInfo

  return {
    /** The address to give Taskly. */
    url: `http://127.0.0.1:${port}`,
    /** The token the stub accepts. */
    token,
    /** What Paperless now holds, in the order it was sent. */
    documents,
    /** The `Taskly` tag, once made. */
    tags,
    /** Every call it answered, as `METHOD /path`. */
    requests,
    close: () =>
      new Promise<void>((resolve) => {
        server.closeAllConnections()
        server.close(() => resolve())
      }),
  }
}
