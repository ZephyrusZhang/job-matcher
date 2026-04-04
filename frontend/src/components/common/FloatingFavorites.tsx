"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Star, MapPin, X, GripVertical } from "lucide-react"
import { JobDetailPanel } from "@/components/jobs/JobDetailPanel"
import { CATEGORY_COLORS } from "@/lib/constants"
import type { FavoriteItem } from "@/types/favorite"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3001"

export function FloatingFavorites() {
  const [isOpen, setIsOpen] = useState(false)
  const [favorites, setFavorites] = useState<FavoriteItem[]>([])
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set())
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  // Drag state
  const [pos, setPos] = useState({ x: 24, y: 24 }) // distance from bottom-right
  const [isDragging, setIsDragging] = useState(false)
  const dragStart = useRef({ mouseX: 0, mouseY: 0, posX: 0, posY: 0 })
  const hasMoved = useRef(false)

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
    const handler = () => fetchFavorites()
    window.addEventListener("favorites-changed", handler)
    return () => window.removeEventListener("favorites-changed", handler)
  }, [])

  useEffect(() => {
    if (isOpen) fetchFavorites()
  }, [isOpen])

  // Drag handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
    hasMoved.current = false
    dragStart.current = { mouseX: e.clientX, mouseY: e.clientY, posX: pos.x, posY: pos.y }
  }, [pos])

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      const dx = dragStart.current.mouseX - e.clientX
      const dy = dragStart.current.mouseY - e.clientY
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) hasMoved.current = true

      const newX = Math.max(8, Math.min(window.innerWidth - 120, dragStart.current.posX + dx))
      const newY = Math.max(8, Math.min(window.innerHeight - 60, dragStart.current.posY + dy))
      setPos({ x: newX, y: newY })
    }

    const handleMouseUp = () => {
      setIsDragging(false)
    }

    document.addEventListener("mousemove", handleMouseMove)
    document.addEventListener("mouseup", handleMouseUp)
    return () => {
      document.removeEventListener("mousemove", handleMouseMove)
      document.removeEventListener("mouseup", handleMouseUp)
    }
  }, [isDragging])

  const handleButtonClick = () => {
    if (!hasMoved.current) setIsOpen(!isOpen)
  }

  const handleRemove = async (jobId: string) => {
    setFavorites((prev) => prev.filter((f) => f.job_id !== jobId))
    setFavoriteIds((prev) => { const next = new Set(prev); next.delete(jobId); return next })
    await fetch(`${API_BASE}/api/favorites/${jobId}`, { method: "DELETE" })
    window.dispatchEvent(new Event("favorites-changed"))
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

  const grouped = favorites.reduce<Record<string, FavoriteItem[]>>((acc, f) => {
    const key = f.company_name
    if (!acc[key]) acc[key] = []
    acc[key].push(f)
    return acc
  }, {})

  return (
    <>
      {/* Floating Draggable Button */}
      <div
        className="fixed z-40 select-none"
        style={{ right: pos.x, bottom: pos.y }}
      >
        <div
          onMouseDown={handleMouseDown}
          onClick={handleButtonClick}
          className={`flex items-center gap-2 bg-neutral-900 text-white border border-neutral-700 rounded-full px-4 py-3 font-medium text-sm shadow-lg hover:bg-neutral-800 transition-colors ${isDragging ? "cursor-grabbing" : "cursor-grab"}`}
        >
          <GripVertical className="h-3.5 w-3.5 text-neutral-500" />
          <Star className="h-4 w-4 fill-current text-yellow-500" />
          收藏
          {favorites.length > 0 && (
            <span className="bg-white text-black text-xs font-semibold rounded-full min-w-[20px] h-5 flex items-center justify-center px-1.5">
              {favorites.length}
            </span>
          )}
        </div>
      </div>

      {/* Favorites Panel */}
      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/30"
            onClick={() => setIsOpen(false)}
          />

          <div
            className="fixed z-50 w-[calc(100vw-32px)] sm:w-[380px] max-h-[70vh] bg-neutral-950 border border-neutral-800 rounded-lg shadow-xl flex flex-col overflow-hidden"
            style={{ right: Math.min(pos.x, 16), bottom: pos.y + 52 }}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-800 shrink-0">
              <h3 className="text-sm font-medium text-white flex items-center gap-2">
                <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                收藏的岗位（{favorites.length}）
              </h3>
              <button onClick={() => setIsOpen(false)} className="text-neutral-500 hover:text-white cursor-pointer">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-4" style={{ scrollbarWidth: "thin", scrollbarColor: "#262626 transparent" }}>
              {favorites.length === 0 ? (
                <div className="flex flex-col items-center py-8 gap-2">
                  <Star className="h-8 w-8 text-neutral-600" />
                  <p className="text-sm text-neutral-500">暂无收藏</p>
                  <p className="text-xs text-neutral-600">在岗位总览页浏览并收藏感兴趣的岗位</p>
                </div>
              ) : (
                Object.entries(grouped).map(([company, jobs]) => (
                  <div key={company} className="space-y-2">
                    <p className="text-xs text-neutral-400 font-medium px-1">{company}（{jobs.length}）</p>
                    {jobs.map((job) => (
                      <div
                        key={job.job_id}
                        className="bg-black border border-neutral-800 rounded-lg p-3 space-y-1.5 hover:border-neutral-600 transition-colors cursor-pointer"
                        onClick={() => handleCardClick(job.job_id)}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-sm text-white font-medium line-clamp-2 leading-snug flex-1">
                            {job.title}
                          </p>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleRemove(job.job_id) }}
                            className="shrink-0 p-0.5 rounded text-neutral-600 hover:text-red-400 hover:bg-red-400/10 transition-colors cursor-pointer"
                            title="取消收藏"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-neutral-500">
                          {job.location && (
                            <span className="flex items-center gap-1">
                              <MapPin className="h-3 w-3 shrink-0" />
                              {job.location}
                            </span>
                          )}
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${CATEGORY_COLORS[job.category] || "bg-neutral-800 text-neutral-400"}`}>
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
