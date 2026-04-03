"use client"

import { Star, MapPin, Clock } from "lucide-react"
import type { Job } from "@/types/job"
import { cn } from "@/lib/utils"
import { CATEGORY_COLORS } from "@/lib/constants"

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
        "bg-neutral-950 border border-neutral-800 rounded-lg overflow-hidden",
        "hover:border-neutral-600 cursor-pointer transition-colors",
        "p-4 flex flex-col gap-2.5 h-[160px]"
      )}
      onClick={() => onClick(job.id)}
    >
      {/* Header: company name + favorite */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs text-neutral-500">{job.company.name}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${CATEGORY_COLORS[job.category] || "bg-neutral-800 text-neutral-400"}`}>
            {job.category}
          </span>
        </div>
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
                ? "fill-yellow-500 text-yellow-500"
                : "text-text-muted hover:text-yellow-500"
            )}
          />
        </button>
      </div>

      {/* Title */}
      <h3 className="text-sm text-text-primary font-medium line-clamp-2 leading-snug">
        {job.title}
      </h3>

      {/* Location + Job Type (same row) */}
      {(job.location || job.job_type) && (
        <div className="flex items-center gap-3 text-xs text-neutral-500">
          {job.location && (
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3 shrink-0" />
              {job.location}
            </span>
          )}
          {job.job_type && (
            <span className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${job.job_type === "intern" ? "bg-blue-400" : job.job_type === "fulltime" ? "bg-emerald-400" : "bg-neutral-500"}`} />
              {job.job_type === "intern" ? "实习" : job.job_type === "fulltime" ? "全职" : job.job_type === "parttime" ? "兼职" : "合同工"}
            </span>
          )}
        </div>
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
