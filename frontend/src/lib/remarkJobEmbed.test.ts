import { describe, expect, it } from "vitest"
import { unified } from "unified"
import remarkParse from "remark-parse"
import remarkGfm from "remark-gfm"
import remarkRehype from "remark-rehype"
import { remarkJobEmbed, trimPartialMarker } from "./remarkJobEmbed"

const A = "3f2a9c10-7b4d-4e88-9a15-c0d3e5f61a27"
const B = "8c1e04b2-33af-4d9e-b6c7-1e2f4a5b9d80"

interface HastNode {
  type: string
  tagName?: string
  properties?: Record<string, unknown>
  children?: HastNode[]
  value?: string
}

/** Run the real pipeline react-markdown uses, down to hast. */
function toHast(markdown: string): HastNode {
  return unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkJobEmbed)
    .use(remarkRehype)
    .runSync(unified().use(remarkParse).use(remarkGfm).parse(markdown)) as unknown as HastNode
}

function collect(node: HastNode, tagName: string, out: HastNode[] = []): HastNode[] {
  if (node.tagName === tagName) out.push(node)
  for (const child of node.children ?? []) collect(child, tagName, out)
  return out
}

describe("remarkJobEmbed", () => {
  it("promotes a marker-only paragraph to a block card group", () => {
    const tree = toHast(`推荐这个：\n\n:job[${A}]\n\n后续说明。`)

    const groups = collect(tree, "job-card-group")
    expect(groups).toHaveLength(1)
    expect(collect(tree, "job-card").map((n) => n.properties?.jobId)).toEqual([A])
    // The block form must not end up inside a paragraph.
    expect(collect(tree, "p").flatMap((p) => collect(p, "job-card"))).toHaveLength(0)
  })

  it("renders a marker inside prose as an inline chip", () => {
    const tree = toHast(`也可以看看 :job[${B}]，方向接近。`)

    expect(collect(tree, "job-card-group")).toHaveLength(0)
    expect(collect(tree, "job-ref").map((n) => n.properties?.jobId)).toEqual([B])
    expect(collect(tree, "p")[0].children?.map((c) => c.tagName ?? c.type)).toEqual([
      "text",
      "job-ref",
      "text",
    ])
  })

  it("groups several markers that share a paragraph", () => {
    const tree = toHast(`:job[${A}]\n:job[${B}]`)

    expect(collect(tree, "job-card-group")).toHaveLength(1)
    expect(collect(tree, "job-card").map((n) => n.properties?.jobId)).toEqual([A, B])
  })

  it("keeps a paragraph inline when a marker is mixed with real text", () => {
    const tree = toHast(`:job[${A}] 值得优先投`)

    expect(collect(tree, "job-card-group")).toHaveLength(0)
    expect(collect(tree, "job-ref")).toHaveLength(1)
  })

  it("leaves markers inside fenced and inline code alone", () => {
    const fenced = toHast("```\n:job[" + A + "]\n```")
    expect(collect(fenced, "job-ref")).toHaveLength(0)
    expect(collect(fenced, "job-card")).toHaveLength(0)

    const inline = toHast("格式是 `:job[" + A + "]` 这样")
    expect(collect(inline, "job-ref")).toHaveLength(0)
  })

  it("works inside list items and table cells", () => {
    const list = toHast(`- 首选 :job[${A}]`)
    expect(collect(collect(list, "li")[0], "job-ref")).toHaveLength(1)

    const table = toHast(`| 岗位 |\n| --- |\n| :job[${B}] |`)
    expect(collect(collect(table, "td")[0], "job-ref")).toHaveLength(1)
  })

  it("normalizes uppercase ids and tolerates padding", () => {
    const tree = toHast(`看 :job[  ${A.toUpperCase()}  ] 吧`)
    expect(collect(tree, "job-ref")[0].properties?.jobId).toBe(A)
  })

  it("ignores malformed ids", () => {
    expect(collect(toHast(`:job[${A.slice(0, -1)}]`), "job-ref")).toHaveLength(0)
    expect(collect(toHast(":job[not-a-uuid]"), "job-ref")).toHaveLength(0)
  })
})

describe("trimPartialMarker", () => {
  it("drops an unterminated marker at the tail", () => {
    expect(trimPartialMarker("推荐 :job[3f2a9c10-7b4d")).toBe("推荐 ")
    expect(trimPartialMarker("推荐 :job[")).toBe("推荐 ")
    expect(trimPartialMarker("推荐 :job")).toBe("推荐 ")
    expect(trimPartialMarker("推荐 :")).toBe("推荐 ")
  })

  it("leaves complete markers and ordinary text untouched", () => {
    expect(trimPartialMarker(`推荐 :job[${A}]`)).toBe(`推荐 :job[${A}]`)
    expect(trimPartialMarker(`:job[${A}] 然后继续写`)).toBe(`:job[${A}] 然后继续写`)
    expect(trimPartialMarker("普通结尾。")).toBe("普通结尾。")
  })
})
