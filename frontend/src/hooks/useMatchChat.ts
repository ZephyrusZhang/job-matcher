"use client"

import { useCallback, useRef, useState } from "react"
import { consumeSSE } from "@/lib/sse"
import { listMessages, sendMessageUrl } from "@/lib/api/match"
import type {
  MatchMessage,
  SendMessagePayload,
  TraceStep,
} from "@/types/match"

/**
 * Drives one conversation: loads history and streams each turn.
 *
 * The stream carries three interleaved things — narration, a tool timeline,
 * and the final answer — so this cannot reuse `useSSE`, whose event switch is
 * fixed to the report contract used by /compare.
 */
export function useMatchChat() {
  const [messages, setMessages] = useState<MatchMessage[]>([])
  const [finalAnswer, setFinalAnswer] = useState("")
  const [steps, setSteps] = useState<TraceStep[]>([])
  const [jobIds, setJobIds] = useState<string[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const abortRef = useRef(false)

  const resetTurn = useCallback(() => {
    setFinalAnswer("")
    setSteps([])
    setJobIds([])
    setError(null)
  }, [])

  const loadHistory = useCallback(async (conversationId: string) => {
    resetTurn()
    try {
      const res = await listMessages(conversationId)
      setMessages(res.data ?? [])
    } catch {
      setMessages([])
    }
  }, [resetTurn])

  const clear = useCallback(() => {
    setMessages([])
    resetTurn()
  }, [resetTurn])

  const send = useCallback(
    async (conversationId: string, payload: SendMessagePayload) => {
      abortRef.current = false
      resetTurn()
      setIsStreaming(true)

      // Show the user's turn immediately rather than waiting for the reload.
      const optimistic: MatchMessage = {
        id: `local-${Date.now()}`,
        session_id: conversationId,
        role: "user",
        content: payload.content,
        final_answer: null,
        scope: payload.scope,
        resume_id: payload.resume_id ?? null,
        steps: [],
        job_ids: [],
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, optimistic])

      try {
        for await (const event of consumeSSE(
          sendMessageUrl(conversationId),
          payload,
        )) {
          if (abortRef.current) break

          switch (event.event) {
            case "narration": {
              // Narration arrives token by token into a numbered slot so it
              // stays in order relative to the tool calls around it.
              const { index, content } = event.data
              setSteps((prev) => {
                const next = [...prev]
                const at = next.findIndex((s) => s.index === index)
                if (at >= 0) {
                  next[at] = { ...next[at], content: (next[at].content ?? "") + content }
                } else {
                  next.push({ type: "narration", index, content })
                }
                return next.sort((a, b) => a.index - b.index)
              })
              break
            }

            case "tool_start":
              setSteps((prev) =>
                [
                  ...prev,
                  {
                    type: "tool" as const,
                    index: event.data.index,
                    call_id: event.data.call_id,
                    name: event.data.name,
                    label: event.data.label,
                    args: event.data.args,
                    ok: true,
                    summary: "",
                    pending: true,
                  },
                ].sort((a, b) => a.index - b.index),
              )
              break

            case "tool_args":
              // Arguments stream in; the timeline shows the settled value on
              // tool_end, so nothing to merge here yet.
              break

            case "tool_end":
              setSteps((prev) =>
                prev.map((t) =>
                  t.call_id === event.data.call_id
                    ? {
                        ...t,
                        pending: false,
                        ok: event.data.ok ?? true,
                        summary: event.data.summary ?? "",
                        observation: event.data.observation ?? "",
                        count: event.data.count ?? null,
                        duration_ms: event.data.duration_ms ?? null,
                      }
                    : t,
                ),
              )
              break

            case "final_delta":
              setFinalAnswer((prev) => prev + (event.data?.content ?? ""))
              break

            case "jobs":
              setJobIds(event.data?.job_ids ?? [])
              break

            case "error":
              setError(event.data?.message ?? "生成失败")
              break

            case "message_end":
              break
          }
        }

        // Re-read from the server so the rendered turn matches what was stored.
        await loadHistory(conversationId)
      } catch (e) {
        setError(e instanceof Error ? e.message : "请求失败")
      } finally {
        setIsStreaming(false)
      }
    },
    [loadHistory, resetTurn],
  )

  const stop = useCallback(() => {
    abortRef.current = true
    setIsStreaming(false)
  }, [])

  return {
    messages,
    finalAnswer,
    steps,
    jobIds,
    isStreaming,
    error,
    loadHistory,
    clear,
    send,
    stop,
  }
}
