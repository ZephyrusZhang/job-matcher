import { apiGet } from './client'
import type { ChatHistory, ChatRequest } from '@/types/chat'
import type { SSEEvent } from '@/lib/sse'
import { consumeSSE } from '@/lib/sse'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3001'

export function getChatHistory(reportId: string) {
  return apiGet<ChatHistory>(`/api/chat/${reportId}`)
}

export function sendMessage(request: ChatRequest): AsyncGenerator<SSEEvent> {
  return consumeSSE(`${API_BASE}/api/chat`, request)
}
