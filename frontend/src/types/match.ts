export type ScopeMode = "companies" | "favorites"

export interface MatchScope {
  mode: ScopeMode
  company_ids: string[]
}

/**
 * One entry in an assistant turn's reasoning trace.
 *
 * `narration` steps are the model thinking out loud; `tool` steps carry the
 * call, its arguments, and the observation the model read back. They are kept
 * in one ordered array because the agent interleaves them.
 */
export interface TraceStep {
  type: "narration" | "tool"
  index: number
  content?: string
  call_id?: string | null
  name?: string | null
  label?: string
  args?: Record<string, unknown> | string | null
  ok?: boolean
  summary?: string
  observation?: string
  count?: number | null
  duration_ms?: number | null
  /** Set while the tool is still running; never persisted. */
  pending?: boolean
}

export interface MatchMessage {
  id: string
  session_id: string
  role: "user" | "assistant"
  /** Assistant narration between tool calls — not the deliverable. */
  content: string
  /** The `final_answer` payload, rendered as the message body. */
  final_answer: string | null
  scope: MatchScope | null
  resume_id: string | null
  steps: TraceStep[]
  job_ids: string[]
  created_at: string
}

export interface Conversation {
  id: string
  title: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface SendMessagePayload {
  content: string
  scope: MatchScope
  resume_id?: string | null
}

export interface ResumeSummary {
  id: string
  label: string
  filename: string
  is_default: boolean
  uploaded_at: string
}
