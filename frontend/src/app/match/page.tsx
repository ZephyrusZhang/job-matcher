"use client"

import { Suspense } from "react"
import { useSearchParams } from "next/navigation"
import { MatchChat } from "@/components/match/MatchChat"
import { ReadOnlyOverlay } from "@/components/common/ReadOnlyOverlay"
import { CONVERSATION_PARAM } from "@/lib/matchRoutes"

function MatchPageBody() {
  const searchParams = useSearchParams()
  const conversationId = searchParams.get(CONVERSATION_PARAM)

  return <MatchChat conversationId={conversationId} />
}

export default function MatchPage() {
  return (
    <ReadOnlyOverlay featureName="智能匹配">
      {/* useSearchParams needs a Suspense boundary or Next opts the whole
          route out of static rendering at build time. */}
      <Suspense fallback={<div className="h-full" />}>
        <MatchPageBody />
      </Suspense>
    </ReadOnlyOverlay>
  )
}
