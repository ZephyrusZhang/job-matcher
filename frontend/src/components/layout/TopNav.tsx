"use client"

import { Search } from "lucide-react"
import { useRouter } from "next/navigation"
import { useState, useCallback, useRef, useEffect } from "react"
import { Input } from "@/components/ui/input"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3001"

export function TopNav() {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const fetchSuggestions = useCallback(async (q: string) => {
    if (q.length < 1) {
      setSuggestions([])
      setShowSuggestions(false)
      return
    }
    try {
      const res = await fetch(`${API_BASE}/api/jobs/suggest?q=${encodeURIComponent(q)}&limit=5`)
      const data = await res.json()
      if (data.success && data.data.length > 0) {
        setSuggestions(data.data)
        setShowSuggestions(true)
      } else {
        setSuggestions([])
        setShowSuggestions(false)
      }
    } catch {
      setSuggestions([])
    }
  }, [])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setQuery(val)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => fetchSuggestions(val), 300)
  }

  const handleSearch = (searchQuery: string) => {
    if (!searchQuery.trim()) return
    setShowSuggestions(false)
    router.push(`/jobs?search=${encodeURIComponent(searchQuery.trim())}`)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch(query)
    if (e.key === "Escape") setShowSuggestions(false)
  }

  // Close suggestions on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => {
      document.removeEventListener("mousedown", handler)
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  return (
    <header className="flex h-14 items-center gap-4 border-b border-border-default bg-bg-secondary px-4 shrink-0">
      <span className="text-text-primary font-semibold text-base whitespace-nowrap">
        JobMatcher
      </span>

      <div className="flex-1 max-w-lg mx-auto" ref={containerRef}>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
          <Input
            value={query}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
            placeholder="搜索岗位..."
            className="pl-9 bg-bg-tertiary border-none text-text-primary placeholder:text-text-muted rounded-[var(--radius-sm)] h-9"
          />

          {showSuggestions && suggestions.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-bg-elevated border border-border-default rounded-[var(--radius-sm)] z-50 shadow-lg">
              <div className="py-2">
                <p className="px-3 py-1 text-xs text-text-muted">搜索建议</p>
                {suggestions.map((s) => (
                  <button
                    key={s}
                    className="w-full text-left px-3 py-2 text-sm text-text-primary hover:bg-bg-tertiary cursor-pointer"
                    onClick={() => {
                      setQuery(s)
                      handleSearch(s)
                    }}
                  >
                    {s}
                  </button>
                ))}
                <p className="px-3 py-1 text-xs text-text-muted">
                  按 Enter 搜索全部结果
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="w-20" />
    </header>
  )
}
