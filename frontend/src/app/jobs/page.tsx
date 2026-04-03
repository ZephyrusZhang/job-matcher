"use client"

import { useEffect, useState, useCallback, useRef, Suspense } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { Inbox, SearchX, Search, X } from "lucide-react"
import { Input } from "@/components/ui/input"
import { PageContainer } from "@/components/layout/PageContainer"
import { CompanySelector } from "@/components/jobs/CompanySelector"
import { FilterBar, type Filters } from "@/components/jobs/FilterBar"
import { SortControl } from "@/components/jobs/SortControl"
import { JobCardGrid } from "@/components/jobs/JobCardGrid"
import { JobDetailPanel } from "@/components/jobs/JobDetailPanel"
import { EmptyState } from "@/components/common/EmptyState"
import { Button } from "@/components/ui/button"
import type { Job } from "@/types/job"
import type { Company } from "@/types/company"
import type { PaginationMeta } from "@/types/api"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3001"

function JobsPageContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const searchQuery = searchParams.get("search")

  // Search state
  const [searchInput, setSearchInput] = useState(searchQuery ?? "")
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const searchContainerRef = useRef<HTMLDivElement>(null)

  // State
  const [companies, setCompanies] = useState<Company[]>([])
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [pagination, setPagination] = useState<PaginationMeta | null>(null)
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set())
  const [filters, setFilters] = useState<Filters>({
    categories: [],
    location: null,
    jobType: null,
    postedWithin: null,
  })
  const [sortValue, setSortValue] = useState("posted_date_desc")
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [locations, setLocations] = useState<string[]>([])

  // Fetch companies on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/companies`)
      .then((res) => res.json())
      .then((data) => {
        if (data.success && data.data.length > 0) {
          setCompanies(data.data)
          setSelectedCompanyId(data.data[0].id)
        }
      })
  }, [])

  // Fetch favorites
  useEffect(() => {
    fetch(`${API_BASE}/api/favorites`)
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          setFavoriteIds(new Set(data.data.map((f: { job_id: string }) => f.job_id)))
        }
      })
  }, [])

  // Fetch jobs when company/filters/sort change
  const fetchJobs = useCallback(
    async (page: number = 1, append: boolean = false) => {
      if (!selectedCompanyId && !searchQuery) return
      if (page === 1) setIsLoading(true)
      else setIsLoadingMore(true)

      const [sortBy, sortOrder] = sortValue.split("_")
      const params = new URLSearchParams()
      if (selectedCompanyId && !searchQuery) params.set("company_id", selectedCompanyId)
      if (filters.categories.length > 0) params.set("category", filters.categories.join(","))
      if (filters.location) params.set("location", filters.location)
      if (filters.jobType) params.set("job_type", filters.jobType)
      if (filters.postedWithin) params.set("posted_within", filters.postedWithin)
      params.set("sort_by", sortBy === "posted" ? "posted_date" : sortBy)
      params.set("sort_order", sortOrder)
      params.set("page", String(page))
      params.set("page_size", "20")

      try {
        let url: string
        if (searchQuery) {
          params.set("q", searchQuery)
          if (selectedCompanyId) params.set("company_id", selectedCompanyId)
          url = `${API_BASE}/api/jobs/search?${params}`
        } else {
          url = `${API_BASE}/api/jobs?${params}`
        }

        const res = await fetch(url)
        const data = await res.json()
        if (data.success) {
          if (append) {
            setJobs((prev) => [...prev, ...data.data])
          } else {
            setJobs(data.data)
          }
          setPagination(data.pagination)

          // Extract unique locations for filter
          if (!append && data.data.length > 0) {
            const locs = [...new Set(data.data.map((j: Job) => j.location).filter(Boolean))] as string[]
            setLocations((prev) => {
              const merged = [...new Set([...prev, ...locs])]
              return merged.sort()
            })
          }
        }
      } finally {
        setIsLoading(false)
        setIsLoadingMore(false)
      }
    },
    [selectedCompanyId, filters, sortValue, searchQuery]
  )

  useEffect(() => {
    fetchJobs(1)
  }, [fetchJobs])

  // Handlers
  const handleCompanyChange = (id: string) => {
    setSelectedCompanyId(id)
    setFilters({ categories: [], location: null, jobType: null, postedWithin: null })
  }

  const handleLoadMore = () => {
    if (pagination && pagination.page < pagination.total_pages) {
      fetchJobs(pagination.page + 1, true)
    }
  }

  const handleToggleFavorite = async (jobId: string) => {
    const wasFavorited = favoriteIds.has(jobId)
    // Optimistic update
    setFavoriteIds((prev) => {
      const next = new Set(prev)
      if (wasFavorited) next.delete(jobId)
      else next.add(jobId)
      return next
    })

    try {
      if (wasFavorited) {
        await fetch(`${API_BASE}/api/favorites/${jobId}`, { method: "DELETE" })
      } else {
        await fetch(`${API_BASE}/api/favorites`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ job_id: jobId }),
        })
      }
    } catch {
      // Rollback
      setFavoriteIds((prev) => {
        const next = new Set(prev)
        if (wasFavorited) next.add(jobId)
        else next.delete(jobId)
        return next
      })
    }
  }

  const handleCardClick = (jobId: string) => {
    setSelectedJobId(jobId)
    setDetailOpen(true)
  }

  // Search handlers
  const fetchSuggestions = useCallback(async (q: string) => {
    if (q.length < 1) { setSuggestions([]); setShowSuggestions(false); return }
    try {
      const res = await fetch(`${API_BASE}/api/jobs/suggest?q=${encodeURIComponent(q)}&limit=5`)
      const data = await res.json()
      if (data.success && data.data.length > 0) { setSuggestions(data.data); setShowSuggestions(true) }
      else { setSuggestions([]); setShowSuggestions(false) }
    } catch { setSuggestions([]) }
  }, [])

  const handleSearchInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchInput(e.target.value)
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    searchTimerRef.current = setTimeout(() => fetchSuggestions(e.target.value), 300)
  }

  const doSearch = (q: string) => {
    if (!q.trim()) return
    setShowSuggestions(false)
    router.push(`/jobs?search=${encodeURIComponent(q.trim())}`)
  }

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) setShowSuggestions(false)
    }
    document.addEventListener("mousedown", handler)
    return () => { document.removeEventListener("mousedown", handler); if (searchTimerRef.current) clearTimeout(searchTimerRef.current) }
  }, [])

  const hasMore = pagination ? pagination.page < pagination.total_pages : false

  return (
    <PageContainer>
      <div className="space-y-[var(--gap-section)]">
        {/* Search Bar */}
        <div className="max-w-xl mx-auto" ref={searchContainerRef}>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
            <Input
              value={searchInput}
              onChange={handleSearchInput}
              onKeyDown={(e) => { if (e.key === "Enter") doSearch(searchInput); if (e.key === "Escape") setShowSuggestions(false) }}
              onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
              placeholder="搜索岗位..."
              className="pl-9 pr-9 bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 rounded-lg h-10 focus:border-neutral-600"
            />
            {searchInput && (
              <button
                onClick={() => {
                  setSearchInput("")
                  setSuggestions([])
                  setShowSuggestions(false)
                  if (searchQuery) router.push("/jobs")
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            )}
            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-bg-elevated border border-border-default rounded-[var(--radius-sm)] z-50 shadow-lg">
                <div className="py-2">
                  <p className="px-3 py-1 text-xs text-text-muted">搜索建议</p>
                  {suggestions.map((s) => (
                    <button key={s} className="w-full text-left px-3 py-2 text-sm text-text-primary hover:bg-bg-tertiary cursor-pointer" onClick={() => { setSearchInput(s); doSearch(s) }}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Search indicator */}
        {searchQuery && (
          <div className="flex items-center gap-3 text-sm text-text-secondary">
            <span>
              搜索: <span className="text-text-primary font-medium">{searchQuery}</span>
              {pagination && ` — 共 ${pagination.total} 个结果`}
            </span>
            <button
              onClick={() => { setSearchInput(""); router.push("/jobs") }}
              className="text-zinc-400 text-xs hover:text-text-primary hover:underline cursor-pointer"
            >
              清除搜索
            </button>
          </div>
        )}

        {/* Filters + Sort in one row */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            {!searchQuery && (
              <FilterBar
                filters={filters}
                locations={locations}
                onChange={(f) => setFilters(f)}
                companies={companies}
                selectedCompanyId={selectedCompanyId}
                onCompanyChange={handleCompanyChange}
              />
            )}
          </div>
          <SortControl
            value={sortValue}
            onChange={setSortValue}
          />
        </div>

        {/* Total count */}
        {pagination && pagination.total > 0 && (
          <p className="text-xs text-text-muted">共 {pagination.total} 个岗位</p>
        )}

        {/* Job Cards */}
        {!isLoading && jobs.length === 0 ? (
          searchQuery ? (
            <EmptyState
              icon={SearchX}
              title="未找到匹配的岗位"
              description="试试其他关键词"
            />
          ) : (
            <EmptyState
              icon={Inbox}
              title="暂无岗位数据"
              description="请等待系统完成采集"
            />
          )
        ) : (
          <JobCardGrid
            jobs={jobs}
            isLoading={isLoading}
            favoriteIds={favoriteIds}
            onToggleFavorite={handleToggleFavorite}
            onCardClick={handleCardClick}
          />
        )}

        {/* Load More */}
        {hasMore && (
          <div className="flex justify-center pt-4">
            <Button
              variant="outline"
              onClick={handleLoadMore}
              disabled={isLoadingMore}
              className="text-text-primary border-border-default"
            >
              {isLoadingMore ? "加载中..." : "加载更多"}
            </Button>
          </div>
        )}
        {!hasMore && jobs.length > 0 && !isLoading && (
          <p className="text-center text-text-muted text-sm">已加载全部岗位</p>
        )}

        {/* Detail Panel */}
        <JobDetailPanel
          jobId={selectedJobId}
          open={detailOpen}
          onClose={() => setDetailOpen(false)}
          isFavorited={selectedJobId ? favoriteIds.has(selectedJobId) : false}
          onToggleFavorite={handleToggleFavorite}
        />
      </div>
    </PageContainer>
  )
}

export default function JobsPage() {
  return (
    <Suspense>
      <JobsPageContent />
    </Suspense>
  )
}
