"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { subscribeSSE } from "@/lib/sse"
import {
  listMessages,
  sendMessage,
  stopTurn,
  streamUrl,
} from "@/lib/api/match"
import { MatchTurnAccumulator } from "@/lib/matchAccumulator"
import type {
  MatchMessage,
  SendMessagePayload,
  TraceStep,
  TurnStatus,
} from "@/types/match"

/** Server heartbeat is 15s; give it slack before calling the socket dead. */
const IDLE_TIMEOUT_MS = 30_000

/** Backoff for reconnecting a subscription that dropped mid-turn. */
const RETRY_DELAYS_MS = [500, 1000, 2000, 4000]

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** The subscription currently driving the UI, and which turn it belongs to. */
interface Watch {
  sessionId: string
  controller: AbortController
}

/**
 * Drives one conversation: loads history, watches the running turn, sends.
 *
 * Submitting and watching are separate requests, so this hook never has to ask
 * whether a stream is safe to reopen — it always is. A turn is folded by a
 * `MatchTurnAccumulator`, and every server snapshot replaces that accumulator
 * outright rather than being merged into it.
 *
 * A subscription belongs to a **specific** conversation, not to the hook. The
 * sidebar switches conversations without unmounting, so a session-agnostic
 * "is a stream alive" flag would both leave the old conversation's stream
 * running and block the new one from starting.
 *
 * The last assistant message is rendered from the accumulator whenever it is
 * live, and is therefore dropped from `messages` to avoid rendering it twice.
 */
