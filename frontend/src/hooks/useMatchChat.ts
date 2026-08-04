"use client"

import { useCallback, useRef, useState } from "react"
import { consumeSSE } from "@/lib/sse"
import { listMessages, sendMessageUrl } from "@/lib/api/match"
import type {
  MatchMessage,
  SendMessagePayload,
  ToolEvent,
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
  const [narration, setNarration] = useState("")
  const [finalAnswer, setFinalAnswer] = useState("")
  const [toolEvents, setToolEvents] = useState<ToolEvent[]>([])
  const [jobIds, setJobIds] = useState<string[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const abortRef = useRef(false)

  const resetTurn = useCallback(() => {
    setNarration("")
    setFinalAnswer("")
    setToolEvents([])
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
        conversation_id: conversationId,
        role: "user",
        content: payload.content,
        final_answer: null,
        scope: payload.scope,
        resume_id: payload.resume_id ?? null,
        tool_events: [],
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
            case "narration":
              setNarration((prev) => prev + (event.data?.content ?? ""))
              break

            case "tool_start":
              setToolEvents((prev) => [
                ...prev,
                {
                  call_id: event.data.call_id,
                  name: event.data.name,
                  label: event.data.label,
                  args: event.data.args,
                  ok: true,
                  summary: "",
                  pending: true,
                },
              ])
              break

            case "tool_args":
              // Arguments stream in; the timeline shows the settled value on
              // tool_end, so nothing to merge here yet.
              break

            case "tool_end":
              setToolEvents((prev) =>
                prev.map((t) =>
                  t.call_id === event.data.call_id
                    ? {
                        ...t,
                        pending: false,
                        ok: event.data.ok ?? true,
                        summary: event.data.summary ?? "",
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
    narration,
    finalAnswer,
    toolEvents,
    jobIds,
    isStreaming,
    error,
    loadHistory,
    clear,
    send,
    stop,
  }
}
