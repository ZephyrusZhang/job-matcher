"use client"

import { MatchChat } from "@/components/match/MatchChat"
import { ReadOnlyOverlay } from "@/components/common/ReadOnlyOverlay"

/** A blank conversation. Nothing is persisted until the first message. */
export default function MatchPage() {
  return (
    <ReadOnlyOverlay featureName="智能匹配">
      <MatchChat conversationId={null} />
    </ReadOnlyOverlay>
  )
}
