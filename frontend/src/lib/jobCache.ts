"use client"

import { useEffect, useSyncExternalStore } from "react"
import { getJob } from "@/lib/api/jobs"
import type { Job } from "@/types/job"

/**
 * Process-wide cache for jobs cited inside assistant answers.
 *
 * Cards are scattered through the message body and the body re-renders on every
 * streamed token, so each card would otherwise refetch constantly. Requests are
 * deduplicated by id and results are shared across messages and conversations —
 * a job's content does not change within a session.
 *
 * The cache is an external store rather than component state: a resolved job
 * has to reach however many cards happen to cite it, and reading it through
 * `useSyncExternalStore` keeps renders in step without a setState-in-effect.
 */
const cache = new Map<string, Job | null>()
const inflight = new Map<string, Promise<void>>()
const listeners = new Set<() => void>()

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange)
  return () => {
    listeners.delete(onChange)
  }
}

/** `undefined` = not fetched yet, `null` = fetched and gone. */
function snapshot(id: string): Job | null | undefined {
  return cache.get(id)
}

function load(id: string): void {
  if (cache.has(id) || inflight.has(id)) return

  const request = getJob(id)
    .then((res) => res.data ?? null)
    // A missing job is a settled answer, not a transient failure: the agent can
    // cite an id that has since been removed by a re-crawl.
    .catch(() => null)
    .then((job) => {
      cache.set(id, job)
      inflight.delete(id)
      for (const listener of listeners) listener()
    })

  inflight.set(id, request)
}

export type JobState = "loading" | "ready" | "missing"

export function useJob(id: string): { job: Job | null; state: JobState } {
  const entry = useSyncExternalStore(
    subscribe,
    () => snapshot(id),
    () => undefined,
  )

  useEffect(() => {
    load(id)
  }, [id])

  if (entry === undefined) return { job: null, state: "loading" }
  if (entry === null) return { job: null, state: "missing" }
  return { job: entry, state: "ready" }
}
