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
    <div className="flex flex-col items-center justify-center py-16">
      {Icon && <Icon className="text-text-muted w-12 h-12 mb-4" />}
      <h3 className="text-text-primary text-base font-medium mb-2">{title}</h3>
      <p className="text-text-secondary text-sm mb-4">{description}</p>
      {actionLabel && onAction && (
        <Button variant="outline" className="text-accent-main" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
