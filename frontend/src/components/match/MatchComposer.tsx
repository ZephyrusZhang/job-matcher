"use client"

import { useEffect, useRef, useState } from "react"
import {
  AtSign,
  Check,
  FileText,
  Loader2,
  Maximize2,
  Minimize2,
  Send,
  Square,
  Upload,
  X,
} from "lucide-react"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { getCompanies } from "@/lib/api/companies"
import { apiGet } from "@/lib/api/client"
import { isComposing } from "@/lib/ime"
import { cn } from "@/lib/utils"
import type { MatchScope, ResumeSummary, ScopeMode } from "@/types/match"
import type { Company } from "@/types/company"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3001"

/**
 * How far the box grows on its own before the expand toggle is worth reaching
 * for — roughly eight lines. Past that the composer would start eating the
 * conversation, which is what the toggle is for.
 */
const AUTO_GROW_MAX_PX = 168

interface MatchComposerProps {
  scope: MatchScope
  onScopeChange: (scope: MatchScope) => void
  resumeId: string | null
  onResumeChange: (id: string | null) => void
  onSend: (content: string) => void
  onStop: () => void
  isStreaming: boolean
}

export function MatchComposer({
  scope,
  onScopeChange,
  resumeId,
  onResumeChange,
  onSend,
  onStop,
  isStreaming,
}: MatchComposerProps) {
  const [value, setValue] = useState("")
  const [companies, setCompanies] = useState<Company[]>([])
  const [resumes, setResumes] = useState<ResumeSummary[]>([])
  const [uploading, setUploading] = useState(false)
  const [expanded, setExpanded] = useState(false)
  // Height the composer occupied while collapsed. Expanding lifts the box out
  // of the flow so it floats over the conversation; without holding its former
  // height the row would collapse and the messages above would jump.
  const [reservedHeight, setReservedHeight] = useState<number | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const toggleExpanded = () => {
    if (!expanded) setReservedHeight(rootRef.current?.offsetHeight ?? null)
    setExpanded((v) => !v)
    textareaRef.current?.focus()
  }

  // Size the box to its content while collapsed; when expanded a class owns
  // the height, so the inline value has to get out of the way.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    if (expanded) {
      el.style.height = ""
      return
    }
    el.style.height = "auto"
    el.style.height = `${Math.min(el.scrollHeight, AUTO_GROW_MAX_PX)}px`
  }, [value, expanded])

  const loadResumes = () => {
    apiGet<ResumeSummary[]>("/api/resumes")
      .then((res) => {
        const list = res.data ?? []
        setResumes(list)
        if (!resumeId) {
          const fallback = list.find((r) => r.is_default) ?? list[0]
          if (fallback) onResumeChange(fallback.id)
        }
      })
      .catch(() => setResumes([]))
  }

  useEffect(() => {
    getCompanies()
      .then((res) => setCompanies(res.data ?? []))
      .catch(() => setCompanies([]))
    loadResumes()
    // Loading once on mount is intentional; both lists change rarely.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const activeResume = resumes.find((r) => r.id === resumeId) ?? null

  const submit = () => {
    const content = value.trim()
    if (!content || isStreaming) return
    onSend(content)
    setValue("")
  }

  const toggleCompany = (id: string) => {
    const next = scope.company_ids.includes(id)
      ? scope.company_ids.filter((c) => c !== id)
      : [...scope.company_ids, id]
    onScopeChange({ mode: "companies", company_ids: next })
  }

  const setMode = (mode: ScopeMode) => {
    onScopeChange({ mode, company_ids: mode === "favorites" ? [] : scope.company_ids })
  }

  const upload = async (file: File) => {
    setUploading(true)
    try {
      const form = new FormData()
      form.append("file", file)
      const res = await fetch(`${API_BASE}/api/resumes`, { method: "POST", body: form })
      const body = await res.json()
      if (body?.data?.id) onResumeChange(body.data.id)
      loadResumes()
    } finally {
      setUploading(false)
    }
  }

  const chips: { key: string; label: string; onRemove: () => void }[] = []
  if (activeResume) {
    chips.push({
      key: "resume",
      label: activeResume.label,
      onRemove: () => onResumeChange(null),
    })
  }
  if (scope.mode === "favorites") {
    chips.push({ key: "favorites", label: "收藏岗位", onRemove: () => setMode("companies") })
  } else {
    for (const id of scope.company_ids) {
      const name = companies.find((c) => c.id === id)?.name ?? id
      chips.push({ key: id, label: name, onRemove: () => toggleCompany(id) })
    }
  }

  return (
    <div
      ref={rootRef}
      className="relative bg-bg-primary px-4 py-3"
      style={expanded && reservedHeight ? { minHeight: reservedHeight } : undefined}
    >
      <div
        className={cn(
          "w-full rounded-lg border border-border-subtle bg-bg-secondary focus-within:border-border-default",
          expanded
            ? // Anchored to the bottom and grown upward, so the conversation
              // behind it keeps its size instead of being squeezed.
              "absolute bottom-3 left-1/2 z-20 w-[calc(100%-2rem)] max-w-3xl -translate-x-1/2 shadow-2xl"
            : "mx-auto max-w-3xl",
        )}
      >
        <textarea
          ref={textareaRef}
          rows={2}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            // An IME's Enter commits its candidate; only a free-standing Enter
            // sends. Escape still has to work mid-composition so the expanded
            // view can always be closed.
            if (e.key === "Enter" && !e.shiftKey && !isComposing(e)) {
              e.preventDefault()
              submit()
            }
            // Esc leaves the tall view without touching what was typed.
            if (e.key === "Escape" && expanded) {
              e.preventDefault()
              setExpanded(false)
            }
          }}
          placeholder="描述你的诉求，例如：帮我找上海的后端实习，偏基础架构方向"
          className={cn(
            "w-full resize-none bg-transparent px-3.5 pt-3 text-sm text-text-primary placeholder:text-text-muted focus:outline-none",
            expanded ? "h-[45vh] overflow-y-auto" : "overflow-y-auto",
          )}
        />

        {chips.length > 0 && (
          <div className="flex flex-wrap gap-1 px-3.5 pb-1">
            {chips.map((chip) => (
              <span
                key={chip.key}
                className="flex items-center gap-1 rounded bg-bg-tertiary px-1.5 py-0.5 text-[11px] text-text-secondary"
              >
                {chip.label}
                <button
                  type="button"
                  onClick={chip.onRemove}
                  className="text-text-muted hover:text-text-primary"
                  aria-label={`移除 ${chip.label}`}
                >
                  <X className="h-2.5 w-2.5" />
                </button>
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center gap-1 px-2.5 pb-2 pt-1">
          {/* Scope picker */}
          <Popover>
            <PopoverTrigger
              className="flex h-7 w-7 items-center justify-center rounded-full border border-border-subtle text-text-muted transition-colors hover:border-border-default hover:text-text-primary"
              aria-label="选择检索范围"
            >
              <AtSign className="h-3.5 w-3.5" />
            </PopoverTrigger>
            <PopoverContent className="w-64 p-2">
              <button
                type="button"
                onClick={() => setMode("favorites")}
                aria-current={scope.mode === "favorites"}
                className={cn(
                  "mb-1 flex w-full items-center justify-between rounded px-2 py-1.5 text-sm transition-colors",
                  scope.mode === "favorites"
                    ? "bg-accent-muted font-medium text-text-primary"
                    : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary",
                )}
              >
                <span className="flex items-center gap-2">
                  <Check
                    className={cn("h-3.5 w-3.5 shrink-0", scope.mode !== "favorites" && "opacity-0")}
                    aria-hidden
                  />
                  收藏岗位
                </span>
              </button>

              <div className="mb-1 border-t border-border-subtle pt-1 text-[11px] text-text-muted">
                按公司（可多选）
              </div>
              <div className="max-h-56 overflow-y-auto">
                {companies.map((company) => {
                  const checked =
                    scope.mode === "companies" && scope.company_ids.includes(company.id)
                  return (
                    <button
                      key={company.id}
                      type="button"
                      onClick={() => toggleCompany(company.id)}
                      className="flex w-full items-center justify-between rounded px-2 py-1.5 text-sm text-text-primary transition-colors hover:bg-bg-tertiary"
                    >
                      <span className="flex items-center gap-2">
                        <span
                          className={cn(
                            "flex h-3.5 w-3.5 items-center justify-center rounded-sm border",
                            checked
                              ? "border-accent-main bg-accent-main text-bg-primary"
                              : "border-border-default",
                          )}
                        >
                          {checked && <span className="text-[9px] leading-none">✓</span>}
                        </span>
                        {company.name}
                      </span>
                      <span className="text-xs text-text-muted">{company.job_count}</span>
                    </button>
                  )
                })}
              </div>
            </PopoverContent>
          </Popover>

          {/* Resume picker */}
          <Popover>
            <PopoverTrigger
              className="flex h-7 w-7 items-center justify-center rounded-full border border-border-subtle text-text-muted transition-colors hover:border-border-default hover:text-text-primary"
              aria-label="选择简历"
            >
              {uploading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <FileText className="h-3.5 w-3.5" />
              )}
            </PopoverTrigger>
            <PopoverContent className="w-64 p-2">
              {resumes.length === 0 && (
                <p className="px-2 py-1.5 text-xs text-text-muted">还没有简历</p>
              )}
              {/* Selection is a tick plus a background tint, not a text colour:
                  the accent resolves to the same near-white/near-black as
                  text-primary, so recolouring the label could not signal
                  anything on its own. The tick keeps its space when unselected
                  so the labels stay aligned. */}
              {resumes.map((resume) => {
                const selected = resume.id === resumeId
                return (
                  <button
                    key={resume.id}
                    type="button"
                    onClick={() => onResumeChange(resume.id)}
                    aria-current={selected}
                    className={cn(
                      "flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm transition-colors",
                      selected
                        ? "bg-accent-muted font-medium text-text-primary"
                        : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary",
                    )}
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <Check
                        className={cn("h-3.5 w-3.5 shrink-0", !selected && "opacity-0")}
                        aria-hidden
                      />
                      <span className="truncate">{resume.label}</span>
                    </span>
                    {resume.is_default && (
                      <span className="ml-2 shrink-0 text-[10px] text-text-muted">默认</span>
                    )}
                  </button>
                )
              })}

              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                className="mt-1 flex w-full items-center gap-2 border-t border-border-subtle px-2 pt-2 text-sm text-text-secondary hover:text-text-primary"
              >
                <Upload className="h-3.5 w-3.5" />
                上传新简历
              </button>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.docx"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) upload(file)
                  e.target.value = ""
                }}
              />
            </PopoverContent>
          </Popover>

          <button
            type="button"
            onClick={toggleExpanded}
            className="ml-auto mr-1 flex h-7 w-7 items-center justify-center rounded-full border border-border-subtle text-text-muted transition-colors hover:border-border-default hover:text-text-primary"
            aria-label={expanded ? "收起输入框" : "放大输入框"}
            aria-pressed={expanded}
            title={expanded ? "收起输入框（Esc）" : "放大输入框"}
          >
            {expanded ? (
              <Minimize2 className="h-3.5 w-3.5" />
            ) : (
              <Maximize2 className="h-3.5 w-3.5" />
            )}
          </button>

          <div>
            {isStreaming ? (
              <button
                type="button"
                onClick={onStop}
                className="flex h-7 w-7 items-center justify-center rounded-full bg-bg-tertiary text-text-secondary transition-colors hover:text-text-primary"
                aria-label="停止生成"
              >
                <Square className="h-3 w-3" />
              </button>
            ) : (
              <button
                type="button"
                onClick={submit}
                disabled={!value.trim()}
                className="flex h-7 w-7 items-center justify-center rounded-full bg-accent-main text-bg-primary transition-opacity disabled:opacity-30"
                aria-label="发送"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
