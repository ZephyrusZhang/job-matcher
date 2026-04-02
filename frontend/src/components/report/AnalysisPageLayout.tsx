"use client"

import { useEffect, useState, useCallback, useRef } from "react"
import { Separator } from "@/components/ui/separator"
import { PageContainer } from "@/components/layout/PageContainer"
import { CompanySelector } from "@/components/jobs/CompanySelector"
import { ResumeUploader } from "./ResumeUploader"
import { PreferencesForm } from "./PreferencesForm"
import { GenerateButton } from "./GenerateButton"
import { ReportRenderer } from "./ReportRenderer"
import { Star, MapPin, Briefcase, X } from "lucide-react"
import type { Company } from "@/types/company"
import type { FavoriteSummary, FavoriteItem } from "@/types/favorite"
import type { ResumeInfo } from "@/types/resume"
import type { Report } from "@/types/report"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3001"

interface SSEEvent {
  event: string
  data: Record<string, unknown>
}

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

  // Favorited jobs for current company
  const [favoritedJobs, setFavoritedJobs] = useState<FavoriteItem[]>([])

  // Report state
  const [report, setReport] = useState<Report | null>(null)
  const [streamContent, setStreamContent] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)
  const [reportId, setReportId] = useState<string | null>(null)

  // Chat state
  const [chatMessages, setChatMessages] = useState<{ role: string; content: string }[]>([])
  const [chatInput, setChatInput] = useState("")
  const [isChatStreaming, setIsChatStreaming] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  // Fetch companies + favorites summary
  useEffect(() => {
    fetch(`${API_BASE}/api/companies`)
      .then((r) => r.json())
      .then((d) => { if (d.success) setCompanies(d.data) })
    fetch(`${API_BASE}/api/favorites/summary`)
      .then((r) => r.json())
      .then((d) => { if (d.success) setFavoriteSummary(d.data) })
  }, [])

  // Fetch resume
  useEffect(() => {
    fetch(`${API_BASE}/api/resume`)
      .then((r) => r.json())
      .then((d) => { if (d.success) setResume(d.data) })
  }, [])

  // Fetch favorited jobs when company changes
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
    // Optimistic remove
    setFavoritedJobs((prev) => prev.filter((j) => j.job_id !== jobId))
    try {
      await fetch(`${API_BASE}/api/favorites/${jobId}`, { method: "DELETE" })
      // Refresh summary
      fetch(`${API_BASE}/api/favorites/summary`)
        .then((r) => r.json())
        .then((d) => { if (d.success) setFavoriteSummary(d.data) })
    } catch {
      // Rollback on error
      if (selectedCompanyId) fetchFavoritedJobs(selectedCompanyId)
    }
  }

  // Fetch existing report when company changes
  useEffect(() => {
    if (!selectedCompanyId) return
    fetch(`${API_BASE}${reportEndpoint}?company_id=${selectedCompanyId}`)
      .then((r) => r.json())
      .then((d) => {
        if (d.success && d.data) {
          setReport(d.data)
          setStreamContent(d.data.content)
          setReportId(d.data.report_id)
          // Load chat history
          fetch(`${API_BASE}/api/chat/history?report_id=${d.data.report_id}`)
            .then((r) => r.json())
            .then((cd) => {
              if (cd.success && cd.data) {
                setChatMessages(cd.data.messages.map((m: { role: string; content: string }) => ({
                  role: m.role,
                  content: m.content,
                })))
              }
            })
        } else {
          setReport(null)
          setStreamContent("")
          setReportId(null)
          setChatMessages([])
        }
      })
  }, [selectedCompanyId, reportEndpoint])

  // SSE parsing helper
  const consumeSSE = useCallback(async (url: string, body: unknown) => {
    const res = await fetch(`${API_BASE}${url}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
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
          } else if (event === endEvent) {
            // Done
          } else if (event === "chat_start") {
            // Chat streaming started
          } else if (event === "chat_end") {
            // Chat streaming done
          }
        }
      }
    }
  }, [startEvent, endEvent])

  const handleGenerate = async () => {
    if (!selectedCompanyId || !interest.trim()) return
    setIsGenerating(true)
    setStreamContent("")
    setReport(null)
    setChatMessages([])

    try {
      await consumeSSE(generateEndpoint, {
        company_id: selectedCompanyId,
        preferences: { interest, additional: additional || undefined },
      })
    } finally {
      setIsGenerating(false)
    }
  }

  const handleSendChat = async () => {
    if (!chatInput.trim() || !reportId || isChatStreaming) return
    const userMsg = chatInput.trim()
    setChatInput("")
    setChatMessages((prev) => [...prev, { role: "user", content: userMsg }])
    setIsChatStreaming(true)

    let assistantContent = ""
    try {
      const res = await fetch(`${API_BASE}/api/chat/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report_id: reportId, message: userMsg }),
      })

      if (!res.ok || !res.body) throw new Error("Chat SSE failed")

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      // Add placeholder for assistant
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
    } finally {
      setIsChatStreaming(false)
    }
  }

  // Disabled conditions
  const favCount = favoriteSummary.find((s) => s.company_id === selectedCompanyId)?.count ?? 0
  const isDisabled = !selectedCompanyId || !resume || favCount === 0 || !interest.trim()

  const showReport = streamContent.length > 0 || report !== null
  const showChat = showReport && !isGenerating

  return (
    <PageContainer>
      <div className="space-y-[var(--gap-section)]">
        {/* Page Header */}
        <div>
          <h1 className="text-xl font-medium text-text-primary">{title}</h1>
          <p className="text-sm text-text-secondary mt-1">{description}</p>
        </div>

        {/* Input Section */}
        <div className="bg-bg-secondary rounded-[var(--radius)] border border-border-default p-6 space-y-6">
          {/* Company Selector */}
          <div className="space-y-3">
            <label className="text-sm font-medium text-text-primary">选择公司</label>
            <CompanySelector
              companies={companies}
              value={selectedCompanyId}
              onChange={setSelectedCompanyId}
              showFavoriteCount
              favoriteSummary={favoriteSummary}
            />
          </div>

          {/* Favorited Jobs Horizontal List */}
          {selectedCompanyId && favoritedJobs.length > 0 && (
            <div className="space-y-3">
              <label className="text-sm font-medium text-text-primary flex items-center gap-2">
                <Star className="h-3.5 w-3.5 text-accent-main fill-accent-main" />
                已收藏的岗位（{favoritedJobs.length}）
              </label>
              <div className="relative">
                <div className="flex gap-3 overflow-x-auto pb-3 -mx-1 px-1" style={{ scrollbarWidth: "thin", scrollbarColor: "var(--border-default) transparent" }}>
                  {favoritedJobs.map((job) => (
                    <div
                      key={job.job_id}
                      className="shrink-0 w-[240px] bg-bg-primary border border-border-default rounded-[var(--radius-sm)] p-3.5 space-y-2 hover:border-accent-main/50 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm text-text-primary font-medium line-clamp-2 leading-snug flex-1">{job.title}</p>
                        <button
                          onClick={() => handleRemoveFavorite(job.job_id)}
                          className="shrink-0 mt-0.5 p-0.5 rounded text-text-muted hover:text-tag-red hover:bg-tag-red-bg transition-colors cursor-pointer"
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
              </div>
            </div>
          )}
          {selectedCompanyId && favoritedJobs.length === 0 && (
            <div className="flex flex-col items-center py-4 gap-2">
              <Star className="h-8 w-8 text-text-muted" />
              <p className="text-sm text-text-muted">该公司暂无收藏岗位</p>
              <p className="text-xs text-text-muted">请先在岗位总览页收藏感兴趣的岗位</p>
            </div>
          )}

          <Separator className="bg-border-subtle" />

          {/* Resume Upload */}
          <div className="space-y-3">
            <label className="text-sm font-medium text-text-primary">上传简历</label>
            <ResumeUploader
              resume={resume}
              onUploadSuccess={(r) => {
                setResume(r)
                setReport(null)
                setStreamContent("")
                setChatMessages([])
              }}
            />
          </div>

          <Separator className="bg-border-subtle" />

          {/* Preferences */}
          <div className="space-y-3">
            <label className="text-sm font-medium text-text-primary">偏好与要求</label>
            <PreferencesForm
              interest={interest}
              additional={additional}
              onInterestChange={setInterest}
              onAdditionalChange={setAdditional}
            />
          </div>

          {/* Generate Button */}
          <div className="flex justify-center pt-2">
            <GenerateButton
              label={generateButtonLabel}
              isGenerating={isGenerating}
              disabled={isDisabled}
              onClick={handleGenerate}
            />
          </div>
        </div>

        {/* Report Section */}
        {showReport && (
          <div className="bg-bg-secondary rounded-[var(--radius)] border border-border-default p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-medium text-text-primary">{reportTitle}</h2>
              {report?.created_at && (
                <span className="text-xs text-text-muted">
                  生成时间: {new Date(report.created_at).toLocaleDateString("zh-CN")}
                </span>
              )}
            </div>
            <Separator className="bg-border-subtle" />
            <ReportRenderer content={streamContent} isStreaming={isGenerating} />
          </div>
        )}

        {/* Chat Section */}
        {showChat && (
          <div className="bg-bg-secondary rounded-[var(--radius)] border border-border-default overflow-hidden animate-in fade-in duration-300">
            <div className="p-6 space-y-4 max-h-[500px] overflow-y-auto">
              {chatMessages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-[var(--radius-sm)] px-4 py-3 ${
                      msg.role === "user"
                        ? "bg-bg-tertiary text-text-primary"
                        : "bg-transparent text-text-primary"
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

            {/* Composer */}
            <div className="border-t border-border-subtle p-4">
              <div className="flex gap-3">
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSendChat()}
                  placeholder={isChatStreaming ? "正在回复..." : "输入追问..."}
                  disabled={isChatStreaming}
                  className="flex-1 bg-bg-tertiary rounded-[var(--radius-sm)] px-4 py-2 text-sm text-text-primary placeholder:text-text-muted border-none outline-none disabled:opacity-50"
                />
                <button
                  onClick={handleSendChat}
                  disabled={isChatStreaming || !chatInput.trim()}
                  className="text-accent-main text-sm font-medium px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  发送
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </PageContainer>
  )
}
