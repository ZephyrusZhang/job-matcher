"use client"

import { useEffect, useRef } from "react"
import { ReportRenderer } from "@/components/report/ReportRenderer"
import { JobCitationCards } from "@/components/match/JobCitationCard"
import { ToolTimeline } from "@/components/match/ToolTimeline"
import { cn } from "@/lib/utils"
import type { MatchMessage, ToolEvent } from "@/types/match"

function ScopeChips({ message }: { message: MatchMessage }) {
  const scope = message.scope
  if (!scope) return null

  const labels =
    scope.mode === "favorites"
      ? ["收藏岗位"]
      : scope.company_ids.length > 0
        ? scope.company_ids
        : []

  if (labels.length === 0) return null

  return (
    <div className="mt-1.5 flex flex-wrap gap-1">
      {labels.map((label) => (
        <span
          key={label}
          className="rounded bg-bg-tertiary px-1.5 py-0.5 text-[11px] text-text-muted"
        >
          {label}
        </span>
      ))}
    </div>
  )
}

function UserBubble({ message }: { message: MatchMessage }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-lg bg-bg-tertiary px-3.5 py-2.5">
        <p className="whitespace-pre-wrap text-sm text-text-primary">{message.content}</p>
        <ScopeChips message={message} />
      </div>
    </div>
  )
}

interface AssistantTurnProps {
  narration: string
  toolEvents: ToolEvent[]
  finalAnswer: string
  jobIds: string[]
  isStreaming?: boolean
}

/**
 * One assistant turn: narration, the tool timeline, then the answer.
 *
 * Narration is the model thinking out loud between tool calls, so it renders
 * muted; the `final_answer` payload is the deliverable and gets full markdown.
 */
function AssistantTurn({
  narration,
  toolEvents,
  finalAnswer,
  jobIds,
  isStreaming = false,
}: AssistantTurnProps) {
  const hasAnything = narration || toolEvents.length > 0 || finalAnswer

  return (
    <div className="max-w-[92%]">
      {narration && (
        <p className="mb-2 whitespace-pre-wrap text-xs leading-relaxed text-text-muted">
          {narration}
        </p>
      )}

      <ToolTimeline events={toolEvents} />

      {finalAnswer ? (
        <ReportRenderer content={finalAnswer} isStreaming={isStreaming} />
      ) : (
        isStreaming &&
        !hasAnything && <p className="text-sm text-text-muted">正在思考…</p>
      )}

      {!isStreaming && jobIds.length > 0 && <JobCitationCards jobIds={jobIds} />}
    </div>
  )
}

interface ChatMessageListProps {
  messages: MatchMessage[]
  narration: string
  toolEvents: ToolEvent[]
  finalAnswer: string
  jobIds: string[]
  isStreaming: boolean
  error: string | null
}

export function ChatMessageList({
  messages,
  narration,
  toolEvents,
  finalAnswer,
  jobIds,
  isStreaming,
  error,
}: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [messages.length, finalAnswer, toolEvents.length, narration])

  return (
    <div className="space-y-5 px-4 py-6">
      {messages.map((message) =>
        message.role === "user" ? (
          <UserBubble key={message.id} message={message} />
        ) : (
          <AssistantTurn
            key={message.id}
            narration={message.content}
            toolEvents={message.tool_events}
            finalAnswer={message.final_answer ?? ""}
            jobIds={message.job_ids}
          />
        ),
      )}

      {isStreaming && (
        <AssistantTurn
          narration={narration}
          toolEvents={toolEvents}
          finalAnswer={finalAnswer}
          jobIds={jobIds}
          isStreaming
        />
      )}

      {error && (
        <div className={cn("rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2")}>
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
