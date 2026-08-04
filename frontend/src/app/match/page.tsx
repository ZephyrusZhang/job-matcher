"use client"

import { useEffect, useState } from "react"
import { ChatMessageList } from "@/components/match/ChatMessageList"
import { MatchComposer } from "@/components/match/MatchComposer"
import { ReadOnlyOverlay } from "@/components/common/ReadOnlyOverlay"
import { useMatchChat } from "@/hooks/useMatchChat"
import { useConversationStore } from "@/store/useConversationStore"
import type { MatchScope } from "@/types/match"

export default function MatchPage() {
  const [scope, setScope] = useState<MatchScope>({ mode: "companies", company_ids: [] })
  const [resumeId, setResumeId] = useState<string | null>(null)

  // The conversation list is rendered by the app sidebar, so this page reads
  // the selection from the shared store rather than owning a panel of its own.
  const conversations = useConversationStore((s) => s.conversations)
  const activeId = useConversationStore((s) => s.activeId)
  const select = useConversationStore((s) => s.select)
  const refresh = useConversationStore((s) => s.fetch)
  const create = useConversationStore((s) => s.create)

  const chat = useMatchChat()
  const { loadHistory, clear } = chat

  const effectiveId = activeId ?? conversations[0]?.id ?? null

  useEffect(() => {
    if (effectiveId) {
      loadHistory(effectiveId)
    } else {
      clear()
    }
  }, [effectiveId, loadHistory, clear])

  const handleSend = async (content: string) => {
    // Sending with nothing selected starts a conversation.
    const conversationId = effectiveId ?? (await create())
    if (!conversationId) return
    select(conversationId)

    await chat.send(conversationId, { content, scope, resume_id: resumeId })
    await refresh()
  }

  const isEmpty = chat.messages.length === 0 && !chat.isStreaming && !chat.finalAnswer

  return (
    <ReadOnlyOverlay featureName="智能匹配">
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
              narration={chat.narration}
              toolEvents={chat.toolEvents}
              finalAnswer={chat.finalAnswer}
              jobIds={chat.jobIds}
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
      </div>
    </ReadOnlyOverlay>
  )
}
