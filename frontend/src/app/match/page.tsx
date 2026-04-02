"use client"

import { AnalysisPageLayout } from "@/components/report/AnalysisPageLayout"

export default function MatchPage() {
  return (
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
  )
}
