/**
 * Custom elements produced by `remarkJobEmbed`.
 *
 * `react-markdown`'s `Components` type is a mapped type over
 * `JSX.IntrinsicElements`, so these have to be declared before they can be
 * used as keys in its `components` map. They are never written by hand in JSX —
 * `mdast-util-to-hast` emits them from the plugin's `hName`.
 */
import type { ReactNode } from "react"

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "job-card": { jobId?: string }
      "job-ref": { jobId?: string }
      "job-card-group": { children?: ReactNode }
    }
  }
}
