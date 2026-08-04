/** Query param naming the open conversation on /match. */
export const SESSION_PARAM = "session_id"

/** URL for a conversation, or the blank chat when `id` is null. */
export function conversationHref(id: string | null): string {
  return id ? `/match?${SESSION_PARAM}=${encodeURIComponent(id)}` : "/match"
}
