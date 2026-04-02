"use client"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { FilterTag } from "./FilterTag"
import type { Company } from "@/types/company"

const JOB_CATEGORIES = [
  "算法", "后端", "客户端", "前端", "测试", "大数据", "安全",
  "硬件", "机器学习", "基础架构", "多媒体", "计算机视觉", "运维",
  "数据挖掘", "自然语言处理",
]

const JOB_TYPES = [
  { value: "fulltime", label: "全职" },
  { value: "intern", label: "实习" },
  { value: "parttime", label: "兼职" },
  { value: "contract", label: "合同工" },
]

const POSTED_WITHIN = [
  { value: "24h", label: "最近24小时" },
  { value: "7d", label: "最近一周" },
  { value: "30d", label: "最近一月" },
]

export interface Filters {
  categories: string[]
  location: string | null
  jobType: string | null
  postedWithin: string | null
}

interface FilterBarProps {
  filters: Filters
  locations: string[]
  onChange: (filters: Filters) => void
  companies?: Company[]
  selectedCompanyId?: string | null
  onCompanyChange?: (id: string) => void
}

export function FilterBar({ filters, locations, onChange, companies, selectedCompanyId, onCompanyChange }: FilterBarProps) {
  const activeFilters: { label: string; onRemove: () => void }[] = []

  filters.categories.forEach((cat) => {
    activeFilters.push({
      label: cat,
      onRemove: () =>
        onChange({ ...filters, categories: filters.categories.filter((c) => c !== cat) }),
    })
  })
  if (filters.location) {
    activeFilters.push({
      label: filters.location,
      onRemove: () => onChange({ ...filters, location: null }),
    })
  }
  if (filters.jobType) {
    const label = JOB_TYPES.find((t) => t.value === filters.jobType)?.label ?? filters.jobType
    activeFilters.push({ label, onRemove: () => onChange({ ...filters, jobType: null }) })
  }
  if (filters.postedWithin) {
    const label = POSTED_WITHIN.find((t) => t.value === filters.postedWithin)?.label ?? filters.postedWithin
    activeFilters.push({ label, onRemove: () => onChange({ ...filters, postedWithin: null }) })
  }

  const jobTypeLabel = JOB_TYPES.find((t) => t.value === filters.jobType)?.label
  const postedLabel = POSTED_WITHIN.find((t) => t.value === filters.postedWithin)?.label
  const selectedCompany = companies?.find((c) => c.id === selectedCompanyId)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        {/* Company Selector (inline) */}
        {companies && onCompanyChange && (
          <Select value={selectedCompanyId ?? null} onValueChange={(val) => { if (val) onCompanyChange(val) }}>
            <SelectTrigger className="w-[200px] bg-bg-tertiary border-border-default text-text-primary text-sm rounded-[var(--radius-sm)] h-9">
              <SelectValue placeholder="选择公司">
                {selectedCompany ? `${selectedCompany.name}（${selectedCompany.job_count}）` : "选择公司"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent className="bg-bg-elevated border-border-default">
              {companies.map((c) => (
                <SelectItem key={c.id} value={c.id} className="text-text-primary text-sm">
                  {c.name}（{c.job_count} 个岗位）
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {/* Category */}
        <Select
          value=""
          onValueChange={(val) => {
            if (val && !filters.categories.includes(val)) {
              onChange({ ...filters, categories: [...filters.categories, val] })
            }
          }}
        >
          <SelectTrigger className="w-[130px] bg-bg-tertiary border-border-default text-text-primary text-sm rounded-[var(--radius-sm)] h-9">
            <SelectValue placeholder="岗位方向">岗位方向</SelectValue>
          </SelectTrigger>
          <SelectContent className="bg-bg-elevated border-border-default">
            {JOB_CATEGORIES.map((cat) => (
              <SelectItem key={cat} value={cat} className="text-text-primary text-sm">
                {cat}{filters.categories.includes(cat) ? " ✓" : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Location */}
        <Select value={filters.location ?? ""} onValueChange={(val) => onChange({ ...filters, location: val ?? null })}>
          <SelectTrigger className="w-[120px] bg-bg-tertiary border-border-default text-text-primary text-sm rounded-[var(--radius-sm)] h-9">
            <SelectValue placeholder="地点">{filters.location ?? "地点"}</SelectValue>
          </SelectTrigger>
          <SelectContent className="bg-bg-elevated border-border-default">
            {locations.map((loc) => (
              <SelectItem key={loc} value={loc} className="text-text-primary text-sm">{loc}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Job Type */}
        <Select value={filters.jobType ?? ""} onValueChange={(val) => onChange({ ...filters, jobType: val ?? null })}>
          <SelectTrigger className="w-[130px] bg-bg-tertiary border-border-default text-text-primary text-sm rounded-[var(--radius-sm)] h-9">
            <SelectValue placeholder="岗位类型">{jobTypeLabel ?? "岗位类型"}</SelectValue>
          </SelectTrigger>
          <SelectContent className="bg-bg-elevated border-border-default">
            {JOB_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value} className="text-text-primary text-sm">{t.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Posted Within */}
        <Select value={filters.postedWithin ?? ""} onValueChange={(val) => onChange({ ...filters, postedWithin: val ?? null })}>
          <SelectTrigger className="w-[130px] bg-bg-tertiary border-border-default text-text-primary text-sm rounded-[var(--radius-sm)] h-9">
            <SelectValue placeholder="发布时间">{postedLabel ?? "发布时间"}</SelectValue>
          </SelectTrigger>
          <SelectContent className="bg-bg-elevated border-border-default">
            {POSTED_WITHIN.map((t) => (
              <SelectItem key={t.value} value={t.value} className="text-text-primary text-sm">{t.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {activeFilters.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {activeFilters.map((f, i) => (
            <FilterTag key={`${f.label}-${i}`} label={f.label} onRemove={f.onRemove} />
          ))}
        </div>
      )}
    </div>
  )
}
