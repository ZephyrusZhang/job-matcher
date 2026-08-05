import type { MatchSnapshot, TraceStep } from "@/types/match"

/**
 * Folds a turn's event stream into the state the chat renders.
 *
 * Everything here is a pure fold over the frames, which is what makes
 * reconnecting safe: the server can hand back a complete snapshot at any point
 * and the accumulator is simply rebuilt from it, with no reconciliation against
 * whatever the client had folded before. That only works if nothing outside
 * ever appends to the result — hence `toState()` returns freshly built values
 * and callers assign them wholesale rather than concatenating.
 *
 * Two numbers travel with each frame and are easy to confuse:
 *
 * - `index` is *which step* a frame belongs to. Hundreds of `narration` frames
 *   share one index and fold into a single step.
 * - `seq` is *which frame* it is. Monotonic within the turn, used to drop
 *   frames a snapshot already accounts for.
 */
export interface AccumulatorState {
  steps: TraceStep[]
  finalAnswer: string
  seq: number
  status: MatchSnapshot["status"]
  messageId: string | null
}

export class MatchTurnAccumulator {
  private steps: TraceStep[] = []
  private finalAnswer = ""
  private seq = 0
  private status: MatchSnapshot["status"] = "running"
  private messageId: string | null = null

  /** Rebuild from a server snapshot, discarding whatever was folded before. */
  static fromSnapshot(snapshot: {
    message_id?: string | null
    seq?: number
    status?: MatchSnapshot["status"]
    steps?: TraceStep[]
    final_answer?: string | null
  }): MatchTurnAccumulator {
    const acc = new MatchTurnAccumulator()
    acc.messageId = snapshot.message_id ?? null
    acc.seq = snapshot.seq ?? 0
    acc.status = snapshot.status ?? "running"
    acc.steps = (snapshot.steps ?? []).map((step) => ({ ...step }))
    acc.finalAnswer = snapshot.final_answer ?? ""
    return acc
  }

  /**
   * Fold one live frame.
   *
   * Frames at or below the current `seq` are already accounted for — the normal
   * path never produces them, but a reconnect that re-snapshots can.
   */
  push(event: string, data: Record<string, unknown>, seq: number | null): void {
    if (seq !== null) {
      if (seq <= this.seq) return
      this.seq = seq
    }

    switch (event) {
      case "narration": {
        const index = data.index as number
        const content = (data.content as string) ?? ""
        const at = this.steps.findIndex((s) => s.index === index)
        if (at >= 0) {
          this.steps[at] = {
            ...this.steps[at],
            content: (this.steps[at].content ?? "") + content,
          }
        } else {
          this.steps = [...this.steps, { type: "narration", index, content }]
        }
        break
      }

      case "tool_start":
        this.steps = [
          ...this.steps,
          {
            type: "tool",
            index: data.index as number,
            call_id: data.call_id as string,
            name: data.name as string,
            label: data.label as string,
            args: data.args as TraceStep["args"],
            ok: true,
            summary: "",
            pending: true,
          },
        ]
        break

      case "tool_end":
        this.steps = this.steps.map((step) =>
          step.call_id === data.call_id
            ? {
                ...step,
                pending: false,
                ok: (data.ok as boolean) ?? true,
                summary: (data.summary as string) ?? "",
                observation: (data.observation as string) ?? "",
                count: (data.count as number | null) ?? null,
                duration_ms: (data.duration_ms as number | null) ?? null,
              }
            : step,
        )
        break

      case "final_delta":
        this.finalAnswer += (data.content as string) ?? ""
        break

      case "message_end":
        this.status = (data.status as MatchSnapshot["status"]) ?? "completed"
        break

      // `tool_args` streams raw argument text; the settled value arrives with
      // `tool_start`, so there is nothing to fold.
      default:
        break
    }

    this.steps.sort((a, b) => a.index - b.index)
  }

  /**
   * Project the fold into what the chat renders.
   *
   * The model is told to finish by calling `final_answer`, but it sometimes
   * just writes the answer as plain text instead. The server settles that the
   * same way at the end of the turn — the trailing narration becomes the
   * answer — and applying the rule here too is what lets such an answer stream
   * into the message body as it arrives, rather than sitting invisibly inside
   * the muted trace and appearing all at once when the turn closes.
   */
  toState(): AccumulatorState {
    let steps = this.steps
    let finalAnswer = this.finalAnswer

    const last = steps[steps.length - 1]
    if (!finalAnswer && last?.type === "narration") {
      finalAnswer = last.content ?? ""
      steps = steps.slice(0, -1)
    }

    return {
      steps,
      finalAnswer,
      seq: this.seq,
      status: this.status,
      messageId: this.messageId,
    }
  }
}
