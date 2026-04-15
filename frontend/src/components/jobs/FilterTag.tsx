import { X } from "lucide-react"
import { cn } from "@/lib/utils"
import { CATEGORY_COLORS } from "@/lib/constants"

interface FilterTagProps {
  label: string
  onRemove: () => void
}

export function FilterTag({ label, onRemove }: FilterTagProps) {
  const categoryColor = CATEGORY_COLORS[label]

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-xs rounded-[var(--radius-sm)] px-2 py-1 border",
        categoryColor
          ? `${categoryColor} border-transparent`
          : "bg-blue-500/10 text-blue-400 border-blue-500/20"
      )}
    >
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
