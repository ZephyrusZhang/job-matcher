import { X } from "lucide-react"

interface FilterTagProps {
  label: string
  onRemove: () => void
}

export function FilterTag({ label, onRemove }: FilterTagProps) {
  return (
    <span className="inline-flex items-center gap-1 bg-bg-tertiary text-text-primary text-xs rounded-[var(--radius-sm)] px-2 py-1">
      {label}
      <button
        onClick={onRemove}
        className="hover:text-accent-main cursor-pointer"
        aria-label={`移除筛选: ${label}`}
      >
        <X className="h-3 w-3" />
      </button>
    </span>
  )
}
