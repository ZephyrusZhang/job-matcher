"use client"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { Company } from "@/types/company"
import type { FavoriteSummary } from "@/types/favorite"

interface CompanySelectorProps {
  companies: Company[]
  value: string | null
  onChange: (id: string) => void
  showFavoriteCount?: boolean
  favoriteSummary?: FavoriteSummary[]
}

export function CompanySelector({
  companies,
  value,
  onChange,
  showFavoriteCount = false,
  favoriteSummary = [],
}: CompanySelectorProps) {
  const getFavoriteCount = (companyId: string) => {
    return favoriteSummary.find((s) => s.company_id === companyId)?.count ?? 0
  }

  const selectedCompany = companies.find((c) => c.id === value)
  const getDisplayText = (company: Company) => {
    const favCount = getFavoriteCount(company.id)
    return showFavoriteCount
      ? `${company.name}（已收藏 ${favCount} 个岗位）`
      : `${company.name}（${company.job_count} 个岗位）`
  }

  return (
    <Select value={value ?? null} onValueChange={(val) => { if (val) onChange(val) }}>
      <SelectTrigger className="w-full bg-neutral-900 border-neutral-800 rounded-lg text-white">
        <SelectValue placeholder="选择公司">
          {selectedCompany ? getDisplayText(selectedCompany) : "选择公司"}
        </SelectValue>
      </SelectTrigger>
      <SelectContent className="bg-neutral-900 border-neutral-800">
        {companies.map((company) => {
          const favCount = getFavoriteCount(company.id)
          const isDisabled = showFavoriteCount && favCount === 0
          return (
            <SelectItem
              key={company.id}
              value={company.id}
              disabled={isDisabled}
              className="text-text-primary"
            >
              {getDisplayText(company)}
            </SelectItem>
          )
        })}
      </SelectContent>
    </Select>
  )
}
