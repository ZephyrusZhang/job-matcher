import { X } from "lucide-react"
import { CATEGORY_COLORS } from "@/lib/constants"

interface FilterTagProps {
  label: string
  onRemove: () => void
}

export function FilterTag({ label, onRemove }: FilterTagProps) {
  const categoryColor = CATEGORY_COLORS[label]
  const colorClass = categoryColor
    ? categoryColor
    : "bg-blue-500/10 text-blue-400 border-blue-500/20"

  return (
    <span className={`inline-flex items-center gap-1 border text-xs rounded-[var(--radius-sm)] px-2 py-1 ${categoryColor ? `${colorClass} border-transparent` : colorClass}`}>
      {label}
      <button
        onClick={onRemove}
        className="hover:opacity-70 cursor-pointer"
        aria-label={`移除筛选: ${label}`}
      >
        <X className="h-3 w-3" />
      </button>
    </span>
  )
}
