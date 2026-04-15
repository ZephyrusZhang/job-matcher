"use client"

import { Skeleton } from "@/components/ui/skeleton"
import type { Job } from "@/types/job"
import { JobCard } from "./JobCard"

interface JobCardGridProps {
  jobs: Job[]
  isLoading: boolean
  favoriteIds: Set<string>
  onToggleFavorite: (jobId: string) => void
  onCardClick: (jobId: string) => void
}

function JobCardSkeleton() {
  return (
    <div className="bg-bg-secondary border border-border-default rounded-[var(--radius)] p-[var(--spacing-card)] flex flex-col gap-3">
      <div className="flex justify-between">
        <Skeleton className="h-3 w-16 bg-bg-tertiary" />
        <Skeleton className="h-4 w-4 bg-bg-tertiary" />
      </div>
      <Skeleton className="h-5 w-3/4 bg-bg-tertiary" />
      <Skeleton className="h-3 w-20 bg-bg-tertiary" />
      <div className="flex gap-1.5">
        <Skeleton className="h-5 w-14 bg-bg-tertiary rounded-[var(--radius-xs)]" />
        <Skeleton className="h-5 w-14 bg-bg-tertiary rounded-[var(--radius-xs)]" />
        <Skeleton className="h-5 w-14 bg-bg-tertiary rounded-[var(--radius-xs)]" />
      </div>
      <Skeleton className="h-3 w-12 bg-bg-tertiary" />
    </div>
  )
}

export function JobCardGrid({
  jobs,
  isLoading,
  favoriteIds,
  onToggleFavorite,
  onCardClick,
}: JobCardGridProps) {
  if (isLoading && jobs.length === 0) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-[var(--gap-grid)]">
        {Array.from({ length: 6 }).map((_, i) => (
          <JobCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-[var(--gap-grid)]">
      {jobs.map((job, i) => (
        <JobCard
          key={job.id}
          job={job}
          isFavorited={favoriteIds.has(job.id)}
          onToggleFavorite={onToggleFavorite}
          onClick={onCardClick}
          index={i}
        />
      ))}
    </div>
  )
}
