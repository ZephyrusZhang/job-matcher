"use client"

import { AnalysisPageLayout } from "@/components/report/AnalysisPageLayout"
import { ReadOnlyOverlay } from "@/components/common/ReadOnlyOverlay"

export default function ComparePage() {
  return (
    <ReadOnlyOverlay featureName="岗位对比">
      <AnalysisPageLayout
        title="岗位对比"
        description="对比你的意向岗位，找出最优选择"
        generateEndpoint="/api/compare/generate"
        reportEndpoint="/api/compare/report"
        generateButtonLabel="生成对比报告"
        reportTitle="对比分析报告"
        startEvent="compare_start"
        endEvent="compare_end"
      />
    </ReadOnlyOverlay>
  )
}
