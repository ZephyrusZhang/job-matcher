"use client"

import { useEffect, useState, useCallback } from "react"
import { Separator } from "@/components/ui/separator"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageContainer } from "@/components/layout/PageContainer"
import { Plus, Trash2, Play, Square, Pencil, X, Check, Loader2 } from "lucide-react"
import type { Company, CompanyCreate } from "@/types/company"
import { getCompanies, createCompany, updateCompany, deleteCompany } from "@/lib/api/companies"
import { triggerCrawl, cancelCrawlTask, getCrawlTasks } from "@/lib/api/crawl"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3001"

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "从未采集"
  const now = Date.now()
  const date = new Date(dateStr).getTime()
  const diffHours = Math.floor((now - date) / (1000 * 60 * 60))
  if (diffHours < 1) return "刚刚"
  if (diffHours < 24) return `${diffHours} 小时前`
  return `${Math.floor(diffHours / 24)} 天前`
}

function CrawlStatusBadge({ status }: { status: Company["crawl_status"] }) {
  const config: Record<string, { label: string; className: string }> = {
    idle: {
      label: "未采集",
      className: "bg-neutral-800 text-neutral-400",
    },
    pending: {
      label: "等待中",
      className: "bg-yellow-500/15 text-yellow-500",
    },
    running: {
      label: "采集中",
      className: "bg-blue-500/15 text-blue-400",
    },
    completed: {
      label: "已完成",
      className: "bg-green-500/15 text-green-400",
    },
    failed: {
      label: "采集失败",
      className: "bg-red-500/15 text-red-400",
    },
    cancelled: {
      label: "已取消",
      className: "bg-orange-500/15 text-orange-400",
    },
  }
  const c = config[status] || config.idle
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${c.className}`}
    >
      {status === "running" && (
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-400" />
        </span>
      )}
      {status === "pending" && (
        <span className="relative flex h-2 w-2">
          <span className="relative inline-flex h-2 w-2 rounded-full bg-yellow-500 animate-pulse" />
        </span>
      )}
      {c.label}
    </span>
  )
}

interface EditingCompany {
  id: string
  name: string
  career_url: string
  crawl_interval_hours: number
}

export default function SettingsPage() {
  const [density, setDensity] = useState<string>("comfortable")
  const [language, setLanguage] = useState<string>("zh")
  const [companies, setCompanies] = useState<Company[]>([])
  const [isAdding, setIsAdding] = useState(false)
  const [newCompany, setNewCompany] = useState<CompanyCreate>({
    id: "",
    name: "",
    career_url: "",
    crawl_interval_hours: 12,
  })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingData, setEditingData] = useState<EditingCompany | null>(null)
  const [triggeringIds, setTriggeringIds] = useState<Set<string>>(new Set())
  // Map company_id → active crawl task_id (for cancel)
  const [activeTaskIds, setActiveTaskIds] = useState<Map<string, string>>(new Map())

  const loadCompanies = useCallback(async () => {
    try {
      const res = await getCompanies()
      setCompanies(res.data)
      // Load active crawl task IDs for companies with active crawls
      const activeCompanies = res.data.filter(
        (c) => c.crawl_status === "pending" || c.crawl_status === "running"
      )
      if (activeCompanies.length > 0) {
        const tasksRes = await getCrawlTasks()
        const taskMap = new Map<string, string>()
        for (const task of tasksRes.data) {
          if (task.status === "pending" || task.status === "running") {
            taskMap.set(task.company_id, task.id)
          }
        }
        setActiveTaskIds(taskMap)
      }
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/api/settings`)
      .then((r) => r.json())
      .then((d) => {
        if (d.success) {
          setDensity(d.data.display_density)
          setLanguage(d.data.language)
        }
      })
    loadCompanies()
  }, [loadCompanies])

  // Poll for status updates when there are active crawls
  useEffect(() => {
    const hasActive = companies.some(
      (c) => c.crawl_status === "pending" || c.crawl_status === "running"
    )
    if (!hasActive) return
    const timer = setInterval(loadCompanies, 3000)
    return () => clearInterval(timer)
  }, [companies, loadCompanies])

  const updateSetting = (patch: Record<string, string>) => {
    fetch(`${API_BASE}/api/settings`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    })
  }

  const handleAddCompany = async () => {
    if (!newCompany.id || !newCompany.name || !newCompany.career_url) return
    try {
      await createCompany(newCompany)
      setIsAdding(false)
      setNewCompany({ id: "", name: "", career_url: "", crawl_interval_hours: 12 })
      await loadCompanies()
    } catch (err: any) {
      alert(err.message || "添加失败")
    }
  }

  const handleUpdateCompany = async () => {
    if (!editingId || !editingData) return
    try {
      await updateCompany(editingId, {
        name: editingData.name,
        career_url: editingData.career_url,
        crawl_interval_hours: editingData.crawl_interval_hours,
      })
      setEditingId(null)
      setEditingData(null)
      await loadCompanies()
    } catch (err: any) {
      alert(err.message || "更新失败")
    }
  }

  const handleDeleteCompany = async (id: string, name: string) => {
    if (!confirm(`确定要删除「${name}」吗？`)) return
    try {
      await deleteCompany(id)
      await loadCompanies()
    } catch (err: any) {
      alert(err.message || "删除失败")
    }
  }

  const handleTriggerCrawl = async (companyId: string) => {
    setTriggeringIds((prev) => new Set(prev).add(companyId))
    try {
      const res = await triggerCrawl(companyId)
      // Store task ID for potential cancel
      setActiveTaskIds((prev) => new Map(prev).set(companyId, res.data.id))
      await loadCompanies()
    } catch (err: any) {
      alert(err.message || "触发失败")
    } finally {
      setTriggeringIds((prev) => {
        const next = new Set(prev)
        next.delete(companyId)
        return next
      })
    }
  }

  const handleCancelCrawl = async (companyId: string) => {
    const taskId = activeTaskIds.get(companyId)
    if (!taskId) return
    try {
      await cancelCrawlTask(taskId)
      setActiveTaskIds((prev) => {
        const next = new Map(prev)
        next.delete(companyId)
        return next
      })
      await loadCompanies()
    } catch (err: any) {
      alert(err.message || "取消失败")
    }
  }

  const startEditing = (company: Company) => {
    setEditingId(company.id)
    setEditingData({
      id: company.id,
      name: company.name,
      career_url: company.career_url,
      crawl_interval_hours: company.crawl_interval_hours,
    })
  }

  const isCrawlActive = (company: Company) =>
    company.crawl_status === "pending" || company.crawl_status === "running"

  const isCrawlDisabled = (company: Company) =>
    isCrawlActive(company) || triggeringIds.has(company.id)

  return (
    <PageContainer>
      <div className="space-y-[var(--gap-section)]">
        <h1 className="text-xl font-medium text-text-primary">设置</h1>

        {/* Display Preferences */}
        <div className="bg-neutral-950 rounded-lg border border-neutral-800 p-4 sm:p-6">
          <h2 className="text-base font-medium text-text-primary">显示偏好</h2>
          <Separator className="bg-neutral-800 my-4" />

          <div className="space-y-6">
            <div className="space-y-3">
              <label className="text-sm text-text-primary">信息密度</label>
              <RadioGroup
                value={density}
                onValueChange={(val) => {
                  setDensity(val)
                  updateSetting({ display_density: val })
                }}
                className="flex gap-6"
              >
                <div className="flex items-center gap-2">
                  <RadioGroupItem value="comfortable" id="comfortable" />
                  <label htmlFor="comfortable" className="text-sm text-text-primary cursor-pointer">
                    舒适
                  </label>
                </div>
                <div className="flex items-center gap-2">
                  <RadioGroupItem value="compact" id="compact" />
                  <label htmlFor="compact" className="text-sm text-text-primary cursor-pointer">
                    紧凑
                  </label>
                </div>
              </RadioGroup>
            </div>

            <div className="space-y-3">
              <label className="text-sm text-text-primary">语言</label>
              <Select
                value={language}
                onValueChange={(val) => {
                  if (val) setLanguage(val)
                  if (val) updateSetting({ language: val })
                }}
              >
                <SelectTrigger className="w-[200px] bg-neutral-900 border-neutral-800 text-white rounded-lg">
                  <SelectValue placeholder="选择语言">{language === "zh" ? "中文" : "English"}</SelectValue>
                </SelectTrigger>
                <SelectContent className="bg-bg-elevated border-border-default">
                  <SelectItem value="zh" className="text-text-primary focus:bg-bg-tertiary focus:text-text-primary">中文</SelectItem>
                  <SelectItem value="en" className="text-text-primary focus:bg-bg-tertiary focus:text-text-primary">English</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        {/* Company Management */}
        <div className="bg-neutral-950 rounded-lg border border-neutral-800 p-4 sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-base font-medium text-text-primary">目标公司</h2>
              <p className="text-sm text-text-secondary mt-1 hidden sm:block">管理需要爬取岗位的目标公司</p>
            </div>
            {!isAdding && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsAdding(true)}
                className="text-text-primary border-neutral-700 hover:bg-neutral-800"
              >
                <Plus className="size-3.5 mr-1" />
                添加公司
              </Button>
            )}
          </div>
          <Separator className="bg-neutral-800 my-4" />

          {/* Add Company Form */}
          {isAdding && (
            <div className="mb-4 rounded-lg border border-neutral-700 bg-neutral-900/50 p-3 sm:p-4 space-y-3">
              <div className="grid grid-cols-2 sm:grid-cols-[1fr_1fr_2fr_auto] gap-3 items-end">
                <div className="space-y-1.5">
                  <label className="text-xs text-text-secondary">公司 ID</label>
                  <Input
                    placeholder="如 bytedance"
                    value={newCompany.id}
                    onChange={(e) => setNewCompany({ ...newCompany, id: e.target.value })}
                    className="bg-neutral-900 border-neutral-700 text-white text-sm h-8"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-text-secondary">公司名称</label>
                  <Input
                    placeholder="如 字节跳动"
                    value={newCompany.name}
                    onChange={(e) => setNewCompany({ ...newCompany, name: e.target.value })}
                    className="bg-neutral-900 border-neutral-700 text-white text-sm h-8"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-text-secondary">招聘页 URL</label>
                  <Input
                    placeholder="https://..."
                    value={newCompany.career_url}
                    onChange={(e) => setNewCompany({ ...newCompany, career_url: e.target.value })}
                    className="bg-neutral-900 border-neutral-700 text-white text-sm h-8"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-text-secondary">间隔(h)</label>
                  <Input
                    type="number"
                    min={1}
                    value={newCompany.crawl_interval_hours}
                    onChange={(e) =>
                      setNewCompany({ ...newCompany, crawl_interval_hours: parseInt(e.target.value) || 12 })
                    }
                    className="bg-neutral-900 border-neutral-700 text-white text-sm h-8 w-20"
                  />
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setIsAdding(false)
                    setNewCompany({ id: "", name: "", career_url: "", crawl_interval_hours: 12 })
                  }}
                  className="text-text-secondary"
                >
                  取消
                </Button>
                <Button
                  size="sm"
                  onClick={handleAddCompany}
                  disabled={!newCompany.id || !newCompany.name || !newCompany.career_url}
                >
                  添加
                </Button>
              </div>
            </div>
          )}

          {/* Mobile: card layout */}
          <div className="md:hidden space-y-3">
            {companies.length === 0 && (
              <p className="text-center text-sm text-text-muted py-8">暂无目标公司，请点击上方「添加公司」</p>
            )}
            {companies.map((company) => (
              <div key={company.id} className="border border-neutral-800 rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm text-text-primary font-medium truncate">{company.name}</p>
                    <p className="text-xs text-text-muted truncate">{company.career_url}</p>
                  </div>
                  <CrawlStatusBadge status={company.crawl_status} />
                </div>
                <div className="flex items-center gap-4 text-xs text-text-secondary">
                  <span>每 <span className="text-blue-400">{company.crawl_interval_hours}</span>h</span>
                  <span>{company.job_count} 岗位</span>
                  <span>{formatRelativeTime(company.last_crawled_at)}</span>
                </div>
                <div className="flex gap-1 pt-1">
                  {isCrawlActive(company) ? (
                    <Button variant="ghost" size="icon-xs" onClick={() => handleCancelCrawl(company.id)} className="text-red-400 hover:text-red-300 hover:bg-red-500/10" title="停止"><Square className="size-3 fill-current" /></Button>
                  ) : (
                    <Button variant="ghost" size="icon-xs" onClick={() => handleTriggerCrawl(company.id)} disabled={triggeringIds.has(company.id)} className="text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 disabled:opacity-30" title="爬取">
                      {triggeringIds.has(company.id) ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
                    </Button>
                  )}
                  <Button variant="ghost" size="icon-xs" onClick={() => startEditing(company)} className="text-text-secondary hover:text-text-primary hover:bg-neutral-800" title="编辑"><Pencil className="size-3.5" /></Button>
                  <Button variant="ghost" size="icon-xs" onClick={() => handleDeleteCompany(company.id, company.name)} className="text-red-400/60 hover:text-red-400 hover:bg-red-500/10" title="删除"><Trash2 className="size-3.5" /></Button>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop: table layout */}
          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow className="border-b border-neutral-800 hover:bg-transparent">
                  <TableHead className="text-text-secondary text-xs uppercase">公司名称</TableHead>
                  <TableHead className="text-text-secondary text-xs uppercase">招聘页 URL</TableHead>
                  <TableHead className="text-text-secondary text-xs uppercase">采集频率</TableHead>
                  <TableHead className="text-text-secondary text-xs uppercase">岗位数</TableHead>
                  <TableHead className="text-text-secondary text-xs uppercase">上次采集</TableHead>
                  <TableHead className="text-text-secondary text-xs uppercase">状态</TableHead>
                  <TableHead className="text-text-secondary text-xs uppercase text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {companies.length === 0 && (
                  <TableRow className="border-b border-neutral-800 hover:bg-transparent">
                    <TableCell colSpan={7} className="text-center text-sm text-text-muted py-8">
                      暂无目标公司，请点击上方「添加公司」
                    </TableCell>
                  </TableRow>
                )}
                {companies.map((company) => (
                  <TableRow key={company.id} className="border-b border-neutral-800 hover:bg-neutral-900/50">
                    {editingId === company.id ? (
                      <>
                        <TableCell>
                          <Input value={editingData?.name ?? ""} onChange={(e) => setEditingData((d) => d ? { ...d, name: e.target.value } : d)} className="bg-neutral-900 border-neutral-700 text-white text-sm h-7 w-full" />
                        </TableCell>
                        <TableCell>
                          <Input value={editingData?.career_url ?? ""} onChange={(e) => setEditingData((d) => d ? { ...d, career_url: e.target.value } : d)} className="bg-neutral-900 border-neutral-700 text-white text-sm h-7 w-full" />
                        </TableCell>
                        <TableCell>
                          <Input type="number" min={1} value={editingData?.crawl_interval_hours ?? 12} onChange={(e) => setEditingData((d) => d ? { ...d, crawl_interval_hours: parseInt(e.target.value) || 12 } : d)} className="bg-neutral-900 border-neutral-700 text-white text-sm h-7 w-20" />
                        </TableCell>
                        <TableCell className="text-sm text-text-primary">{company.job_count}</TableCell>
                        <TableCell className="text-sm text-text-secondary">{formatRelativeTime(company.last_crawled_at)}</TableCell>
                        <TableCell><CrawlStatusBadge status={company.crawl_status} /></TableCell>
                        <TableCell className="text-right">
                          <div className="flex gap-1 justify-end">
                            <Button variant="ghost" size="icon-xs" onClick={handleUpdateCompany} className="text-green-400 hover:text-green-300 hover:bg-green-500/10"><Check className="size-3.5" /></Button>
                            <Button variant="ghost" size="icon-xs" onClick={() => { setEditingId(null); setEditingData(null) }} className="text-text-secondary hover:text-text-primary"><X className="size-3.5" /></Button>
                          </div>
                        </TableCell>
                      </>
                    ) : (
                      <>
                        <TableCell className="text-sm text-text-primary font-medium">
                          {company.name}
                          <span className="text-text-muted text-xs ml-2">({company.id})</span>
                        </TableCell>
                        <TableCell className="text-sm text-text-secondary max-w-[200px] truncate">
                          <a href={company.career_url} target="_blank" rel="noopener noreferrer" className="hover:text-blue-400 transition-colors">{company.career_url}</a>
                        </TableCell>
                        <TableCell className="text-sm text-text-primary">每 <span className="text-blue-400">{company.crawl_interval_hours}</span> 小时</TableCell>
                        <TableCell className="text-sm text-text-primary">{company.job_count}</TableCell>
                        <TableCell className="text-sm text-text-secondary">{formatRelativeTime(company.last_crawled_at)}</TableCell>
                        <TableCell><CrawlStatusBadge status={company.crawl_status} /></TableCell>
                        <TableCell className="text-right">
                          <div className="flex gap-1 justify-end">
                            {isCrawlActive(company) ? (
                              <Button variant="ghost" size="icon-xs" onClick={() => handleCancelCrawl(company.id)} className="text-red-400 hover:text-red-300 hover:bg-red-500/10" title="停止爬取"><Square className="size-3 fill-current" /></Button>
                            ) : (
                              <Button variant="ghost" size="icon-xs" onClick={() => handleTriggerCrawl(company.id)} disabled={triggeringIds.has(company.id)} className="text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 disabled:opacity-30" title="手动触发爬取">
                                {triggeringIds.has(company.id) ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
                              </Button>
                            )}
                            <Button variant="ghost" size="icon-xs" onClick={() => startEditing(company)} className="text-text-secondary hover:text-text-primary hover:bg-neutral-800" title="编辑"><Pencil className="size-3.5" /></Button>
                            <Button variant="ghost" size="icon-xs" onClick={() => handleDeleteCompany(company.id, company.name)} className="text-red-400/60 hover:text-red-400 hover:bg-red-500/10" title="删除"><Trash2 className="size-3.5" /></Button>
                          </div>
                        </TableCell>
                      </>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>
    </PageContainer>
  )
}
