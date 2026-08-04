"use client"

import { useEffect, useRef } from "react"
import { MarkdownRenderer } from "@/components/match/MarkdownRenderer"
import { JobCitationCards } from "@/components/match/JobCitationCard"
import { ThinkingTrace } from "@/components/match/ThinkingTrace"
import { cn } from "@/lib/utils"
import type { MatchMessage, TraceStep } from "@/types/match"

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
  steps: TraceStep[]
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
  steps,
  finalAnswer,
  jobIds,
  isStreaming = false,
}: AssistantTurnProps) {
  const hasAnything = steps.length > 0 || finalAnswer

  return (
    <div>
      <ThinkingTrace steps={steps} isStreaming={isStreaming} />

      {finalAnswer ? (
        <MarkdownRenderer content={finalAnswer} isStreaming={isStreaming} />
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
  steps: TraceStep[]
  finalAnswer: string
  jobIds: string[]
  isStreaming: boolean
  error: string | null
}

export function ChatMessageList({
  messages,
  steps,
  finalAnswer,
  jobIds,
  isStreaming,
  error,
}: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [messages.length, finalAnswer, steps])

  return (
    <div className="mx-auto w-full max-w-3xl space-y-5 px-4 py-6">
      {messages.map((message) =>
        message.role === "user" ? (
          <UserBubble key={message.id} message={message} />
        ) : (
          <AssistantTurn
            key={message.id}
            steps={message.steps}
            finalAnswer={message.final_answer ?? ""}
            jobIds={message.job_ids}
          />
        ),
      )}

      {isStreaming && (
        <AssistantTurn
          steps={steps}
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
