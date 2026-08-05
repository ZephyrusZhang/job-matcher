import { describe, expect, it } from "vitest"
import { MatchTurnAccumulator } from "./matchAccumulator"

/** One turn's frames, as the server numbers them. */
const FRAMES: Array<[string, Record<string, unknown>, number]> = [
  ["narration", { index: 0, content: "好的" }, 1],
  ["narration", { index: 0, content: "，我先看看" }, 2],
  ["tool_start", { index: 1, call_id: "c1", name: "search_jobs", label: "检索岗位", args: {} }, 3],
  ["tool_end", { index: 1, call_id: "c1", ok: true, summary: "2 条", observation: "…", count: 2, duration_ms: 900 }, 4],
  ["narration", { index: 2, content: "分析完成" }, 5],
  ["final_delta", { content: "## 推荐" }, 6],
  ["final_delta", { content: "一：后端" }, 7],
]

function foldAll(frames = FRAMES): MatchTurnAccumulator {
  const acc = new MatchTurnAccumulator()
  for (const [event, data, seq] of frames) acc.push(event, { ...data }, seq)
  return acc
}

describe("MatchTurnAccumulator", () => {
  it("folds frames into ordered steps and the answer", () => {
    const s = foldAll().toState()

    expect(s.seq).toBe(7)
    expect(s.finalAnswer).toBe("## 推荐一：后端")
    expect(s.steps.map((x) => x.type)).toEqual(["narration", "tool", "narration"])
    expect(s.steps[0].content).toBe("好的，我先看看")
    expect(s.steps[1].summary).toBe("2 条")
    expect(s.steps[1].pending).toBe(false)
  })

  it("is idempotent — replaying the same frames changes nothing", () => {
    const acc = foldAll()
    const once = acc.toState()

    for (const [event, data, seq] of FRAMES) acc.push(event, { ...data }, seq)

    const twice = acc.toState()
    expect(twice.finalAnswer).toBe(once.finalAnswer)
    expect(twice.steps).toEqual(once.steps)
    expect(twice.seq).toBe(once.seq)
  })

  it("does not double the answer when a snapshot overlaps live frames", () => {
    // The failure this guards against: hydrate to seq 5, then let the server
    // resend 3..7 — every frame passes a naive check and the text doubles.
    const full = foldAll().toState()

    const acc = MatchTurnAccumulator.fromSnapshot({
      message_id: "m1",
      seq: 5,
      status: "running",
      steps: foldAll(FRAMES.slice(0, 5)).toState().steps,
      final_answer: "",
    })
    for (const [event, data, seq] of FRAMES.slice(2)) acc.push(event, { ...data }, seq)

    const resumed = acc.toState()
    expect(resumed.finalAnswer).toBe(full.finalAnswer)
    expect(resumed.steps[0].content).toBe("好的，我先看看")
  })

  it("snapshot replaces the accumulator instead of merging into it", () => {
    const acc = foldAll()
    const replaced = MatchTurnAccumulator.fromSnapshot({
      message_id: "m1",
      seq: 99,
      status: "running",
      steps: [{ type: "narration", index: 0, content: "服务端版本" }],
      final_answer: "服务端正文",
    })

    expect(replaced.toState().finalAnswer).toBe("服务端正文")
    expect(replaced.toState().steps).toHaveLength(1)
    // The old instance is untouched — nothing is shared between them.
    expect(acc.toState().finalAnswer).toBe("## 推荐一：后端")
  })

  it("a snapshot and the frames it was folded from agree", () => {
    // The property the resume path rests on: whichever projection the client
    // receives, it lands in the same place.
    const live = foldAll().toState()
    const viaSnapshot = MatchTurnAccumulator.fromSnapshot({
      message_id: "m1",
      seq: live.seq,
      status: "running",
      steps: live.steps,
      final_answer: live.finalAnswer,
    }).toState()

    expect(viaSnapshot.steps).toEqual(live.steps)
    expect(viaSnapshot.finalAnswer).toEqual(live.finalAnswer)
    expect(viaSnapshot.seq).toEqual(live.seq)
  })

  it("renders a trailing narration as the body when final_answer never came", () => {
    // The model answered in plain text instead of calling `final_answer`.
    // Without this the answer would accumulate invisibly in the muted trace
    // and only become the body once the server settled the turn.
    const acc = new MatchTurnAccumulator()
    acc.push("narration", { index: 0, content: "好的，我先看看" }, 1)
    acc.push("tool_start", { index: 1, call_id: "c1", name: "search_jobs", label: "检索岗位", args: {} }, 2)
    acc.push("tool_end", { index: 1, call_id: "c1", ok: true, summary: "2 条" }, 3)
    acc.push("narration", { index: 2, content: "# 分析\n\n第一个岗位…" }, 4)

    const s = acc.toState()
    expect(s.finalAnswer).toBe("# 分析\n\n第一个岗位…")
    // The interstitial line stays in the trace rather than being glued to the
    // front of the answer.
    expect(s.steps.map((x) => x.type)).toEqual(["narration", "tool"])
    expect(s.steps[0].content).toBe("好的，我先看看")
  })

  it("leaves narration in the trace once final_answer is streaming", () => {
    const acc = new MatchTurnAccumulator()
    acc.push("narration", { index: 0, content: "让我查一下" }, 1)
    acc.push("final_delta", { content: "正式回复" }, 2)

    const s = acc.toState()
    expect(s.finalAnswer).toBe("正式回复")
    expect(s.steps).toHaveLength(1)
  })

  it("records the terminal status from message_end", () => {
    const acc = foldAll()
    acc.push("message_end", { message_id: "m1", status: "stopped" }, 8)
    expect(acc.toState().status).toBe("stopped")
  })

  it("ignores tool_args, which carries no foldable state", () => {
    const acc = foldAll()
    const before = acc.toState()
    acc.push("tool_args", { name: "search_jobs", delta: '{"query":' }, 8)
    const after = acc.toState()

    expect(after.steps).toEqual(before.steps)
    expect(after.finalAnswer).toBe(before.finalAnswer)
    expect(after.seq).toBe(8)
  })
})
