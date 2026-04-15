import type { LucideIcon } from "lucide-react"
import { Button } from "@/components/ui/button"

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
}

export function EmptyState({ icon: Icon, title, description, actionLabel, onAction }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      {Icon && <Icon className="text-text-muted w-8 h-8 mb-3 stroke-[1.5]" />}
      <h3 className="text-text-primary text-sm font-medium mb-1">{title}</h3>
      <p className="text-text-muted text-xs">{description}</p>
      {actionLabel && onAction && (
        <Button variant="outline" size="sm" className="text-text-primary mt-4" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
