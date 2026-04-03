"use client"

import { useState, useEffect } from "react"
import { Star, MapPin, Briefcase, X } from "lucide-react"
import { JobDetailPanel } from "@/components/jobs/JobDetailPanel"
import type { FavoriteItem } from "@/types/favorite"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3001"

export function FloatingFavorites() {
  const [isOpen, setIsOpen] = useState(false)
  const [favorites, setFavorites] = useState<FavoriteItem[]>([])
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set())
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  const fetchFavorites = () => {
    fetch(`${API_BASE}/api/favorites`)
      .then((r) => r.json())
      .then((d) => {
        if (d.success) {
          setFavorites(d.data)
          setFavoriteIds(new Set(d.data.map((f: FavoriteItem) => f.job_id)))
        }
      })
  }

  useEffect(() => {
    fetchFavorites()
  }, [])

  // Refresh when panel opens
  useEffect(() => {
    if (isOpen) fetchFavorites()
  }, [isOpen])

  const handleRemove = async (jobId: string) => {
    setFavorites((prev) => prev.filter((f) => f.job_id !== jobId))
    setFavoriteIds((prev) => { const next = new Set(prev); next.delete(jobId); return next })
    await fetch(`${API_BASE}/api/favorites/${jobId}`, { method: "DELETE" })
  }

  const handleToggleFavorite = async (jobId: string) => {
    const was = favoriteIds.has(jobId)
    if (was) {
      await handleRemove(jobId)
    } else {
      setFavoriteIds((prev) => new Set(prev).add(jobId))
      await fetch(`${API_BASE}/api/favorites`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId }),
      })
      fetchFavorites()
    }
  }

  const handleCardClick = (jobId: string) => {
    setSelectedJobId(jobId)
    setDetailOpen(true)
  }

  // Group by company
  const grouped = favorites.reduce<Record<string, FavoriteItem[]>>((acc, f) => {
    const key = f.company_name
    if (!acc[key]) acc[key] = []
    acc[key].push(f)
    return acc
  }, {})

  return (
    <>
      {/* Floating Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 bg-neutral-900 text-white border border-neutral-700 rounded-full px-4 py-3 font-medium text-sm shadow-lg hover:bg-neutral-800 transition-colors cursor-pointer"
      >
        <Star className="h-4 w-4 fill-current text-yellow-500" />
        收藏
        {favorites.length > 0 && (
          <span className="bg-text-primary text-bg-primary text-xs font-semibold rounded-full min-w-[20px] h-5 flex items-center justify-center px-1.5">
            {favorites.length}
          </span>
        )}
      </button>

      {/* Favorites Panel */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40 bg-black/30"
            onClick={() => setIsOpen(false)}
          />

          {/* Panel */}
          <div className="fixed bottom-20 right-6 z-50 w-[380px] max-h-[70vh] bg-neutral-950 border border-neutral-800 rounded-lg shadow-xl flex flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-800 shrink-0">
              <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
                <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                收藏的岗位（{favorites.length}）
              </h3>
              <button onClick={() => setIsOpen(false)} className="text-text-muted hover:text-text-primary cursor-pointer">
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-3 space-y-4" style={{ scrollbarWidth: "thin", scrollbarColor: "var(--border-default) transparent" }}>
              {favorites.length === 0 ? (
                <div className="flex flex-col items-center py-8 gap-2">
                  <Star className="h-8 w-8 text-text-muted" />
                  <p className="text-sm text-text-muted">暂无收藏</p>
                  <p className="text-xs text-text-muted">在岗位总览页浏览并收藏感兴趣的岗位</p>
                </div>
              ) : (
                Object.entries(grouped).map(([company, jobs]) => (
                  <div key={company} className="space-y-2">
                    <p className="text-xs text-text-secondary font-medium px-1">{company}（{jobs.length}）</p>
                    {jobs.map((job) => (
                      <div
                        key={job.job_id}
                        className="bg-black border border-neutral-800 rounded-lg p-3 space-y-1.5 hover:border-zinc-600 transition-colors cursor-pointer"
                        onClick={() => handleCardClick(job.job_id)}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-sm text-text-primary font-medium line-clamp-2 leading-snug flex-1">
                            {job.title}
                          </p>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleRemove(job.job_id) }}
                            className="shrink-0 p-0.5 rounded text-text-muted hover:text-tag-red hover:bg-tag-red-bg transition-colors cursor-pointer"
                            title="取消收藏"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-text-secondary">
                          {job.location && (
                            <span className="flex items-center gap-1">
                              <MapPin className="h-3 w-3 shrink-0" />
                              {job.location}
                            </span>
                          )}
                          <span className="flex items-center gap-1">
                            <Briefcase className="h-3 w-3 shrink-0" />
                            {job.category}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}

      {/* Job Detail Drawer */}
      <JobDetailPanel
        jobId={selectedJobId}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        isFavorited={selectedJobId ? favoriteIds.has(selectedJobId) : false}
        onToggleFavorite={handleToggleFavorite}
      />
    </>
  )
}
