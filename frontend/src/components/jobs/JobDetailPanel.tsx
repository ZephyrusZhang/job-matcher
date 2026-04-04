"use client"

import { useEffect, useState } from "react"
import { Star, ExternalLink, MapPin, ChevronDown } from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
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

function SectionTitle({ children, color = "border-zinc-500" }: { children: React.ReactNode; color?: string }) {
  return (
    <h4 className={`text-white text-sm font-medium border-l-2 ${color} pl-3`}>
      {children}
    </h4>
  )
}

function DetailContent({
  job,
  isLoading,
  isFavorited,
  onToggleFavorite,
  isMobile,
  onClose,
}: {
  job: Job | null
  isLoading: boolean
  isFavorited: boolean
  onToggleFavorite: (jobId: string) => void
  isMobile: boolean
  onClose: () => void
}) {
  const jobTypeLabel: Record<string, string> = {
    fulltime: "全职",
    intern: "实习",
    parttime: "兼职",
    contract: "合同工",
  }

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
      {/* Mobile drag handle */}
      {isMobile && (
        <div className="flex justify-center pt-2 pb-0 shrink-0">
          <button onClick={onClose} className="p-1 cursor-pointer">
            <ChevronDown className="h-5 w-5 text-neutral-600" />
          </button>
        </div>
      )}

      {/* Header */}
      <SheetHeader className="p-5 sm:p-6 pb-0">
        <p className="text-xs text-text-secondary">{job.company.name}</p>
        <SheetTitle className="text-base sm:text-lg font-medium text-text-primary">
          {job.title}
        </SheetTitle>
        <div className="flex items-center gap-2 text-sm text-text-secondary flex-wrap">
          {job.location && (
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {job.location}
            </span>
          )}
          {job.job_type && (
            <>
              <span>·</span>
              <span>{jobTypeLabel[job.job_type] ?? job.job_type}</span>
            </>
          )}
        </div>
      </SheetHeader>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-5">
        <Separator className="bg-border-subtle" />

        {job.summary && (
          <div className="space-y-2">
            <SectionTitle color="border-blue-500">职位概述</SectionTitle>
            <p className="text-sm text-text-primary leading-relaxed">{job.summary}</p>
          </div>
        )}

        <div className="space-y-2">
          <SectionTitle color="border-emerald-500">核心职责</SectionTitle>
          <p className="text-sm text-text-primary leading-relaxed whitespace-pre-line">
            {job.responsibilities}
          </p>
        </div>

        <div className="space-y-2">
          <SectionTitle color="border-orange-500">技术要求</SectionTitle>
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
            <SectionTitle color="border-violet-500">团队与产品</SectionTitle>
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
      <div className="sticky bottom-0 bg-neutral-950 border-t border-neutral-800 p-3 sm:p-4 flex gap-3">
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
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent
        side={isMobile ? "bottom" : "right"}
        showCloseButton={!isMobile}
        className={cn(
          "bg-neutral-950 p-0 flex flex-col overflow-hidden",
          isMobile
            ? "h-[64vh] rounded-t-2xl border-t border-neutral-800"
            : "w-[85vw] md:w-[45vw] md:min-w-[500px] max-w-[800px] border-l border-neutral-800"
        )}
      >
        <DetailContent
          job={job}
          isLoading={isLoading}
          isFavorited={isFavorited}
          onToggleFavorite={onToggleFavorite}
          isMobile={isMobile}
          onClose={onClose}
        />
      </SheetContent>
    </Sheet>
  )
}
