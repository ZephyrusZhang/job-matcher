"use client"

import { Textarea } from "@/components/ui/textarea"

interface PreferencesFormProps {
  interest: string
  additional: string
  onInterestChange: (val: string) => void
  onAdditionalChange: (val: string) => void
}

export function PreferencesForm({
  interest,
  additional,
  onInterestChange,
  onAdditionalChange,
}: PreferencesFormProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-medium text-text-primary">岗位兴趣方向</label>
        <Textarea
          value={interest}
          onChange={(e) => onInterestChange(e.target.value)}
          placeholder="例如：对前端开发方向最感兴趣，也愿意尝试全栈方向..."
          className="bg-bg-tertiary border-none text-text-primary placeholder:text-text-muted rounded-[var(--radius-sm)] min-h-[80px] resize-none"
        />
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium text-text-primary">
          其他要求或补充说明
          <span className="text-text-muted font-normal ml-1">（可选）</span>
        </label>
        <Textarea
          value={additional}
          onChange={(e) => onAdditionalChange(e.target.value)}
          placeholder="例如：希望有远程或混合办公选项，偏好有导师制度的团队..."
          className="bg-bg-tertiary border-none text-text-primary placeholder:text-text-muted rounded-[var(--radius-sm)] min-h-[80px] resize-none"
        />
      </div>
    </div>
  )
}
