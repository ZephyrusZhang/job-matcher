"use client"

import { useCallback, useEffect, useState } from "react"
import { ChatMessageList } from "@/components/match/ChatMessageList"
import { ConversationSidebar } from "@/components/match/ConversationSidebar"
import { MatchComposer } from "@/components/match/MatchComposer"
import { ReadOnlyOverlay } from "@/components/common/ReadOnlyOverlay"
import { useMatchChat } from "@/hooks/useMatchChat"
import {
  createConversation,
  deleteConversation,
  listConversations,
  renameConversation,
} from "@/lib/api/match"
import type { Conversation, MatchScope } from "@/types/match"

export default function MatchPage() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [scope, setScope] = useState<MatchScope>({ mode: "companies", company_ids: [] })
  const [resumeId, setResumeId] = useState<string | null>(null)

  const chat = useMatchChat()
  const { loadHistory, clear } = chat

  const refreshConversations = useCallback(async () => {
    try {
      const res = await listConversations()
      const list = res.data ?? []
      setConversations(list)
      return list
    } catch {
      setConversations([])
      return []
    }
  }, [])

  useEffect(() => {
    refreshConversations()
  }, [refreshConversations])

  // Default to the most recent conversation without writing it back to state,
  // so an explicit selection still wins and no effect sets state on mount.
  const effectiveId = activeId ?? conversations[0]?.id ?? null

  useEffect(() => {
    if (effectiveId) {
      loadHistory(effectiveId)
    } else {
      clear()
    }
  }, [effectiveId, loadHistory, clear])

  const handleCreate = async () => {
    const res = await createConversation().catch(() => null)
    if (res?.data) {
      setActiveId(res.data.id)
      await refreshConversations()
    }
  }

  const handleRename = async (id: string, title: string) => {
    await renameConversation(id, title).catch(() => null)
    await refreshConversations()
  }

  const handleDelete = async (id: string) => {
    await deleteConversation(id).catch(() => null)
    const list = await refreshConversations()
    if (effectiveId === id) setActiveId(list.length > 0 ? list[0].id : null)
  }

  const handleSend = async (content: string) => {
    let conversationId = effectiveId

    // Sending with nothing selected starts a conversation.
    if (!conversationId) {
      const res = await createConversation().catch(() => null)
      if (!res?.data) return
      conversationId = res.data.id
      setActiveId(conversationId)
    }

    await chat.send(conversationId, { content, scope, resume_id: resumeId })
    await refreshConversations()
  }

  const isEmpty = chat.messages.length === 0 && !chat.isStreaming && !chat.finalAnswer

  return (
    <ReadOnlyOverlay featureName="智能匹配">
      <div className="flex h-[calc(100vh-3.5rem)]">
        <ConversationSidebar
          conversations={conversations}
          activeId={effectiveId}
          onSelect={setActiveId}
          onCreate={handleCreate}
          onRename={handleRename}
          onDelete={handleDelete}
        />

        <div className="flex min-w-0 flex-1 flex-col">
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
      </div>
    </ReadOnlyOverlay>
  )
}
