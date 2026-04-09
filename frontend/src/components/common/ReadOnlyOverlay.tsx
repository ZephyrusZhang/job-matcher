"use client"

import { Lock, ExternalLink } from "lucide-react"
import type { ReactNode } from "react"
import { IS_READ_ONLY_MODE } from "@/lib/readonly"

interface ReadOnlyOverlayProps {
  /** The underlying page content — rendered beneath the mask. */
  children: ReactNode
  /** Override the default feature name shown on the mask card. */
  featureName?: string
  /** Override the default long description. */
  description?: string
  /** Optional repo URL for the "self-host" link. */
  repoUrl?: string
}

/**
 * Full-page mask shown on top of pages that are disabled in the cloud demo.
 *
 * The underlying page still mounts (so route-level code doesn't need to
 * branch), but it's rendered with `aria-hidden` + `pointer-events-none` and
 * a dimmed visual treatment while the overlay sits on top.
 *
 * When `NEXT_PUBLIC_READ_ONLY_MODE` is not set, this component is a pass-through.
 */
export function ReadOnlyOverlay({
  children,
  featureName = "该功能",
  description = "该功能在演示环境中不可用，仅用于展示。如需使用完整功能，请参考项目文档自行部署。",
  repoUrl = "https://github.com/ZephyrusZhang/job-matcher",
}: ReadOnlyOverlayProps) {
  if (!IS_READ_ONLY_MODE) {
    return <>{children}</>
  }

  return (
    <div className="relative">
      {/* Underlying page, dimmed and non-interactive */}
      <div
        aria-hidden
        inert
        className="pointer-events-none select-none blur-[2px] opacity-30"
      >
        {children}
      </div>

      {/* Full-area mask */}
      <div className="absolute inset-0 z-20 flex items-start justify-center pt-24 md:pt-32 px-4">
        <div className="w-full max-w-md rounded-[var(--radius-sm)] border border-border-default bg-bg-elevated shadow-xl p-6 md:p-8">
          <div className="flex flex-col items-center text-center">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-bg-tertiary border border-border-default">
              <Lock className="h-5 w-5 text-text-muted" />
            </div>

            <h3 className="text-text-primary text-base font-medium mb-2">
              {featureName}在演示环境中不可用
            </h3>

            <p className="text-text-secondary text-sm leading-relaxed mb-5">
              {description}
            </p>

            {repoUrl && (
              <a
                href={repoUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 text-xs text-text-muted hover:text-text-primary transition-colors cursor-pointer"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                查看源码 / 自行部署
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