export function useMatchChat() {
  const [messages, setMessages] = useState<MatchMessage[]>([])
  const [finalAnswer, setFinalAnswer] = useState("")
  const [steps, setSteps] = useState<TraceStep[]>([])
  const [status, setStatus] = useState<TurnStatus>("completed")
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const accRef = useRef<MatchTurnAccumulator | null>(null)
  const watchRef = useRef<Watch | null>(null)
  const sessionRef = useRef<string | null>(null)
  const loadRef = useRef<(sessionId: string) => Promise<void>>(async () => {})

  const flush = useCallback((sessionId: string) => {
    // A late frame from a conversation the user already left must not paint
    // over the one they are looking at.
    if (sessionRef.current !== sessionId) return
    const acc = accRef.current
    if (!acc) return
    const next = acc.toState()
    setSteps(next.steps)
    setFinalAnswer(next.finalAnswer)
    setStatus(next.status)
  }, [])

  const resetTurn = useCallback(() => {
    accRef.current = null
    setFinalAnswer("")
    setSteps([])
    setStatus("completed")
    setError(null)
  }, [])

  /** Drop the current subscription. The run keeps going server-side. */
  const stopWatching = useCallback(() => {
    watchRef.current?.controller.abort()
    watchRef.current = null
    setIsStreaming(false)
  }, [])

  /**
   * Watch one conversation's current turn.
   *
   * The first frame is a full snapshot, so this is the same code path for a
   * fresh send, a page reload, a conversation switch, and a dropped
   * connection — no offset is sent and none is needed.
   */
  const watch = useCallback(
    async (sessionId: string) => {
      if (watchRef.current?.sessionId === sessionId) return
      stopWatching()

      const self: Watch = { sessionId, controller: new AbortController() }
      watchRef.current = self
      setIsStreaming(true)

      let attempt = 0
      try {
        while (!self.controller.signal.aborted) {
          let terminal = false

          try {
            for await (const frame of subscribeSSE(streamUrl(sessionId), {
              signal: self.controller.signal,
              idleTimeoutMs: IDLE_TIMEOUT_MS,
            })) {
              if (watchRef.current !== self) return
              attempt = 0

              if (frame.event === "snapshot") {
                accRef.current = MatchTurnAccumulator.fromSnapshot(frame.data)
                flush(sessionId)
                if (frame.data.status !== "running") terminal = true
                continue
              }
              if (frame.event === "error") {
                setError(frame.data?.message ?? "生成失败")
                continue
              }

              accRef.current?.push(frame.event, frame.data ?? {}, frame.seq)
              flush(sessionId)
              if (frame.event === "message_end") terminal = true
            }
          } catch (e) {
            if (self.controller.signal.aborted) return
            if (attempt >= RETRY_DELAYS_MS.length) {
              setError(e instanceof Error ? e.message : "连接中断")
              break
            }
            await delay(RETRY_DELAYS_MS[attempt++])
            continue
          }

          if (terminal) break
          // The stream closed without a terminal frame: the turn may still be
          // running, so reconnect and let the fresh snapshot decide.
          if (attempt >= RETRY_DELAYS_MS.length) break
          await delay(RETRY_DELAYS_MS[attempt++])
        }
      } finally {
        // Only settle if nothing superseded this watch — otherwise the switch
        // that replaced it has already set up the state it wants.
        if (watchRef.current === self) {
          watchRef.current = null
          setIsStreaming(false)
          // Re-read so the rendered turn matches what was stored, and so the
          // finished message rejoins `messages`.
          if (sessionRef.current === sessionId) await loadRef.current(sessionId)
        }
      }
    },
    [flush, stopWatching],
  )

  const watchFnRef = useRef(watch)
  watchFnRef.current = watch

  /**
   * Load history, and pick the turn back up when one is still running.
   *
   * Hydrating the accumulator from the stored row is not what makes the resume
   * correct — the subscription's own snapshot does that — it just avoids the
   * running turn blanking out for the round trip it takes to arrive.
   */
  const load = useCallback(
    async (sessionId: string) => {
      const alreadyWatching = watchRef.current?.sessionId === sessionId
      if (watchRef.current && !alreadyWatching) stopWatching()
      sessionRef.current = sessionId

      try {
        const res = await listMessages(sessionId)
        if (sessionRef.current !== sessionId) return

        const rows = res.data ?? []
        const last = rows[rows.length - 1]

        if (last?.role === "assistant" && last.status === "running") {
          setMessages(rows.slice(0, -1))
          // Re-seeding a live accumulator would rewind it to whatever the row
          // held; the subscription is already ahead of that.
          if (!alreadyWatching) {
            accRef.current = MatchTurnAccumulator.fromSnapshot({
              message_id: last.id,
              seq: last.seq,
              status: last.status,
              steps: last.steps,
              final_answer: last.final_answer,
            })
            flush(sessionId)
            setError(null)
            void watchFnRef.current(sessionId)
          }
        } else {
          setMessages(rows)
          if (!alreadyWatching) resetTurn()
        }
      } catch {
        if (sessionRef.current === sessionId) setMessages([])
      }
    },
    [flush, resetTurn, stopWatching],
  )

  loadRef.current = load

  const clear = useCallback(() => {
    stopWatching()
    sessionRef.current = null
    setMessages([])
    resetTurn()
  }, [resetTurn, stopWatching])

  const send = useCallback(
    async (sessionId: string, payload: SendMessagePayload) => {
      stopWatching()
      sessionRef.current = sessionId
      resetTurn()

      // Show the user's turn immediately rather than waiting for the reload.
      const optimistic: MatchMessage = {
        id: `local-${Date.now()}`,
        session_id: sessionId,
        role: "user",
        content: payload.content,
        final_answer: null,
        scope: payload.scope,
        resume_id: payload.resume_id ?? null,
        steps: [],
        job_ids: [],
        status: "completed",
        seq: 0,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, optimistic])

      try {
        await sendMessage(sessionId, payload)
      } catch (e) {
        setError(e instanceof Error ? e.message : "请求失败")
        return
      }
      await watch(sessionId)
    },
    [resetTurn, stopWatching, watch],
  )

  /** Stop both ends: the local reader and the agent behind it. */
  const stop = useCallback(async () => {
    const sessionId = sessionRef.current
    stopWatching()
    if (!sessionId) return
    try {
      await stopTurn(sessionId)
    } catch {
      // The turn may have finished on its own between click and request.
    }
    await load(sessionId)
  }, [load, stopWatching])

  /**
   * Pick a turn back up after the tab was hidden.
   *
   * A hidden tab should not reconnect — the user is not there to see it — and
   * an existing subscription for this same conversation must not be replaced.
   */
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState !== "visible") return
      const sessionId = sessionRef.current
      if (!sessionId) return
      if (watchRef.current?.sessionId === sessionId) return
      void loadRef.current(sessionId)
    }
    document.addEventListener("visibilitychange", onVisible)
    return () => document.removeEventListener("visibilitychange", onVisible)
  }, [])

  useEffect(() => stopWatching, [stopWatching])

  return {
    messages,
    finalAnswer,
    steps,
    status,
    isStreaming,
    error,
    loadHistory: load,
    clear,
    send,
    stop,
  }
}
