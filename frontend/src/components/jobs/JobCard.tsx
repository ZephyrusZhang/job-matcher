"use client"

import { Star, MapPin, Clock } from "lucide-react"
import type { Job } from "@/types/job"
import { cn } from "@/lib/utils"

interface JobCardProps {
  job: Job
  isFavorited: boolean
  onToggleFavorite: (jobId: string) => void
  onClick: (jobId: string) => void
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return ""
  const now = Date.now()
  const date = new Date(dateStr).getTime()
  const diffMs = now - date
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return "今天"
  if (diffDays === 1) return "昨天"
  if (diffDays < 7) return `${diffDays}天前`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}周前`
  return `${Math.floor(diffDays / 30)}月前`
}

export function JobCard({ job, isFavorited, onToggleFavorite, onClick }: JobCardProps) {
  return (
    <div
      className={cn(
        "bg-bg-secondary border border-border-default rounded-[var(--radius)] overflow-hidden",
        "hover:border-accent-main cursor-pointer transition-colors",
        "p-[var(--spacing-card)] flex flex-col gap-2.5"
      )}
      onClick={() => onClick(job.id)}
    >
      {/* Header: company name + favorite */}
      <div className="flex items-start justify-between">
        <span className="text-xs text-text-secondary">{job.company.name}</span>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onToggleFavorite(job.id)
          }}
          className="p-1 -m-1 shrink-0"
          aria-label={isFavorited ? "取消收藏" : "收藏"}
        >
          <Star
            className={cn(
              "h-4 w-4 transition-colors",
              isFavorited
                ? "fill-accent-main text-accent-main"
                : "text-text-secondary hover:text-accent-main"
            )}
          />
        </button>
      </div>

      {/* Title */}
      <h3 className="text-sm text-text-primary font-medium line-clamp-2 leading-snug">
        {job.title}
      </h3>

      {/* Location */}
      {job.location && (
        <div className="flex items-center gap-1 text-xs text-text-secondary">
          <MapPin className="h-3 w-3 shrink-0" />
          <span>{job.location}</span>
        </div>
      )}

      {/* Summary */}
      {job.summary && (
        <p className="text-xs text-text-muted line-clamp-2 leading-relaxed">
          {job.summary}
        </p>
      )}

      {/* Posted date */}
      {job.posted_date && (
        <div className="flex items-center gap-1 text-xs text-text-muted mt-auto">
          <Clock className="h-3 w-3 shrink-0" />
          <span>{formatRelativeTime(job.posted_date)}</span>
        </div>
      )}
    </div>
  )
}
