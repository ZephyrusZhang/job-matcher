import type { Conversation, MatchMessage } from "@/types/match"
import { apiDelete, apiGet, apiPatch, apiPost } from "./client"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3001"

export function listConversations() {
  return apiGet<Conversation[]>("/api/match/conversations")
}

export function createConversation(title = "") {
  return apiPost<Conversation>("/api/match/conversations", { title })
}

export function renameConversation(id: string, title: string) {
  return apiPatch<Conversation>(`/api/match/conversations/${id}`, { title })
}

export function deleteConversation(id: string) {
  return apiDelete<null>(`/api/match/conversations/${id}`)
}

export function listMessages(conversationId: string) {
  return apiGet<MatchMessage[]>(
    `/api/match/conversations/${conversationId}/messages`,
  )
}

/** SSE endpoint for one turn — consumed via `lib/sse.ts`, not `apiPost`. */
export function sendMessageUrl(conversationId: string) {
  return `${API_BASE}/api/match/conversations/${conversationId}/messages`
}
