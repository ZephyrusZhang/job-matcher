/**
 * Turns `:job[<uuid>]` markers in an assistant answer into job-card elements.
 *
 * The agent embeds jobs by writing the marker into the Markdown it returns from
 * `final_answer`. This plugin rewrites those markers in the Markdown AST, so
 * `mdast-util-to-hast` emits `<job-card>` / `<job-ref>` elements and
 * `react-markdown` resolves them through its `components` map.
 *
 * Working on the AST rather than the raw string buys two things: markers inside
 * fenced or inline code are skipped for free (code is never a `text` node), and
 * a marker inside a list item or table cell keeps its surrounding structure.
 *
 * Keep the pattern in sync with `backend/app/utils/job_citations.py`.
 */

/** Matches the backend's `_JOB_RE`. */
const JOB_RE = /:job\[\s*([0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})\s*\]/g

/** Our own inline node type; unknown to mdast, which is what `hName` is for. */
const MARKER = "jobRef"

interface MdastNode {
  type: string
  value?: string
  children?: MdastNode[]
  data?: { hName?: string; hProperties?: Record<string, unknown> }
}

/**
 * A marker node.
 *
 * It deliberately carries no `value`: `mdast-util-to-hast`'s unknown-node
 * handler turns a valueless node into an element, which `hName` then renames.
 */
function marker(jobId: string): MdastNode {
  return {
    type: MARKER,
    children: [],
    data: { hName: "job-ref", hProperties: { jobId } },
  }
}

/** Split one text node around its markers, or `null` when it has none. */
function splitText(value: string): MdastNode[] | null {
  const matches = [...value.matchAll(JOB_RE)]
  if (matches.length === 0) return null

  const out: MdastNode[] = []
  let cursor = 0

  for (const match of matches) {
    const start = match.index ?? 0
    if (start > cursor) out.push({ type: "text", value: value.slice(cursor, start) })
    out.push(marker(match[1].toLowerCase()))
    cursor = start + match[0].length
  }
  if (cursor < value.length) out.push({ type: "text", value: value.slice(cursor) })

  return out
}

/** Whitespace between markers, including soft and hard line breaks. */
function isFiller(node: MdastNode): boolean {
  if (node.type === "break") return true
  return node.type === "text" && !(node.value ?? "").trim()
}

/**
 * Promote a marker-only paragraph to a block container.
 *
 * A full card is a `<div>`, which is invalid inside the `<p>` a paragraph would
 * render as. When the paragraph holds nothing but markers we replace the
 * paragraph itself, so the cards are block-level and the markup stays legal;
 * markers mixed into prose stay inline chips.
 */
function promote(paragraph: MdastNode): void {
  const children = paragraph.children ?? []
  const markers = children.filter((child) => child.type === MARKER)

  if (markers.length === 0) return
  if (!children.every((child) => child.type === MARKER || isFiller(child))) return

  paragraph.data = { hName: "job-card-group" }
  for (const node of markers) {
    if (node.data) node.data.hName = "job-card"
  }
  paragraph.children = markers
}

function walk(node: MdastNode): void {
  if (!node.children) return

  const next: MdastNode[] = []
  let changed = false

  for (const child of node.children) {
    if (child.type === "text" && typeof child.value === "string") {
      const parts = splitText(child.value)
      if (parts) {
        next.push(...parts)
        changed = true
        continue
      }
      next.push(child)
      continue
    }
    walk(child)
    next.push(child)
  }

  if (changed) node.children = next
  if (node.type === "paragraph") promote(node)
}

export function remarkJobEmbed() {
  return (tree: MdastNode): void => {
    walk(tree)
  }
}

/**
 * Drop a half-arrived marker at the very end of a streaming answer.
 *
 * The final answer accumulates token by token, so `:job[3f2a9c10-7b4d` is
 * briefly real text. Only the tail is trimmed; complete markers earlier in the
 * document are untouched.
 */
const PARTIAL_TAIL = /:(?:j(?:o(?:b(?:\[[^\]\n]*)?)?)?)?$/

export function trimPartialMarker(content: string): string {
  return content.replace(PARTIAL_TAIL, "")
}
