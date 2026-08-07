"use client"

import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { JobCard } from "@/components/match/JobCard"
import { JobRefChip } from "@/components/match/JobRefChip"
import { remarkJobEmbed, trimPartialMarker } from "@/lib/remarkJobEmbed"
import { cn } from "@/lib/utils"

interface MarkdownRendererProps {
  content: string
  isStreaming: boolean
}

export function MarkdownRenderer({ content, isStreaming }: MarkdownRendererProps) {
  if (!content) return null

  // While tokens are still arriving the tail may hold half a `:job[…]` marker,
  // which would otherwise flash as raw text before it completes.
  const body = isStreaming ? trimPartialMarker(content) : content

  return (
    <div className={cn("prose-invert max-w-none", isStreaming && "streaming-cursor")}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkJobEmbed]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-lg font-medium text-text-primary mt-6 mb-3">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-base font-medium text-text-primary mt-5 mb-2">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-medium text-text-primary border-l-2 border-blue-500 pl-3 mt-4 mb-2">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="text-sm text-text-primary leading-relaxed mb-3">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="text-sm text-text-primary list-disc pl-5 mb-3 space-y-1">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="text-sm text-text-primary list-decimal pl-5 mb-3 space-y-1">{children}</ol>
          ),
          li: ({ children }) => (
            <li className="text-sm text-text-primary leading-relaxed">{children}</li>
          ),
          strong: ({ children }) => (
            <strong className="text-text-primary font-medium">{children}</strong>
          ),
          em: ({ children }) => (
            <em className="text-text-secondary">{children}</em>
          ),
          hr: () => <hr className="border-border-subtle my-4" />,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-zinc-600 pl-3 text-sm text-text-secondary italic my-3">
              {children}
            </blockquote>
          ),

          // GFM tables were parsed but had no component overrides, so they fell
          // back to unstyled <table> and collapsed into run-together text.
          // Wide tables scroll inside their own container rather than pushing
          // the message column sideways.
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto rounded-md border border-border-subtle">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-bg-tertiary">{children}</thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-border-subtle">{children}</tbody>
          ),
          tr: ({ children }) => <tr>{children}</tr>,
          th: ({ children }) => (
            <th className="whitespace-nowrap px-3 py-2 text-left text-xs font-medium text-text-secondary">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-2 align-top text-sm text-text-primary">{children}</td>
          ),

          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-accent-main underline decoration-accent-main/30 underline-offset-2 transition-colors hover:decoration-accent-main"
            >
              {children}
            </a>
          ),
          code: ({ children, className }) => {
            // Fenced blocks arrive with a language class; bare ones are inline.
            const isBlock = Boolean(className)
            if (isBlock) {
              return <code className="font-mono text-xs leading-relaxed">{children}</code>
            }
            return (
              <code className="rounded bg-bg-tertiary px-1 py-0.5 font-mono text-[0.85em] text-text-primary">
                {children}
              </code>
            )
          },
          pre: ({ children }) => (
            <pre className="my-3 overflow-x-auto rounded-md border border-border-subtle bg-bg-secondary p-3 text-text-primary">
              {children}
            </pre>
          ),

          // Emitted by remarkJobEmbed, never written as literal markup: a
          // paragraph holding only `:job[…]` markers becomes a card group,
          // a marker inside prose becomes an inline chip.
          "job-card-group": ({ children }) => (
            <div className="my-3 grid gap-1.5 sm:grid-cols-2">{children}</div>
          ),
          "job-card": ({ jobId }) => (jobId ? <JobCard id={jobId} /> : null),
          "job-ref": ({ jobId }) => (jobId ? <JobRefChip id={jobId} /> : null),
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  )
}
