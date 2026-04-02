import { useState, useRef, useCallback } from 'react'
import { consumeSSE } from '@/lib/sse'

interface SSEState {
  content: string
  isStreaming: boolean
  reportId: string | null
}

export function useSSE() {
  const [state, setState] = useState<SSEState>({
    content: '',
    isStreaming: false,
    reportId: null,
  })
  const abortRef = useRef(false)

  const start = useCallback(async (url: string, body: unknown) => {
    abortRef.current = false
    setState({ content: '', isStreaming: true, reportId: null })

    try {
      const stream = consumeSSE(url, body)

      for await (const event of stream) {
        if (abortRef.current) break

        switch (event.event) {
          case 'report_start':
          case 'compare_start':
          case 'chat_start':
            setState((prev) => ({
              ...prev,
              reportId: event.data?.report_id ?? event.data?.id ?? null,
            }))
            break

          case 'chunk':
            setState((prev) => ({
              ...prev,
              content: prev.content + (event.data?.content ?? event.data ?? ''),
            }))
            break

          case 'report_end':
          case 'compare_end':
          case 'chat_end':
            setState((prev) => ({ ...prev, isStreaming: false }))
            break
        }
      }

      // Stream finished naturally
      setState((prev) => ({ ...prev, isStreaming: false }))
    } catch (error) {
      setState((prev) => ({ ...prev, isStreaming: false }))
      throw error
    }
  }, [])

  const stop = useCallback(() => {
    abortRef.current = true
    setState((prev) => ({ ...prev, isStreaming: false }))
  }, [])

  const reset = useCallback(() => {
    abortRef.current = true
    setState({ content: '', isStreaming: false, reportId: null })
  }, [])

  return {
    content: state.content,
    isStreaming: state.isStreaming,
    reportId: state.reportId,
    start,
    stop,
    reset,
  }
}
