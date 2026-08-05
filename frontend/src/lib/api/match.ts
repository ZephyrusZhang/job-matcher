import type {
  Conversation,
  MatchMessage,
  SendMessagePayload,
} from "@/types/match"
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

/**
 * Submit a turn. Returns once the agent is scheduled — the answer arrives on
 * the subscription, not here, so this request is never retried.
 */
export function sendMessage(sessionId: string, payload: SendMessagePayload) {
  return apiPost<{ message_id: string }>(
    `/api/match/conversations/${sessionId}/messages`,
    payload,
  )
}

/** Stop the in-flight turn. Idempotent when nothing is running. */
export function stopTurn(sessionId: string) {
  return apiPost<null>(`/api/match/conversations/${sessionId}/stop`, {})
}

/** SSE subscription for the current turn — consumed via `lib/sse.ts`. */
export function streamUrl(sessionId: string) {
  return `${API_BASE}/api/match/conversations/${sessionId}/stream`
}
