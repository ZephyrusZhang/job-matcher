"use client"

import { useState } from "react"
import { Check, ChevronDown, Loader2, X } from "lucide-react"
import { cn } from "@/lib/utils"
import type { ToolEvent } from "@/types/match"

/** Render tool arguments compactly enough to sit on the collapsed row. */
function summarizeArgs(args: ToolEvent["args"]): string {
  if (!args) return ""
  if (typeof args === "string") return args.slice(0, 60)

  const parts: string[] = []
  for (const [key, value] of Object.entries(args)) {
    if (value === null || value === undefined || value === "") continue
    if (Array.isArray(value)) {
      if (value.length === 0) continue
      parts.push(value.join("·"))
    } else {
      parts.push(String(value))
    }
    if (key === "top_k") parts.pop()
  }
  return parts.join(" / ").slice(0, 60)
}

function ToolRow({ event }: { event: ToolEvent }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetail = Boolean(event.args && Object.keys(event.args).length > 0)

  return (
    <div className="text-xs">
      <button
        type="button"
        onClick={() => hasDetail && setExpanded((v) => !v)}
        className={cn(
          "flex w-full items-center gap-2 rounded px-2 py-1 text-left transition-colors",
          hasDetail && "hover:bg-bg-tertiary",
        )}
      >
        <span className="shrink-0">
          {event.pending ? (
            <Loader2 className="h-3 w-3 animate-spin text-accent" />
          ) : event.ok ? (
            <Check className="h-3 w-3 text-emerald-500" />
          ) : (
            <X className="h-3 w-3 text-red-500" />
          )}
        </span>

        <span className="shrink-0 font-medium text-text-secondary">
          {event.label || event.name}
        </span>

        <span className="truncate text-text-muted">{summarizeArgs(event.args)}</span>

        <span className="ml-auto flex shrink-0 items-center gap-1.5 text-text-muted">
          {event.summary && <span>{event.summary}</span>}
          {hasDetail && (
            <ChevronDown
              className={cn("h-3 w-3 transition-transform", expanded && "rotate-180")}
            />
          )}
        </span>
      </button>

      {expanded && (
        <pre className="mx-2 mb-1 overflow-x-auto rounded bg-bg-tertiary px-2 py-1.5 text-[11px] leading-relaxed text-text-muted">
          {JSON.stringify(event.args, null, 2)}
        </pre>
      )}
    </div>
  )
}

interface ToolTimelineProps {
  events: ToolEvent[]
}

/**
 * The agent's tool calls for one turn, newest last.
 *
 * Collapsed to a single line each; expanding shows the full arguments. The
 * `final_answer` tool is deliberately absent — it is the answer, not a step.
 */
export function ToolTimeline({ events }: ToolTimelineProps) {
  if (events.length === 0) return null

  return (
    <div className="mb-3 space-y-0.5 rounded-md border border-border-subtle bg-bg-secondary/60 p-1">
      {events.map((event) => (
        <ToolRow key={event.call_id} event={event} />
      ))}
    </div>
  )
}
