"use client"

import { useEffect, useState, useCallback, useRef } from "react"
import { Separator } from "@/components/ui/separator"
import { Button } from "@/components/ui/button"
import { PageContainer } from "@/components/layout/PageContainer"
import { CompanySelector } from "@/components/jobs/CompanySelector"
import { ResumeUploader } from "./ResumeUploader"
import { PreferencesForm } from "./PreferencesForm"
import { GenerateButton } from "./GenerateButton"
import { ReportRenderer } from "./ReportRenderer"
import { JobDetailPanel } from "@/components/jobs/JobDetailPanel"
import { Star, MapPin, X, RotateCcw, Square } from "lucide-react"
import { CATEGORY_COLORS } from "@/lib/constants"
import type { Company } from "@/types/company"
import type { FavoriteSummary, FavoriteItem } from "@/types/favorite"
import type { ResumeInfo } from "@/types/resume"
import type { Report } from "@/types/report"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3001"

interface SSEEvent {
  event: string
  data: Record<string, unknown>
}

type ViewMode = "form" | "chat"

interface AnalysisPageLayoutProps {
  title: string
  description: string
  generateEndpoint: string
  reportEndpoint: string
  generateButtonLabel: string
  reportTitle: string
  startEvent: string
  endEvent: string
}

export function AnalysisPageLayout({
  title,
  description,
  generateEndpoint,
  reportEndpoint,
  generateButtonLabel,
  reportTitle,
  startEvent,
  endEvent,
}: AnalysisPageLayoutProps) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(null)
  const [favoriteSummary, setFavoriteSummary] = useState<FavoriteSummary[]>([])
  const [resume, setResume] = useState<ResumeInfo | null>(null)
  const [interest, setInterest] = useState("")
  const [additional, setAdditional] = useState("")

  const [favoritedJobs, setFavoritedJobs] = useState<FavoriteItem[]>([])
  const [detailJobId, setDetailJobId] = useState<string | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  // View mode: form or chat
  const [viewMode, setViewMode] = useState<ViewMode>("form")

  // Report state
  const [streamContent, setStreamContent] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)
  const [reportId, setReportId] = useState<string | null>(null)

  // Chat state
  const [chatMessages, setChatMessages] = useState<{ role: string; content: string }[]>([])
  const [chatInput, setChatInput] = useState("")
  const [isChatStreaming, setIsChatStreaming] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  // Fetch companies + favorites summary
  useEffect(() => {
    fetch(`${API_BASE}/api/companies`)
      .then((r) => r.json())
      .then((d) => { if (d.success) setCompanies(d.data) })
    fetch(`${API_BASE}/api/favorites/summary`)
      .then((r) => r.json())
      .then((d) => { if (d.success) setFavoriteSummary(d.data) })
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/api/resume`)
      .then((r) => r.json())
      .then((d) => { if (d.success) setResume(d.data) })
  }, [])

  const fetchFavoritedJobs = useCallback((companyId: string) => {
    fetch(`${API_BASE}/api/favorites?company_id=${companyId}`)
      .then((r) => r.json())
      .then((d) => {
        if (d.success) setFavoritedJobs(d.data)
        else setFavoritedJobs([])
      })
  }, [])

  useEffect(() => {
    if (!selectedCompanyId) { setFavoritedJobs([]); return }
    fetchFavoritedJobs(selectedCompanyId)
  }, [selectedCompanyId, fetchFavoritedJobs])

  const handleRemoveFavorite = async (jobId: string) => {
    setFavoritedJobs((prev) => prev.filter((j) => j.job_id !== jobId))
    try {
      await fetch(`${API_BASE}/api/favorites/${jobId}`, { method: "DELETE" })
      window.dispatchEvent(new Event("favorites-changed"))
      fetch(`${API_BASE}/api/favorites/summary`)
        .then((r) => r.json())
        .then((d) => { if (d.success) setFavoriteSummary(d.data) })
    } catch {
      if (selectedCompanyId) fetchFavoritedJobs(selectedCompanyId)
    }
  }

  // SSE parsing helper
  const consumeSSE = useCallback(async (url: string, body: unknown, signal?: AbortSignal) => {
    const res = await fetch(`${API_BASE}${url}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    })
    if (!res.ok || !res.body) throw new Error("SSE request failed")

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const parts = buffer.split("\n\n")
      buffer = parts.pop()!
      for (const part of parts) {
        let event = "message"
        let data = ""
        for (const line of part.split("\n")) {
          if (line.startsWith("event: ")) event = line.slice(7)
          else if (line.startsWith("data: ")) data += line.slice(6)
        }
        if (data) {
          const parsed: SSEEvent = { event, data: JSON.parse(data) }
          if (event === startEvent) {
            setReportId(parsed.data.report_id as string)
          } else if (event === "chunk") {
            setStreamContent((prev) => prev + (parsed.data.content as string))
          }
        }
      }
    }
  }, [startEvent])

  const handleGenerate = async () => {
    if (!selectedCompanyId || !interest.trim()) return

    setViewMode("chat")
    setIsGenerating(true)
    setStreamContent("")
    setChatMessages([])
    setReportId(null)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      await consumeSSE(generateEndpoint, {
        company_id: selectedCompanyId,
        preferences: { interest, additional: additional || undefined },
      }, controller.signal)
    } catch (e) {
      if ((e as Error).name === "AbortError") return // user stopped
      throw e
    } finally {
      setIsGenerating(false)
      abortRef.current = null
    }
  }

  const handleRegenerate = () => {
    setViewMode("form")
    setStreamContent("")
    setChatMessages([])
    setReportId(null)
  }

  const handleSendChat = async () => {
    if (!chatInput.trim() || !reportId || isChatStreaming) return
    const userMsg = chatInput.trim()
    setChatInput("")
    setChatMessages((prev) => [...prev, { role: "user", content: userMsg }])
    setIsChatStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller

    let assistantContent = ""
    try {
      const res = await fetch(`${API_BASE}/api/chat/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report_id: reportId, message: userMsg }),
        signal: controller.signal,
      })
      if (!res.ok || !res.body) throw new Error("Chat SSE failed")

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      setChatMessages((prev) => [...prev, { role: "assistant", content: "" }])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const parts = buffer.split("\n\n")
        buffer = parts.pop()!
        for (const part of parts) {
          let data = ""
          for (const line of part.split("\n")) {
            if (line.startsWith("data: ")) data += line.slice(6)
          }
          if (data) {
            const parsed = JSON.parse(data)
            if (parsed.content) {
              assistantContent += parsed.content
              setChatMessages((prev) => {
                const updated = [...prev]
                updated[updated.length - 1] = { role: "assistant", content: assistantContent }
                return updated
              })
            }
          }
        }
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") return
      throw e
    } finally {
      setIsChatStreaming(false)
      abortRef.current = null
    }
  }

  const handleStop = () => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsGenerating(false)
    setIsChatStreaming(false)
  }

  // Auto scroll to bottom on new messages
  useEffect(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight
    }
  }, [chatMessages, streamContent])

  const favCount = favoriteSummary.find((s) => s.company_id === selectedCompanyId)?.count ?? 0
  const isDisabled = !selectedCompanyId || !resume || favCount === 0 || !interest.trim()

  return (
    <PageContainer>
      {viewMode === "form" ? (
        /* ===== FORM VIEW ===== */
        <div className="space-y-[var(--gap-section)]">
          <div>
            <h1 className="text-xl font-medium text-white">{title}</h1>
            <p className="text-sm text-neutral-400 mt-1">{description}</p>
          </div>

          <div className="bg-neutral-950 rounded-lg border border-neutral-800 p-6 space-y-6">
            {/* Company Selector */}
            <div className="space-y-3">
              <label className="text-sm font-medium text-white">选择公司</label>
              <CompanySelector
                companies={companies}
                value={selectedCompanyId}
                onChange={setSelectedCompanyId}
                showFavoriteCount
                favoriteSummary={favoriteSummary}
              />
            </div>

            {/* Favorited Jobs */}
            {selectedCompanyId && favoritedJobs.length > 0 && (
              <div className="space-y-3">
                <label className="text-sm font-medium text-white flex items-center gap-2">
                  <Star className="h-3.5 w-3.5 text-yellow-500 fill-yellow-500" />
                  已收藏的岗位（{favoritedJobs.length}）
                </label>
                <div className="flex gap-3 overflow-x-auto pb-3 -mx-1 px-1" style={{ scrollbarWidth: "thin", scrollbarColor: "#262626 transparent" }}>
                  {favoritedJobs.map((job) => (
                    <div
                      key={job.job_id}
                      onClick={() => { setDetailJobId(job.job_id); setDetailOpen(true) }}
                      className="shrink-0 w-[240px] bg-black border border-neutral-800 rounded-lg p-3.5 space-y-2 hover:border-neutral-600 transition-colors cursor-pointer"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm text-white font-medium line-clamp-2 leading-snug flex-1">{job.title}</p>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleRemoveFavorite(job.job_id) }}
                          className="shrink-0 mt-0.5 p-0.5 rounded text-neutral-600 hover:text-red-400 hover:bg-red-400/10 transition-colors cursor-pointer"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-neutral-500">
                        {job.location && job.location.length > 0 && (
                          <span className="flex items-center gap-1 truncate">
                            <MapPin className="h-3 w-3 shrink-0" />
                            <span className="truncate">{job.location.join(" / ")}</span>
                          </span>
                        )}
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${CATEGORY_COLORS[job.category] || "bg-neutral-800 text-neutral-400"}`}>
                          {job.category}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {selectedCompanyId && favoritedJobs.length === 0 && (
              <div className="flex flex-col items-center py-4 gap-2">
                <Star className="h-8 w-8 text-neutral-700" />
                <p className="text-sm text-neutral-500">该公司暂无收藏岗位</p>
                <p className="text-xs text-neutral-600">请先在岗位总览页收藏感兴趣的岗位</p>
              </div>
            )}

            <Separator className="bg-neutral-800" />

            {/* Resume */}
            <div className="space-y-3">
              <label className="text-sm font-medium text-white">上传简历</label>
              <ResumeUploader
                resume={resume}
                onUploadSuccess={(r) => setResume(r)}
              />
            </div>

            <Separator className="bg-neutral-800" />

            {/* Preferences */}
            <div className="space-y-3">
              <label className="text-sm font-medium text-white">偏好与要求</label>
              <PreferencesForm
                interest={interest}
                additional={additional}
                onInterestChange={setInterest}
                onAdditionalChange={setAdditional}
              />
            </div>

            {/* Generate */}
            <div className="flex justify-center pt-2">
              <GenerateButton
                label={generateButtonLabel}
                isGenerating={false}
                disabled={isDisabled}
                onClick={handleGenerate}
              />
            </div>
          </div>
        </div>
      ) : (
        /* ===== CHAT VIEW (Report + Conversation) ===== */
        <div className="flex flex-col h-[calc(100vh-80px)] md:h-[calc(100vh-48px)]">
          {/* Header bar */}
          <div className="flex items-center justify-between py-4 shrink-0">
            <div>
              <h1 className="text-lg font-medium text-white">{reportTitle}</h1>
              <p className="text-xs text-neutral-500 mt-0.5">
                {selectedCompanyId && companies.find(c => c.id === selectedCompanyId)?.name}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRegenerate}
              className="border-neutral-700 text-neutral-300 hover:text-white hover:bg-neutral-800"
            >
              <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
              重新生成
            </Button>
          </div>

          {/* Messages area */}
          <div
            ref={messagesContainerRef}
            className="flex-1 overflow-y-auto space-y-4 pb-4"
            style={{ scrollbarWidth: "thin", scrollbarColor: "#262626 transparent" }}
          >
            {/* Report as first "assistant" message */}
            {streamContent && (
              <div className="bg-neutral-950 rounded-lg border border-neutral-800 p-6">
                <ReportRenderer content={streamContent} isStreaming={isGenerating} />
              </div>
            )}

            {/* Chat messages */}
            {chatMessages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-lg px-4 py-3 ${
                    msg.role === "user"
                      ? "bg-blue-500/15 border border-blue-500/30 text-text-primary"
                      : "bg-neutral-950 border border-neutral-800 text-text-primary"
                  }`}
                >
                  {msg.role === "assistant" ? (
                    <ReportRenderer content={msg.content} isStreaming={isChatStreaming && i === chatMessages.length - 1} />
                  ) : (
                    <p className="text-sm">{msg.content}</p>
                  )}
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          {/* Composer — always visible in chat view, disabled while generating */}
          <div className="shrink-0 border-t border-neutral-800 pt-4 pb-2">
            <div className="flex gap-3">
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSendChat()}
                placeholder={isGenerating ? "报告生成中..." : isChatStreaming ? "正在回复..." : "基于报告内容进行追问..."}
                disabled={isGenerating || isChatStreaming}
                className="flex-1 bg-neutral-900 border border-neutral-800 rounded-lg px-4 py-2.5 text-sm text-white placeholder:text-neutral-500 outline-none disabled:opacity-50 focus:border-neutral-600"
              />
              {isGenerating || isChatStreaming ? (
                <Button
                  onClick={handleStop}
                  variant="outline"
                  className="border-red-800 text-red-400 hover:bg-red-950 hover:text-red-300 px-4"
                >
                  <Square className="h-3.5 w-3.5 mr-1.5 fill-current" />
                  停止
                </Button>
              ) : (
                <Button
                  onClick={handleSendChat}
                  disabled={!chatInput.trim()}
                  className="bg-white text-black hover:bg-neutral-200 disabled:opacity-50 px-5"
                >
                  发送
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Job Detail Drawer */}
      <JobDetailPanel
        jobId={detailJobId}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        isFavorited={detailJobId ? favoritedJobs.some((j) => j.job_id === detailJobId) : false}
        onToggleFavorite={async (jobId) => {
          const isFav = favoritedJobs.some((j) => j.job_id === jobId)
          if (isFav) {
            await handleRemoveFavorite(jobId)
          } else {
            await fetch(`${API_BASE}/api/favorites`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ job_id: jobId }),
            })
            if (selectedCompanyId) fetchFavoritedJobs(selectedCompanyId)
          }
        }}
      />
    </PageContainer>
  )
}
