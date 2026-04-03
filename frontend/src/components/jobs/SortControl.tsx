"use client"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const SORT_OPTIONS = [
  { value: "posted_date_desc", label: "最新优先" },
  { value: "posted_date_asc", label: "最早优先" },
  { value: "title_asc", label: "标题 A-Z" },
  { value: "title_desc", label: "标题 Z-A" },
]

interface SortControlProps {
  value: string
  onChange: (value: string) => void
}

export function SortControl({ value, onChange }: SortControlProps) {
  const currentLabel = SORT_OPTIONS.find((o) => o.value === value)?.label ?? "排序"

  return (
    <Select value={value} onValueChange={(val) => { if (val) onChange(val) }}>
      <SelectTrigger className="w-[140px] bg-neutral-900 border-neutral-800 text-white text-sm rounded-lg h-9">
        <SelectValue placeholder={currentLabel}>{currentLabel}</SelectValue>
      </SelectTrigger>
      <SelectContent className="bg-neutral-900 border-neutral-800">
        {SORT_OPTIONS.map((opt) => (
          <SelectItem key={opt.value} value={opt.value} className="text-text-primary text-sm">
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
