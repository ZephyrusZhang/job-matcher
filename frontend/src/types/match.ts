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

/**
 * How far a turn got.
 *
 * `running` means a live run is still writing the row and the client should
 * subscribe; `interrupted` means a backend restart stranded it, so there is
 * nothing left to subscribe to.
 */
export type TurnStatus =
  | "running"
  | "completed"
  | "stopped"
  | "failed"
  | "interrupted"

/** The complete state of a turn as of `seq` — a value, not a delta. */
export interface MatchSnapshot {
  message_id: string | null
  seq: number
  status: TurnStatus
  steps: TraceStep[]
  final_answer: string
  job_ids: string[]
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
  /**
   * Jobs the turn recommended, parsed server-side from the answer's `:job[…]`
   * markers. Kept as a record — the cards themselves render inline, so nothing
   * in the UI reads this.
   */
  job_ids: string[]
  status: TurnStatus
  /** Frames folded into this row so far — the resume anchor. */
  seq: number
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
