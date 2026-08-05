"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ChatMessageList } from "@/components/match/ChatMessageList"
import { MatchComposer } from "@/components/match/MatchComposer"
import { JobDetailPanel } from "@/components/jobs/JobDetailPanel"
import { useMatchChat } from "@/hooks/useMatchChat"
import { useConversationStore } from "@/store/useConversationStore"
import { useFavoriteStore } from "@/store/useFavoriteStore"
import { useJobDrawerStore } from "@/store/useJobDrawerStore"
import { conversationHref } from "@/lib/matchRoutes"
import type { MatchScope } from "@/types/match"

interface MatchChatProps {
  /** `null` on /match — a blank conversation that is not persisted yet. */
  conversationId: string | null
}

/**
 * Shared body for a blank chat and for one addressed by ?session_id.
 *
 * A conversation is created only when the first message is sent, so opening a
 * new chat leaves no empty row in the sidebar. On send the route switches to
 * the conversation's own URL.
 */
export function MatchChat({ conversationId }: MatchChatProps) {
  const [scope, setScope] = useState<MatchScope>({ mode: "companies", company_ids: [] })
  const [resumeId, setResumeId] = useState<string | null>(null)

  const router = useRouter()
  const create = useConversationStore((s) => s.create)
  const refresh = useConversationStore((s) => s.fetch)

  const drawerJobId = useJobDrawerStore((s) => s.jobId)
  const drawerOpen = useJobDrawerStore((s) => s.isOpen)
  const closeDrawer = useJobDrawerStore((s) => s.close)

  const favoriteIds = useFavoriteStore((s) => s.favoriteIds)
  const toggleFavorite = useFavoriteStore((s) => s.toggle)
  const fetchFavorites = useFavoriteStore((s) => s.fetchFavorites)

  const chat = useMatchChat()
  const { loadHistory, clear } = chat

  useEffect(() => {
    if (conversationId) {
      loadHistory(conversationId)
    } else {
      clear()
    }
  }, [conversationId, loadHistory, clear])

  // The drawer's favourite button needs to know the current state, and nothing
  // else on this page loads it.
  useEffect(() => {
    fetchFavorites()
  }, [fetchFavorites])

  const handleSend = async (content: string) => {
    let id = conversationId

    // First message of a blank chat is what brings the conversation into being.
    if (!id) {
      id = await create()
      if (!id) return
      router.push(conversationHref(id))
    }

    await chat.send(id, { content, scope, resume_id: resumeId })
    await refresh()
  }

  const isEmpty =
    chat.messages.length === 0 &&
    chat.steps.length === 0 &&
    !chat.isStreaming &&
    !chat.finalAnswer

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center">
            <h1 className="text-lg font-medium text-text-primary">智能匹配</h1>
            <p className="mt-2 max-w-md text-sm text-text-muted">
              选择简历与检索范围，用一句话描述你的诉求。
              方向、城市、学历等条件可以直接写在问题里。
            </p>
          </div>
        ) : (
          <ChatMessageList
            messages={chat.messages}
            steps={chat.steps}
            finalAnswer={chat.finalAnswer}
            status={chat.status}
            isStreaming={chat.isStreaming}
            error={chat.error}
          />
        )}
      </div>

      <MatchComposer
        scope={scope}
        onScopeChange={setScope}
        resumeId={resumeId}
        onResumeChange={setResumeId}
        onSend={handleSend}
        onStop={chat.stop}
        isStreaming={chat.isStreaming}
      />

      {/* Opened by the job cards embedded in an answer, which sit too deep in
          the Markdown tree to receive a callback. */}
      <JobDetailPanel
        jobId={drawerJobId}
        open={drawerOpen}
        onClose={closeDrawer}
        isFavorited={drawerJobId ? favoriteIds.has(drawerJobId) : false}
        onToggleFavorite={toggleFavorite}
      />
    </div>
  )
}
