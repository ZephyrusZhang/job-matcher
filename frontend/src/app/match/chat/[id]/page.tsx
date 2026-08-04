"use client"

import { useParams } from "next/navigation"
import { MatchChat } from "@/components/match/MatchChat"
import { ReadOnlyOverlay } from "@/components/common/ReadOnlyOverlay"

/** An existing conversation, identified by the `id` route segment. */
export default function MatchConversationPage() {
  const params = useParams<{ id: string }>()
  const id = typeof params?.id === "string" ? params.id : null

  return (
    <ReadOnlyOverlay featureName="智能匹配">
      <MatchChat conversationId={id} />
    </ReadOnlyOverlay>
  )
}
