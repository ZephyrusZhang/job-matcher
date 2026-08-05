export interface SSEEvent {
  event: string
  data: any
  /** The frame's `id:` line, when the endpoint numbers its frames. */
  seq: number | null
}

export interface ConsumeOptions {
  /** Sent with the request so a caller can tear the stream down. */
  signal?: AbortSignal
  /**
   * Give up if nothing at all arrives for this long.
   *
   * A connection can die without ever reporting it — a dropped NAT mapping, a
   * peer killed without a FIN — and the reader would then block forever. The
   * server sends a comment frame on an interval, so silence past that interval
   * means the connection is gone rather than merely idle.
   */
  idleTimeoutMs?: number
}

async function* readStream(
  res: Response,
  options: ConsumeOptions,
): AsyncGenerator<SSEEvent> {
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null)
    throw new Error(
      errorBody?.error?.message ?? `SSE request failed with status ${res.status}`,
    )
  }
  if (!res.body) {
    throw new Error("Response body is null")
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  const idle = options.idleTimeoutMs
  let buffer = ""

  try {
    while (true) {
      const read = reader.read()
      const { done, value } = idle
        ? await Promise.race([
            read,
            new Promise<never>((_, reject) =>
              setTimeout(() => reject(new Error("SSE_IDLE_TIMEOUT")), idle),
            ),
          ])
        : await read

      if (done) break

      buffer += decoder.decode(value, { stream: true })

      const blocks = buffer.split("\n\n")
      // Keep the last incomplete chunk in the buffer
      buffer = blocks.pop() ?? ""

      for (const block of blocks) {
        if (!block.trim()) continue

        let event = "message"
        let data = ""
        let seq: number | null = null

        for (const line of block.split("\n")) {
          // Comment frames (`: ping`) exist only to prove the socket is alive.
          if (line.startsWith(":")) continue
          if (line.startsWith("event:")) {
            event = line.slice(6).trim()
          } else if (line.startsWith("data:")) {
            data = line.slice(5).trim()
          } else if (line.startsWith("id:")) {
            const parsed = Number(line.slice(3).trim())
            seq = Number.isFinite(parsed) ? parsed : null
          }
        }

        if (data) {
          let parsed: any
          try {
            parsed = JSON.parse(data)
          } catch {
            parsed = data
          }
          yield { event, data: parsed, seq }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/** POST a body and consume the SSE response. */
export async function* consumeSSE(
  url: string,
  body: unknown,
  options: ConsumeOptions = {},
): AsyncGenerator<SSEEvent> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: options.signal,
  })
  yield* readStream(res, options)
}

/**
 * Subscribe to an SSE endpoint with GET.
 *
 * Used for streams that only say *what to watch*, never *what to do* — those
 * can be reopened at will, which is what makes resuming possible.
 */
export async function* subscribeSSE(
  url: string,
  options: ConsumeOptions = {},
): AsyncGenerator<SSEEvent> {
  const res = await fetch(url, {
    method: "GET",
    headers: { Accept: "text/event-stream" },
    signal: options.signal,
  })
  yield* readStream(res, options)
}
