"use client"

import { AnalysisPageLayout } from "@/components/report/AnalysisPageLayout"
import { ReadOnlyOverlay } from "@/components/common/ReadOnlyOverlay"

export default function MatchPage() {
  return (
    <ReadOnlyOverlay featureName="智能匹配">
      <AnalysisPageLayout
        title="智能匹配"
        description="从你收藏的岗位中，发现最适合你的岗位"
        generateEndpoint="/api/match/generate"
        reportEndpoint="/api/match/report"
        generateButtonLabel="生成推荐报告"
        reportTitle="推荐报告"
        startEvent="report_start"
        endEvent="report_end"
      />
    </ReadOnlyOverlay>
  )
}
