"use client"

import { useEffect, useState } from "react"
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
import { PageContainer } from "@/components/layout/PageContainer"
import type { Company } from "@/types/company"

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

export default function SettingsPage() {
  const [density, setDensity] = useState<string>("comfortable")
  const [language, setLanguage] = useState<string>("zh")
  const [companies, setCompanies] = useState<Company[]>([])

  useEffect(() => {
    fetch(`${API_BASE}/api/settings`)
      .then((r) => r.json())
      .then((d) => {
        if (d.success) {
          setDensity(d.data.display_density)
          setLanguage(d.data.language)
        }
      })
    fetch(`${API_BASE}/api/companies`)
      .then((r) => r.json())
      .then((d) => { if (d.success) setCompanies(d.data) })
  }, [])

  const updateSetting = (patch: Record<string, string>) => {
    fetch(`${API_BASE}/api/settings`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    })
  }

  return (
    <PageContainer>
      <div className="space-y-[var(--gap-section)]">
        <h1 className="text-xl font-medium text-text-primary">设置</h1>

        {/* Display Preferences */}
        <div className="bg-neutral-950 rounded-lg border border-neutral-800 p-6">
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

        {/* Company Table */}
        <div className="bg-neutral-950 rounded-lg border border-neutral-800 p-6">
          <h2 className="text-base font-medium text-text-primary">目标公司</h2>
          <Separator className="bg-neutral-800 my-4" />
          <p className="text-sm text-text-secondary mb-4">以下公司的岗位将被自动采集</p>

          <Table>
            <TableHeader>
              <TableRow className="border-b border-neutral-800 hover:bg-transparent">
                <TableHead className="text-text-secondary text-xs uppercase">公司名称</TableHead>
                <TableHead className="text-text-secondary text-xs uppercase">采集频率</TableHead>
                <TableHead className="text-text-secondary text-xs uppercase">上次采集</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {companies.map((company) => (
                <TableRow key={company.id} className="border-b border-neutral-800 hover:bg-transparent">
                  <TableCell className="text-sm text-text-primary">{company.name}</TableCell>
                  <TableCell className="text-sm text-text-primary">
                    每 {company.crawl_interval_hours} 小时
                  </TableCell>
                  <TableCell className="text-sm text-text-primary">
                    {formatRelativeTime(company.last_crawled_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </PageContainer>
  )
}
