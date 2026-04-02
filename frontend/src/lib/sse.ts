export interface SSEEvent {
  event: string
  data: any
}

export async function* consumeSSE(
  url: string,
  body: unknown,
): AsyncGenerator<SSEEvent> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null)
    throw new Error(
      errorBody?.error?.message ?? `SSE request failed with status ${res.status}`,
    )
  }

  if (!res.body) {
    throw new Error('Response body is null')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      const events = buffer.split('\n\n')
      // Keep the last incomplete chunk in the buffer
      buffer = events.pop() ?? ''

      for (const eventBlock of events) {
        if (!eventBlock.trim()) continue

        let event = 'message'
        let data = ''

        for (const line of eventBlock.split('\n')) {
          if (line.startsWith('event:')) {
            event = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            data = line.slice(5).trim()
          }
        }

        if (data) {
          let parsed: any
          try {
            parsed = JSON.parse(data)
          } catch {
            parsed = data
          }
          yield { event, data: parsed }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
