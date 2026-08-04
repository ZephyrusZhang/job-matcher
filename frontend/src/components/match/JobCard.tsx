"use client"

import { ExternalLink } from "lucide-react"
import { useJob } from "@/lib/jobCache"
import { useJobDrawerStore } from "@/store/useJobDrawerStore"
import { CATEGORY_COLORS, JOB_TYPE_COLORS } from "@/lib/constants"
import { cn } from "@/lib/utils"

interface JobCardProps {
  id: string
}

/**
 * The block form of a `:job[...]` citation, rendered where the marker stood
 * alone in its own paragraph.
 *
 * The card body opens the detail drawer; only the corner icon leaves for the
 * company's own posting. The link is a sibling of the button rather than a
 * child, because interactive content cannot nest inside a `<button>`.
 */
export function JobCard({ id }: JobCardProps) {
  const { job, state } = useJob(id)
  const openDrawer = useJobDrawerStore((s) => s.open)

  if (state === "loading") {
    return (
      <div className="h-[58px] animate-pulse rounded-md border border-border-subtle bg-bg-secondary" />
    )
  }

  if (state === "missing" || !job) {
    return (
      <div className="rounded-md border border-dashed border-border-subtle px-3 py-2 text-xs text-text-muted">
        岗位已下架
      </div>
    )
  }

  return (
    <div className="group relative rounded-md border border-border-subtle bg-bg-secondary transition-colors hover:border-border-default">
      <button
        type="button"
        onClick={() => openDrawer(job.id)}
        className="w-full cursor-pointer px-3 py-2 text-left"
      >
        {/* Right padding keeps the title clear of the overlaid link. */}
        <span className="line-clamp-1 pr-6 text-sm text-text-primary">{job.title}</span>
        <span className="mt-1 flex flex-wrap items-center gap-1.5 text-xs">
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
                JOB_TYPE_COLORS[job.job_type]?.badge ?? "bg-neutral-500/15 text-neutral-400",
              )}
            >
              {job.job_type}
            </span>
          )}
          <span className="text-text-muted">{job.company?.name}</span>
          {job.location?.length > 0 && (
            <span className="text-text-muted">{job.location.join(" · ")}</span>
          )}
        </span>
      </button>

      <a
        href={job.source_url}
        target="_blank"
        rel="noreferrer"
        title="打开公司招聘页"
        aria-label="打开公司招聘页"
        className="absolute right-1.5 top-1.5 rounded p-1 text-text-muted opacity-0 transition-opacity hover:bg-bg-tertiary hover:text-text-primary focus-visible:opacity-100 group-hover:opacity-100"
      >
        <ExternalLink className="h-3 w-3" />
      </a>
    </div>
  )
}
