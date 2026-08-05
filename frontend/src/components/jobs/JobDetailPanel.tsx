"use client"

import { useEffect, useState } from "react"
import { Star, ExternalLink, MapPin } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import type { Job } from "@/types/job"
import { cn } from "@/lib/utils"
import { useIsMobile } from "@/hooks/useIsMobile"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3001"

interface JobDetailPanelProps {
  jobId: string | null
  open: boolean
  onClose: () => void
  isFavorited: boolean
  onToggleFavorite: (jobId: string) => void
}

function SectionTitle({ children, color = "bg-zinc-500" }: { children: React.ReactNode; color?: string }) {
  return (
    <h4 className="text-text-primary text-sm font-medium flex items-center gap-2">
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${color}`} />
      {children}
    </h4>
  )
}

function DetailContent({
  job,
  isLoading,
  isFavorited,
  onToggleFavorite,
}: {
  job: Job | null
  isLoading: boolean
  isFavorited: boolean
  onToggleFavorite: (jobId: string) => void
}) {
  if (isLoading) {
    return (
      <div className="p-5 sm:p-6 space-y-4">
        <Skeleton className="h-3 w-20 bg-bg-tertiary" />
        <Skeleton className="h-6 w-3/4 bg-bg-tertiary" />
        <Skeleton className="h-4 w-1/2 bg-bg-tertiary" />
        <Separator className="bg-border-subtle" />
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-4 w-24 bg-bg-tertiary" />
            <Skeleton className="h-16 w-full bg-bg-tertiary" />
          </div>
        ))}
      </div>
    )
  }

  if (!job) return null

  return (
    <>
      {/* Header. Right padding clears the close button in the corner. */}
      <DialogHeader className="p-5 pb-0 pr-12 sm:p-6 sm:pb-0 sm:pr-12">
        <p className="text-xs text-text-secondary">{job.company.name}</p>
        <DialogTitle className="text-base sm:text-lg font-medium text-text-primary">
          {job.title}
        </DialogTitle>
        <div className="flex items-center gap-2 text-sm text-text-secondary flex-wrap">
          {job.location && job.location.length > 0 && (
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {job.location.join(" / ")}
            </span>
          )}
          {job.job_type && (
            <>
              <span>·</span>
              <span>{job.job_type}</span>
            </>
          )}
        </div>
      </DialogHeader>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-5">
        <Separator className="bg-border-subtle" />

        {job.summary && (
          <div className="space-y-2">
            <SectionTitle color="bg-blue-500">职位概述</SectionTitle>
            <p className="text-sm text-text-primary leading-relaxed">{job.summary}</p>
          </div>
        )}

        <div className="space-y-2">
          <SectionTitle color="bg-emerald-500">核心职责</SectionTitle>
          <p className="text-sm text-text-primary leading-relaxed whitespace-pre-line">
            {job.responsibilities}
          </p>
        </div>

        <div className="space-y-2">
          <SectionTitle color="bg-orange-500">技术要求</SectionTitle>
          {job.requirements.must_have.length > 0 && (
            <div className="space-y-1.5">
              {job.requirements.must_have.map((s, i) => (
                <p key={i} className="text-sm text-text-primary leading-relaxed">{s}</p>
              ))}
            </div>
          )}
          {job.requirements.nice_to_have.length > 0 && (
            <div className="space-y-1.5 mt-2">
              {job.requirements.nice_to_have.map((s, i) => (
                <p key={i} className="text-sm text-text-secondary leading-relaxed">{s}</p>
              ))}
            </div>
          )}
        </div>

        {(job.department || job.department_product) && (
          <div className="space-y-2">
            <SectionTitle color="bg-violet-500">团队与产品</SectionTitle>
            {job.department && (
              <p className="text-sm text-text-primary">
                <span className="text-text-secondary">部门: </span>
                {job.department}
              </p>
            )}
            {job.department_product && (
              <p className="text-sm text-text-primary">
                <span className="text-text-secondary">产品: </span>
                {job.department_product}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="sticky bottom-0 bg-bg-secondary border-t border-border-default p-3 sm:p-4 flex gap-3">
        <Button
          variant="outline"
          onClick={() => onToggleFavorite(job.id)}
          className={cn(
            "flex-1",
            isFavorited
              ? "bg-yellow-500/10 text-yellow-500 border-yellow-500/30"
              : "text-text-primary border-border-default"
          )}
        >
          <Star className={cn("h-4 w-4 mr-2", isFavorited && "fill-yellow-500 text-yellow-500")} />
          {isFavorited ? "已收藏" : "收藏"}
        </Button>
        <Button
          variant="outline"
          className="flex-1 text-text-primary border-border-default"
          onClick={() => window.open(job.source_url, "_blank")}
        >
          <ExternalLink className="h-4 w-4 mr-2" />
          原始链接
        </Button>
      </div>
    </>
  )
}

export function JobDetailPanel({
  jobId,
  open,
  onClose,
  isFavorited,
  onToggleFavorite,
}: JobDetailPanelProps) {
  const [job, setJob] = useState<Job | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const isMobile = useIsMobile()

  useEffect(() => {
    if (!jobId || !open) return
    setIsLoading(true)
    fetch(`${API_BASE}/api/jobs/${jobId}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.success) setJob(data.data)
      })
      .finally(() => setIsLoading(false))
  }, [jobId, open])

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent
        className={cn(
          "flex flex-col overflow-hidden bg-neutral-950 p-0",
          // Tall enough to read a full JD without the page behind it moving,
          // but never taller than the viewport — the body scrolls instead.
          "max-h-[85vh] max-w-[min(90vw,760px)]",
          isMobile && "max-h-[80vh]",
        )}
      >
        <DetailContent
          job={job}
          isLoading={isLoading}
          isFavorited={isFavorited}
          onToggleFavorite={onToggleFavorite}
        />
      </DialogContent>
    </Dialog>
  )
}
