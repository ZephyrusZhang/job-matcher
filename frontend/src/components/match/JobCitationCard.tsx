"use client"

import { useEffect, useState } from "react"
import { ExternalLink } from "lucide-react"
import { getJob } from "@/lib/api/jobs"
import { CATEGORY_COLORS, JOB_TYPE_COLORS } from "@/lib/constants"
import { cn } from "@/lib/utils"
import type { Job } from "@/types/job"

interface JobCitationCardsProps {
  jobIds: string[]
  /** Only the first few are worth showing inline. */
  limit?: number
}

/**
 * Compact cards for the jobs an assistant turn touched.
 *
 * The stream only carries ids, so details are fetched here — the agent may
 * have inspected far more jobs than it ended up recommending.
 */
export function JobCitationCards({ jobIds, limit = 6 }: JobCitationCardsProps) {
  const [jobs, setJobs] = useState<Job[]>([])

  useEffect(() => {
    let cancelled = false
    const ids = jobIds.slice(0, limit)

    // An empty list still flows through Promise.all so state is never set
    // synchronously inside the effect body.
    Promise.all(
      ids.map((id) =>
        getJob(id)
          .then((res) => res.data)
          .catch(() => null),
      ),
    ).then((results) => {
      if (!cancelled) {
        setJobs(results.filter((j): j is Job => Boolean(j)))
      }
    })

    return () => {
      cancelled = true
    }
  }, [jobIds, limit])

  if (jobs.length === 0) return null

  return (
    <div className="mt-4 space-y-1.5">
      <div className="text-xs text-text-muted">相关岗位</div>
      <div className="grid gap-1.5 sm:grid-cols-2">
        {jobs.map((job) => (
          <a
            key={job.id}
            href={job.source_url}
            target="_blank"
            rel="noreferrer"
            className="group rounded-md border border-border-subtle bg-bg-secondary px-3 py-2 transition-colors hover:border-border-default"
          >
            <div className="flex items-start justify-between gap-2">
              <span className="line-clamp-1 text-sm text-text-primary">{job.title}</span>
              <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 text-text-muted opacity-0 transition-opacity group-hover:opacity-100" />
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs">
              {job.category && (
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5",
                    CATEGORY_COLORS[job.category] ?? "bg-neutral-500/15 text-neutral-400",
                  )}
                >
                  {job.category}
                </span>
              )}
              {job.job_type && (
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5",
                    JOB_TYPE_COLORS[job.job_type]?.badge ??
                      "bg-neutral-500/15 text-neutral-400",
                  )}
                >
                  {job.job_type}
                </span>
              )}
              <span className="text-text-muted">
                {job.location?.join(" · ")}
              </span>
            </div>
          </a>
        ))}
      </div>
    </div>
  )
}
