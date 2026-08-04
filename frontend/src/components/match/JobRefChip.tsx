"use client"

import { useJob } from "@/lib/jobCache"
import { useJobDrawerStore } from "@/store/useJobDrawerStore"

interface JobRefChipProps {
  id: string
}

/**
 * The inline form of a `:job[...]` citation, rendered where the marker sat in
 * the middle of a sentence.
 *
 * Everything here is inline-level: the chip lives inside a `<p>`, so it must
 * never introduce block elements. It opens the drawer like the block card
 * does, but carries no separate link icon — at this size that would cost more
 * in clutter than it saves, and the drawer already offers 原始链接.
 */
export function JobRefChip({ id }: JobRefChipProps) {
  const { job, state } = useJob(id)
  const openDrawer = useJobDrawerStore((s) => s.open)

  if (state === "loading") {
    return (
      <span className="mx-0.5 inline-block h-[1.15em] w-24 animate-pulse rounded bg-bg-tertiary align-text-bottom" />
    )
  }

  if (state === "missing" || !job) {
    return <span className="mx-0.5 text-xs text-text-muted">（岗位已下架）</span>
  }

  return (
    <button
      type="button"
      onClick={() => openDrawer(job.id)}
      className="mx-0.5 inline-flex cursor-pointer items-baseline gap-1 rounded bg-bg-tertiary px-1.5 py-0.5 text-[0.9em] text-text-primary transition-colors hover:bg-bg-secondary"
    >
      <span>{job.title}</span>
      {job.company?.name && (
        <span className="text-text-muted">· {job.company.name}</span>
      )}
    </button>
  )
}
