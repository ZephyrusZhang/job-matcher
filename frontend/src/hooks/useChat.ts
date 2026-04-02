import { useState, useCallback } from 'react'
import type { ChatMessage } from '@/types/chat'
import { getChatHistory } from '@/lib/api/chat'
import { useSSE } from './useSSE'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3001'

export function useChat(reportId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const sse = useSSE()

  const loadHistory = useCallback(async () => {
    setIsLoadingHistory(true)
    try {
      const res = await getChatHistory(reportId)
      setMessages(res.data.messages)
    } catch {
      setMessages([])
    } finally {
      setIsLoadingHistory(false)
    }
  }, [reportId])

  const sendMessage = useCallback(
    async (message: string) => {
      // Add user message to list immediately
      const userMessage: ChatMessage = {
        id: `temp-${Date.now()}`,
        role: 'user',
        content: message,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, userMessage])

      sse.reset()

      try {
        await sse.start(`${API_BASE}/api/chat`, {
          report_id: reportId,
          message,
        })

        // After stream completes, add the assistant message
        setMessages((prev) => [
          ...prev,
          {
            id: sse.reportId ?? `msg-${Date.now()}`,
            role: 'assistant' as const,
            content: sse.content,
            created_at: new Date().toISOString(),
          },
        ])
        sse.reset()
      } catch {
        // Remove the optimistic user message on failure
        setMessages((prev) => prev.filter((m) => m.id !== userMessage.id))
      }
    },
    [reportId, sse],
  )

  return {
    messages,
    isLoadingHistory,
    streamingContent: sse.content,
    isStreaming: sse.isStreaming,
    loadHistory,
    sendMessage,
    stopStreaming: sse.stop,
  }
}
