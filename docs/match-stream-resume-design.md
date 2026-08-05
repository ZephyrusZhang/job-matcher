# /match 断流恢复与双向停止 · 方案设计

> 状态：**待实现**（设计已定稿，等待对 §6 三个取舍的确认）
>
> 目标：用户刷新页面后回到正在运行的对话，仍能接着之前的内容继续流式输出；
> 用户点击停止时，前端停止接收，后端对应的 agent run 也真正停止。
>
> 参考：内部 Artifact《Data Agent v2 · 断流恢复走查》—— 事件流协议与前端三层分工。
> 本文说明借鉴了什么、偏离了什么、以及为什么。

---

## 1. 今天实际会发生什么

### 1.1 刷新 = 整轮产出丢失

`app/services/match_service.py::stream_turn` 是被 `StreamingResponse` 迭代的 async
generator。客户端断开时 Starlette 关闭生成器，`GeneratorExit` 在当前 `yield` 处抛出：

```python
async for frame in self._drain(queue, agent_task):
    yield frame                                     # ← GeneratorExit 在这里抛出
    ...
finally:
    reset_turn_context(token)                       # ← 会执行

job_ids = await self._resolve_citations(...)        # ← 永不执行
await conv_model.add_message(...)                   # ← 永不执行
yield _sse("message_end", ...)                      # ← 永不执行
```

后果有两个：

1. **这一轮的全部产出丢失。** `add_message` 是整轮唯一的落库点，它没跑，
   数据库里连一条 assistant 行都不会有。
2. **`agent_task` 变成孤儿。** `_drain` 末尾的 `agent_task.cancel()` 同样在生成器
   关闭时被跳过，任务没人 cancel、没人 await，继续烧 token 直到
   `TURN_TIMEOUT_SECONDS = 300` 超时。

### 1.2 停止是单边的

`frontend/src/hooks/useMatchChat.ts`：

```ts
const stop = useCallback(() => {
  abortRef.current = true
  setIsStreaming(false)
}, [])
```

只是让前端不再读流。**后端完全不知情**，agent 会跑完整轮、消耗完整的 token。

### 1.3 前端折叠不是幂等的

```ts
setFinalAnswer((prev) => prev + (event.data?.content ?? ""))   // 非幂等
next[at] = { ...next[at], content: (next[at].content ?? "") + content }   // 非幂等
```

任何形式的重放都会导致内容翻倍。这是恢复机制的前置障碍。

---

## 2. 已核实的前提

实现依赖以下事实，均已在代码中确认：

| 事实 | 位置 |
|---|---|
| `BaseAgent.run` 已支持 `cancel_check: Callable[[], bool]` 参数 | `app/core/langgraph/base.py:430` |
| `cancel_check` 在 `_chat` 节点顶部被 poll，抛 `AgentCancelled` | `base.py:226-228` |
| `cancel_check` 在 `_tool_call` 节点顶部被 poll，抛 `AgentCancelled` | `base.py:263-265` |
| `match_messages` 无 `status` / `seq` 列 | `app/database.py:98-109` |
| `add_message` 只有 INSERT，没有 UPDATE 路径 | `app/models/match_conversation.py:125` |
| 一轮真实对话产生 535 个 `final_delta` 事件 | 实测（bilibili 前端实习，4 次工具调用） |
| 逐帧落库（535 次 `UPDATE`+`commit`，37KB blob）耗时 208ms / WAL 84ms | 实测，见 §6.3 |

---

## 2.5 `index` 与 `seq` 是两个正交的轴

**实现时最容易混的一处，先单独说明。**

`index` 是**这一帧属于哪一段**，取值是该 step 在 `steps[]` 数组里的下标。
见 `app/services/match_stream.py:191-196`：

```python
def _append_narration(self, text: str) -> None:
    if not self.steps or self.steps[-1]["type"] != "narration":
        self.steps.append({"type": "narration", "index": len(self.steps), "content": ""})
    self.steps[-1]["content"] += text
    self._emit("narration", {"index": self.steps[-1]["index"], "content": text})
```

`index = len(self.steps)`，就是数组下标。一轮真实 trace：

```
[0] narration  19字                       ← 19 个 token 全部带 index:0
[1] tool  get_resume_profile  obs=2107字   ← index:1
[2] tool  list_favorites      obs=4017字   ← index:2
[3] narration  27字                       ← 27 个 token 全部带 index:3
[4] tool  get_job_detail      obs=975字    ← index:4
[5] narration 638字
```

`seq` 是本方案新增的，含义是**这是本轮第几帧**。

| | 回答的问题 | 单调？ | 谁在用 |
|---|---|---|---|
| `index` | 这一帧属于哪一段 | 否，同段内重复 | 折叠 —— 相同 index 的帧合并进同一个 step |
| `seq` | 这是第几帧 | 是，轮内递增 | 去重 + 恢复锚点 |

19 个 narration token 带着同一个 `index: 0`，`seq` 却是 2、3、4…20。
前者让它们折叠成一个 step，后者让它们各自可寻址。

这正是 v2 里 `Extra.Index`（协议定义为「段在本轮里的次序」）与 `Seq` 的关系，
累积器的 `segKey = ${Type}:${Index}` 就是拿它建段的。**也正因为 `index` 在
「原子帧」和「段成品」两种投影下取值相同**，快照与实时帧才能混着喂进同一个
累积器还产出一致结果。

两个例外：

- **`final_delta` 没有 `index`**（`match_stream.py:227` 只发 `{"content": text}`）。
  一轮只有一个最终回复，它是单例而非段序列，直接追加到 `final_answer`。
- **`tool_args` 没有 `index`**，按 `name` 走，且在累积器里折叠成空
  （前端 `case "tool_args": break`）。它仍然占用一个 `seq`。

---

## 3. 从 v2 借什么、改什么

v2 的三条不变量全部采纳：

1. **fold 是纯函数** —— 同一批事件折叠多少次结果都一样，所以重放安全。
2. **本地状态是纯派生的** —— store 里存的是 `fold(events)` 的产物，随时可丢弃重算。
3. **锚点与内容必须同源** —— 「累积器装到哪」和「流从哪续」必须来自同一个快照。

但落地形态需要改。v2 有相当一部分复杂度来自它的两个结构性约束，而这两个约束在
本项目不存在：

| v2 的做法 | 本方案 | 理由 |
|---|---|---|
| 事件流是唯一真相 | **采纳** | 真相载体是逐帧落库的聚合态，不是逐事件表 |
| 本地状态纯派生、整体替换 | **采纳** | 现有的 `+=` 必须换成纯 fold |
| 锚点与内容同源 | **采纳，且由结构保证** | 见 §3.2 |
| `/Chat` + `/GetMessageStream` 双流语义 | **合并成单流** | 消掉「哪条流能重放」这一整类问题 |
| `GetMessageList` + `GetMessageStream` 两次请求配对 | **合成一次** | 消掉 `resolveV2ResumePlan` 存在的全部理由 |
| 逐帧 seq 重放 | **快照优先** | 见 §6.2 |
| session 全局 seq + `FirstSeq`/`LastSeq` | **轮内 seq，只要一个数** | 见 §3.3 |

### 3.1 单一流式端点

v2 走查中有很大篇幅在讲「`/Chat` 断了为什么不能重连、怎么交棒给
`/GetMessageStream`」。根因是**提交和流式是同一条流**：body 里带着问题文本，
重发一次等于再问一遍，后端还会用 `SESSION_BUSY` 顶回来。

本方案把两者拆开：

```
POST /api/match/conversations/{sid}/messages   → 201 {message_id}   非流式，立即返回
GET  /api/match/conversations/{sid}/stream     → SSE                纯订阅，永远可重放
```

于是不存在「不可重放的流」这个类别。v2 中的 `v2StreamDisconnected` 交棒事件、
`terminalSeen` 判断、`isHistorySyncing` 特判全部不需要。

代价：多一次往返（本地 ~5ms）。

### 3.2 锚点与内容同源 —— 用结构保证而非用约定

v2 必须靠 `resolveV2ResumePlan` 把 `fromSeq` 和 `hydrateEvents` **成对返回**，
因为内容来自 `GetMessageList` 的 `Events`、锚点来自同一个 pack 的 `LastSeq`，
两者混用就会出错（走查里那个「`FromSeq` 传 110 导致正文翻倍」的例子）。

本方案让 `/stream` 在建连时，**在同一把锁下**从 run 对象取出聚合态和 seq，
作为第一帧发出：

```
event: snapshot
data: {"message_id":"…","seq":417,"status":"running",
       "steps":[…],"final_answer":"…","job_ids":[…]}

event: final_delta   id: 418        ← 严格从 snapshot.seq 之后开始
event: final_delta   id: 419
…
event: message_end   id: 530
```

`seq` 与它所描述的内容物理上不可能来自不同时刻 —— **没有两个可以混用的值**。
客户端拿到 `snapshot` 就整体替换累积器，之后按 seq 去重折叠实时帧。

#### snapshot 是全量，不是增量

这是最容易看拧的一点。`snapshot.seq = 517` **不是「从这里继续」，而是「这份
快照里装到了 517」** —— `final_answer` 和 `steps` 已经包含 513~517 产出的内容。

客户端从 `/messages` 拿到的可能是 seq=512 的版本，两次水合之间那 5 帧
**从来没有以「帧」的形式出现过**，它们的内容是被快照的聚合结果直接带回来的。
所以不存在需要补的缺口。

```
增量模型（不采用）
  客户端: 我到 512 了
  服务端: 好，给你 513, 514, …
  → 需要服务端保留逐帧重放缓冲区
  → 客户端的 512 与它的累积器内容必须严格同源，否则重复或漏帧

全量模型（本方案）
  客户端: （不提供任何锚点）
  服务端: 这是当前全量态 @517，之后的帧我推给你
  → 客户端丢掉自己那份 512，整体替换
  → 没有可以配错的两个值
```

若按增量模型、客户端已用快照 B(@517) 建好累积器却告诉服务端「我到 512」，
服务端重推 513~517 —— 这些帧 seq 都 > 512，过得了去重判断，于是被二次折叠进
一个**已经含有它们**的累积器，`seg.text += chunk`，正文翻倍。这就是 v2 走查里
那个 bug，也是 `resolveV2ResumePlan` 存在的全部理由。

**订阅接口因此不接受 `from_seq` 参数** —— 让客户端没有机会提供锚点。

### 3.3 为什么不需要 `FirstSeq` / `LastSeq`

v2 的 `seq` 是 **session 全局**的：一个 session 一张 `t_session_event` 表，
seq 跨所有轮次单调递增。所以一个 pack 必须用两个数才能圈出「我是这条全局流的
哪一段」，`FirstSeq` 还兼任分页 cursor。

本方案的 `seq` 是**单条 assistant 消息内**的，每轮从 0 重新开始：

```
v2:     pack{ FirstSeq: 101, LastSeq: 200 }   ← 101 是信息，必须存
本方案:  message{ seq: 512 }                   ← FirstSeq 恒为 0，存了没有信息量
```

v2 用 `FirstSeq - 1` 做降级（`LastSeq` 异常时重放整轮），我们的等价物是
`seq = 0`，同样是常量。

分页也不靠它 —— 消息列表按 `created_at` 分页，索引现成：

```sql
CREATE INDEX idx_match_msg_session ON match_messages(session_id, created_at);
```

v2 的第三个锚点 `detail.LastEventSeq`（会话级，「没有 running pack 时的兜底」）
同样不需要：没有 `running` 的消息，就没有要恢复的东西。

**代价**：`seq` 只在轮内有意义，无法表达「这个 session 一共产出过多少事件」。
目前没有任何功能需要这个数。

---

## 4. 核心模型

```
RunRegistry（进程内，单例）
  session_id → Run
                ├─ task: asyncio.Task              agent 任务本体
                ├─ cancel: threading.Event         喂给 BaseAgent.run(cancel_check=…)
                ├─ message_id: str
                ├─ seq: int                        每发出一个事件 +1
                ├─ steps / final_answer / job_ids  聚合态，SSE 与快照共用同一份
                ├─ subscribers: set[asyncio.Queue] 支持多标签页
                └─ status: running|completed|stopped|failed
                          │
                          │ 逐帧落库（§4.1）
                          ▼
                match_messages 行（status + seq + steps + final_answer）
```

### 4.1 发帧顺序：折叠 → 落库 → 推送

```python
async def _emit(self, event: str, data: dict) -> None:
    async with run.lock:
        run.seq += 1
        run.apply(event, data)                     # ① 内存折叠
        await persist(run)                         # ② 落库
        for q in run.subscribers:                  # ③ 才推给前端
            q.put_nowait({"seq": run.seq, "event": event, "data": data})
```

这个顺序不只是「能接受」，它在正确性上是**唯一安全的方向**：

```
persist → emit   ⟹  DB.seq ≥ 任何客户端见过的 seq       ← 安全
emit → persist   ⟹  客户端可能见过 DB 里还没有的帧      ← 恢复会倒退
```

前者保证客户端永远不会比数据库更超前，恢复时读 DB 一定不丢内容。
性能开销实测 208ms / 轮（WAL 84ms），见 §6.3。

`run.lock` 同时承担 §3.2 的职责：订阅时取快照与挂队列在同一临界区完成，
所以快照 seq 与队列第一帧 seq 必然相邻。

**落库拆两条 SQL。** 535 帧里绝大多数是 `final_delta`，它不改 `steps`：

```python
if event in ("tool_start", "tool_end", "narration"):
    UPDATE match_messages SET seq=?, steps=?, final_answer=? WHERE id=?   # 少数帧，含 37KB blob
else:
    UPDATE match_messages SET seq=?, final_answer=? WHERE id=?            # final_delta，~3KB
```

37KB 的 `steps` blob 就从 535 次写入里退出去了。

---

## 5. 后端设计

### 5.1 Schema

```sql
ALTER TABLE match_messages ADD COLUMN status TEXT NOT NULL DEFAULT 'completed';
ALTER TABLE match_messages ADD COLUMN seq    INTEGER NOT NULL DEFAULT 0;
```

`status` 取值：`running` / `completed` / `stopped` / `failed` / `interrupted`。

既有行默认 `completed`，语义正确，无需数据回填。`app/database.py` 的
`_CREATE_TABLES_SQL` 同步更新，另配 `backend/scripts/migrate_message_status.py`
（幂等、先备份，与现有三个迁移脚本同风格）。

`app/models/match_conversation.py` 新增：

```python
async def update_message_progress(
    db, message_id, *, seq, steps, final_answer, job_ids=None, status=None
) -> None:
    """更新一条运行中的 assistant 消息。add_message 只有 INSERT，快照需要 UPDATE。"""
```

### 5.2 端点

| 方法 | 路径 | 语义 |
|---|---|---|
| `POST` | `/match/conversations/{sid}/messages` | 提交。落 user 行 + assistant 行（`status=running`），启动 run，**立即返回** `{message_id}`。已有活跃 run → 409 `SESSION_BUSY` |
| `GET` | `/match/conversations/{sid}/stream` | 订阅。先发 `snapshot`，再发实时帧。无活跃 run 时发一个终态 snapshot 后即关闭 |
| `POST` | `/match/conversations/{sid}/stop` | 停止。置 cancel → 等待收敛 → 修 checkpoint → 落 `status=stopped` |
| `GET` | `/match/conversations/{sid}/messages` | 契约不变。内容直接读 DB（逐帧落库，不会落后）；只需查 registry 判断 `running` 还是 `interrupted` |

`SESSION_BUSY` 按仓库惯例新增 `AppError` 子类（`app/exceptions.py`），
携带稳定的机器码 + 中文消息 + HTTP 409。

### 5.3 停止：用 `cancel_check`，不用 `Task.cancel()`

`BaseAgent.run` 已有的 `cancel_check` 在**图节点边界**检查
（`base.py:226` / `base.py:263`），而 `Task.cancel()` 可能在 LLM 请求中途或
checkpointer 写入中途炸开。协作式取消明显更安全。

```python
async def stop(self, db, session_id: str) -> None:
    run = registry.get(session_id)
    if run is None:
        return                                # 幂等：已结束就什么都不做
    run.cancel.set()                          # 下一个节点边界抛 AgentCancelled
    await run.wait(timeout=10)                # 等 task 收敛
    await self._repair_checkpoint(session_id)
    await update_message_progress(..., status="stopped")
```

### 5.4 停止后必须修复 checkpoint

**这是最容易漏的一点。**

`cancel_check` 在 `_tool_call` **顶部**触发时，checkpoint 里已经写入了带
`tool_calls` 的 `AIMessage`，而对应的 `ToolMessage` 永远不会产生。该 thread 的
下一轮请求会直接失败 —— `CLAUDE.md` 里记录的「a `tool_call` without a matching
`ToolMessage` makes the next request fail」正是这个约束。

所以停止流程必须补写合成 ToolMessage：

```python
async def _repair_checkpoint(self, session_id: str) -> None:
    """给被取消的 tool_calls 补占位 ToolMessage，否则该线程下一轮必挂。"""
    graph = await matcher_agent._get_graph()
    config = {"configurable": {"thread_id": session_id}}
    state = await graph.aget_state(config)

    messages = state.values.get("messages") or []
    if not messages:
        return
    last = messages[-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return

    await graph.aupdate_state(config, {"messages": [
        ToolMessage(content='{"error":"用户已停止本轮"}',
                    name=tc["name"], tool_call_id=tc["id"])
        for tc in last.tool_calls
    ]})
```

### 5.5 心跳与看门狗

v2 走查在末尾自陈了一个未修的隐患：静默挂死（NAT 映射过期、对端进程被 kill
但没发 FIN）不会触发 `onClose`，`reader.read()` 一直挂着，页面转圈到天荒地老。
v2 的 SSE 没有客户端读超时看门狗。

本方案顺手关掉这个缺口：

- 服务端每 **15s** 发一个 `: ping` 注释帧
- 客户端 **30s** 没收到任何字节 → 主动 abort 并重新订阅

成本很低，省掉一类最难排查的挂死。

---

## 6. 三个取舍（需确认）

### 6.1 提交与流式拆成两个请求

多一次往返，换掉整套「交棒」机制。

替代方案是让 `POST /messages` 继续直接返回流（保持现状），刷新后走 `/stream`。
但那就回到 v2 的双流语义，`SESSION_BUSY`、交棒事件、`terminalSeen` 这些都得实现。

**倾向：拆开。**

### 6.2 快照优先，而非逐帧重放

一轮实测有 **535 个 `final_delta`**。恢复时重放 535 帧没有意义 —— 客户端要的是
聚合结果，不是把 token 再吐一遍。

所以 `/stream` 首帧发聚合快照（对应 v2 的「段成品」投影），之后才是原子帧。
代价是重连时多传一份全文（~3KB），换掉整个逐帧重放缓冲区。

**倾向：快照优先。**

### 6.3 逐帧落库 —— 采纳「先落库再发 SSE」

> **本节结论已修正。** 早期设计主张「内存是运行中的真相，DB 按 ~1s 节流快照」，
> 理由是「535 次 UPDATE 会明显拖慢流」。该理由未经测量，实测后不成立，已推翻。

按一轮真实对话的量级实测（4 个 tool step，`observation` 各 3000 字 →
`steps` blob **37,012 bytes**；`final_answer` 逐帧增长；每帧 `UPDATE` + `commit`）：

```
steps blob = 37,012 bytes
默认 journal (delete)   535 次 UPDATE+commit:  208 ms  (0.39 ms/帧)
WAL                    535 次 UPDATE+commit:   84 ms  (0.16 ms/帧)
```

208ms 摊在 34 秒的一轮里不构成瓶颈：事件平均间隔约 50ms，落库占其中 0.4ms，
不到 1%。再叠加 §4.1 的两条 SQL 拆分（37KB blob 退出 `final_delta` 路径），
实际开销还要更低。

**所以采纳原始设想：折叠 → 落库 → 推送（§4.1）。** 带来的好处不只是省掉一层
概念：

- 顺序保证 `DB.seq ≥ 任何客户端见过的 seq`，恢复读 DB 一定不丢内容
- `list_messages` 不再需要「从内存 run 合并出更新内容」这个特例，
  只需查 registry 区分 `running` / `interrupted`
- 变体二（后端重启）能恢复到**断点的精确位置**，而不是最后一次快照

**倾向：逐帧落库。**

#### 附：要不要开 WAL

当前库是默认的 `journal_mode = delete`（实测确认），`app/database.py` 只设了
`PRAGMA foreign_keys = ON`。开 WAL 能把落库开销从 208ms 降到 84ms。

但这是**全局改动**，且 WAL 会产生 `-wal` / `-shm` 两个 sidecar 文件，而
`backend/data/job_matcher.db` 是 git 跟踪的 —— 需要同时加 `.gitignore` 规则。
208ms 本来就够用，**建议本方案先不动 journal 模式**，留作后续独立决定。

---

## 7. 前端设计

### 7.1 `MatchTurnAccumulator` —— 纯 fold

现有的增量 setState 换成累积器类，内部用 `Map` 维护段状态，对外**整体赋值**：

```ts
class MatchTurnAccumulator {
  static fromSnapshot(s: Snapshot): MatchTurnAccumulator   // 整体替换，不合并
  push(event: SSEEvent, seq: number): void                 // seq <= this.seq 直接丢弃
  toState(): { steps: TraceStep[]; finalAnswer: string; seq: number }
}
```

`useMatchChat` 每帧之后 `setState(acc.toState())` —— **整体赋值，不是 `+=`**。

这是 v2 那句「三层都是丢弃→重建，全程没有一处需要判断『这段内容我是不是已经
有了』」在本项目的落点。

### 7.2 恢复流程

```
进入 /match?session_id=X
  ↓
GET /messages
  ↓
最后一条 assistant.status === "running"？
  ├─ 否 → 正常渲染历史，结束
  └─ 是 → acc = MatchTurnAccumulator.fromSnapshot(那条消息)
          GET /stream                ← 服务端首帧 snapshot 会再覆盖一次，幂等
          折叠实时帧直到 message_end
```

**订阅必须归属于具体会话，不能是 hook 级的布尔量。**

v2 的守卫是三个布尔：

```ts
if (document.visibilityState !== "visible") return
if (streamAliveRef.current) return          // ← 与会话无关
if (isStreamingRef.current) return
```

那是因为 `ChatBIV2Chat` 一次只服务一个会话。**我们的侧边栏可以在不卸载组件的
情况下切换会话**，照抄会同时引发两个故障：切走时旧会话的流不会断，切回时
`streamAliveRef` 仍为 true 又会挡住新订阅 —— 结果是整段生成期间界面不更新，
直到旧流自然结束触发一次 `/messages`，正文才**一次性整块出现**。

所以守卫要带上会话身份：

```ts
interface Watch { sessionId: string; controller: AbortController }
const watchRef = useRef<Watch | null>(null)

// watch(id)：只有正在看同一个会话才短路，否则先掐断旧的
if (watchRef.current?.sessionId === sessionId) return
stopWatching()

// load(id)：切换会话时必须断开上一条订阅
if (watchRef.current && watchRef.current.sessionId !== sessionId) stopWatching()

// flush(id)：迟到的帧不能画到用户已经切走的会话上
if (sessionRef.current !== sessionId) return
```

`load` 还要区分「已经在看这个会话」—— 那种情况下不要用 DB 行重新水合累积器，
订阅本身已经比它更靠前。

挂在 `visibilitychange` 上；退避重连 `[500, 1000, 2000, 4000]ms`，
耗尽后拉一次 `/messages` 收口。

### 7.2.1 纯文本回复必须实时提升为正文

模型被要求用 `final_answer` 收尾，但它有时直接把答案写成普通文本。服务端在
`_close_out` 里兜底（末尾 narration 即答案），**客户端必须用同一条规则实时投影**，
否则这类答案会一路累积在静音的「思考过程」里，直到本轮结束才突然变成正文 ——
症状与上面那个会话切换 bug 完全一样，且不切会话也会发生。

`MatchTurnAccumulator.toState()`：

```ts
const last = steps[steps.length - 1]
if (!finalAnswer && last?.type === "narration") {
  finalAnswer = last.content ?? ""
  steps = steps.slice(0, -1)
}
```

注意是**末尾那一条** narration，不是全部。早先那些「好的，我先看看」属于 trace；
把它们一起拼进正文会让回复以工具间的闲聊开头。

### 7.3 停止

```ts
const stop = async () => {
  abortRef.current = true          // 停止本地读取
  await stopTurn(sessionId)        // POST /stop
  await loadHistory(sessionId)     // 拉回 status=stopped 的最终态
}
```

### 7.4 `lib/sse.ts` 扩展

- 支持 GET 订阅（现在只有 POST）
- 解析 `id:` 行取出 seq（现在只解析 `event:` / `data:`）
- 心跳超时主动 abort

---

## 8. 边界情况

| 场景 | 行为 |
|---|---|
| 刷新，run 还活着 | `/messages` 看到 `running` → 订阅 → 首帧 snapshot 补齐 → 接着流 |
| 刷新，run 已结束 | `status=completed`，直接渲染，不订阅 |
| 后端重启，行还是 `running` | registry 无此 run → 服务端改写为 `interrupted`，前端显示「已中断」并停止转圈。因为逐帧落库，内容恢复到**断点的精确位置** |
| 两个标签页 | 两个 subscriber queue，各自收到自己的 snapshot，互不影响 |
| 正在流式时又发一条 | `POST /messages` 返回 409 `SESSION_BUSY`，前端禁用发送按钮 |
| 停止后立刻再问 | checkpoint 已修复（§5.4），正常 |
| 停止时 run 已自然结束 | `stop` 幂等，直接返回当前终态 |
| 网络静默挂死 | 客户端 30s 看门狗 abort → 重新订阅（§5.5） |

---

## 9. 明确不做的

- **不建 `match_events` 事件表。** 逐事件落库对应 535 行/轮，SQLite 扛不住也没
  必要 —— 「段成品」聚合态已足够重建 UI。
- **不做跨 turn 的全局 seq。** seq 只在单条 assistant 消息内单调，恢复锚点只需
  定位「这一轮流到哪」。
- **不动 `/compare` 的 `useSSE`。** 按 `CLAUDE.md` 既有决定保持不变。
  （注：`/compare` 页面此前已删除，`useSSE` 是否还有消费者，实现时顺带确认。）

---

## 10. 改动清单

| 文件 | 动作 |
|---|---|
| `backend/app/services/match_runs.py` | **新增** `Run` / `RunRegistry` |
| `backend/app/services/match_service.py` | 重写：提交 / 订阅 / 停止三条路径 |
| `backend/app/routers/match.py` | 新增 `GET /stream`、`POST /stop`，改 `POST /messages` |
| `backend/app/models/match_conversation.py` | `add_message` 加 status/seq；新增 `update_message_progress` |
| `backend/app/database.py` | DDL 加两列 |
| `backend/app/exceptions.py` | 新增 `SessionBusyError` |
| `backend/scripts/migrate_message_status.py` | **新增**，幂等 + 备份 |
| `backend/app/schemas/match.py` | `MatchMessageOut` 加 `status` / `seq` |
| `backend/app/agents/matcher.py` | 无改动（`cancel_check` 走 `BaseAgent`） |
| `frontend/src/lib/matchAccumulator.ts` | **新增** 纯 fold 累积器 |
| `frontend/src/lib/sse.ts` | GET 订阅 + `id:` seq 解析 + 心跳超时 |
| `frontend/src/lib/api/match.ts` | 新增 `stopTurn` / `streamUrl` |
| `frontend/src/hooks/useMatchChat.ts` | 改为累积器驱动 + 恢复 + 停止 |
| `frontend/src/components/match/MatchChat.tsx` | 挂 `visibilitychange` 恢复守卫 |
| `frontend/src/types/match.ts` | 加 `status` / `seq` / `Snapshot` |
| `frontend/src/lib/matchAccumulator.test.ts` | **新增** 幂等性与投影等价性用例 |
| `CLAUDE.md` | 更新 SSE 契约与恢复机制 |

---

## 11. 测试计划

**累积器（vitest）**

- 幂等性：同一批事件 fold 两次，结果相同。
- 重叠安全：`fromSnapshot` 之后再喂重叠帧，内容不翻倍
  （对应 v2 走查里那个「`FromSeq` 传 110 导致正文翻倍」的 bug）。
- 投影等价：把一轮真实事件分别以「一次快照」和「逐帧」喂进累积器，
  断言输出一致 —— 这是 v2 单测锁的那条性质。

**后端（pytest）**

- `extract` 与 `update_message_progress` 的快照读写往返。
- `RunRegistry` 的多订阅者分发与终态清理。

**端到端（手动 + curl）**

- 起一轮真实对话，中途断开 curl → 重新订阅 → 断言最终 `final_answer`
  与不中断时一致。
- 中途 `POST /stop` → 断言 `status=stopped`、task 在 10s 内收敛、
  **紧接着再发一轮不报 tool_call 错**（专门验证 §5.4）。
- 浏览器：流式中途刷新页面，确认接着流；点击停止，确认两端都停。

**回归基线**

`uv run pytest` 当前基线为 1 failed（`test_config.py::test_load_config`）
/ 14 errors（`test_api.py` conftest 陈旧），实现后不得变差。
`bunx tsc --noEmit`、`bun run lint`、`bun run build` 保持干净。

---

## 12. 附录 · 一次冷启动恢复的完整走查

以实测那轮 bilibili 对话为蓝本：688 个事件
（1 `message_start` + 46 `narration` + 98 `tool_args` + 4 `tool_start`
+ 4 `tool_end` + 535 `final_delta` + 1 `message_end`）。

```
T+0s    发送「帮我在 bilibili 里找两个前端实习岗位，简单说说为什么推荐」
T+18s   关掉标签页       ← 后端 seq=268，正文已流出约 430 字
T+25s   重新打开页面     ← 后端 seq=512，仍在跑
T+34s   本轮自然结束     seq=688
```

### T+0s · 提交

前端：

```ts
const { message_id } = await sendMessage(sessionId, { content, scope, resume_id })
// POST /messages → 201 {"message_id":"msg_a1"}   ← 不是流，拿到 id 就返回
subscribe(sessionId)                              // 紧接着 GET /stream
```

后端 `POST /messages` 按序做四件事然后立即返回：

```python
await conv_model.add_message(db, sid, role="user", ...)
message_id = str(uuid.uuid4())
await conv_model.add_message(db, sid, role="assistant", message_id=message_id,
                             status="running", seq=0)          # 行先落库
run = registry.create(sid, message_id)
run.task = asyncio.create_task(self._drive(sid, run, request)) # 任务归 registry 所有
return ApiResponse.ok({"message_id": message_id})
```

第三、四步是关键。今天 agent task 的生命周期挂在 response generator 上，
generator 一关任务就成孤儿、结果无人落库（§1.1）。现在 task 属于 registry，
HTTP 请求结束与它无关。

### T+18s · 关掉标签页

**前端**：页面销毁，累积器随之 GC。store 里从来只有 fold 结果、没有事件，
所以丢的是派生物，不用记录丢在哪。

**后端**：`/stream` 的 generator 抛 `GeneratorExit`：

```python
finally:
    run.subscribers.discard(queue)      # 只摘掉这一个订阅者
    # run.task 不受影响，registry 仍持有它
```

此刻内存 `seq=268`，**DB `seq` 同为 268**（逐帧落库，§4.1）。

一个时序细节：SSE generator 只有在**尝试写入**时才会发现对端没了。若 agent
恰好卡在一次 LLM 请求上、20 秒无事件产出，后端要等下一帧或下一个 15s 心跳
才察觉。这不影响正确性 —— run 不依赖订阅者存在。

### T+18s ~ T+25s · 没有人在听

后端继续跑完第 4 次 `get_job_detail`，正文流到约 1100 字，`seq` 涨到 512，
每一帧都落库。这些帧被推进一个空的 subscribers 集合，全部丢弃。

> **产品取舍**：用户关窗后 token 照烧（v2 同样如此）。好处是回来就能拿到完整
> 结果；代价是用户不再回来的话这一轮白花。改成「无订阅者超过 N 秒即取消」也
> 可以，但会让「关窗去开个会再回来」这个主要场景失效。**倾向保持照跑。**

### T+25s · 重新打开 —— 冷启动恢复

与 v2 走查里「切 tab 再切回」不同：那里前端进程还活着、只是流断了；这里整个
页面是新的，**内存里什么都没有**，恢复只有一条路 —— 全量问后端要。
`visibilitychange` 那套守卫在此场景用不上（刚 mount，本来就没有活流），
真正跑的是挂载流程。

**步骤 1 · 拉历史**

```
GET /api/match/conversations/{sid}/messages
```

```jsonc
[
  { "id": "msg_u1", "role": "user", "content": "帮我在 bilibili 里找两个前端实习岗位…" },
  { "id": "msg_a1", "role": "assistant", "status": "running", "seq": 512,
    "steps": [ /* 3 narration + 4 tool，全部完成 */ ],
    "final_answer": "## 推荐一：⭐ AI-Native 开发工程师…（约 1100 字）" }
]
```

注意 `seq` 是 512 不是 268。恢复锚点从来不是「我听到哪」，而是「服务端写到哪」。
前端那个 268 随页面一起没了，也不需要。

**步骤 2 · 判定 + 水合**

```ts
const last = messages.at(-1)
if (last?.role === "assistant" && last.status === "running") {
  accRef.current = MatchTurnAccumulator.fromSnapshot(last)   // seq=512，整体替换
  subscribe(sessionId)
}
```

用户屏幕上此刻已渲染出 4 张工具卡 + 1100 字正文并在转圈，**全部来自 HTTP
响应，一帧 SSE 都还没收到**。

**步骤 3 · 订阅**

```python
async def subscribe(self, session_id):
    run = registry.get(session_id)
    queue = asyncio.Queue()

    async with run.lock:                       # ★ 同一临界区取快照 + 挂订阅
        snapshot = run.snapshot()
        run.subscribers.add(queue)

    yield _sse("snapshot", snapshot)
    while True:
        frame = await queue.get()
        if frame is None: break
        yield _sse(frame["event"], frame["data"], seq=frame["seq"])
```

`run.lock` 保证 `snapshot.seq = 517` 之后队列的第一帧必然是 518 —— 没有缝隙，
也没有重叠。

**步骤 4 · 第二次水合（必须幂等）**

累积器里已有步骤 2 装进去的 512 版本，现在来了 517 版本：

```ts
case "snapshot":
  accRef.current = MatchTurnAccumulator.fromSnapshot(event.data)  // 整体替换
  setState(accRef.current.toState())
```

丢掉旧的，重叠的 1~512 一次比对都不做。513~517 那 5 帧前端**从未以「帧」的
形式见过**，它们的内容由快照直接带回（§3.2）。

两次水合各有分工：`/messages` 那次是为了**立刻出画面**（且它本来就要调，
要渲染前几轮对话），`/stream` 首帧那次是为了**精确对齐锚点**。

### T+34s · 收工

```python
run.status = "completed"
job_ids = await self._resolve_citations(db, run.final_answer, turn_ctx)
await update_message_progress(db, message_id, ..., job_ids=job_ids, status="completed")
for q in run.subscribers:
    q.put_nowait({"seq": run.seq, "event": "message_end", "data": {...}})
    q.put_nowait(None)
registry.discard(session_id)
```

前端收到 `message_end` → 停止转圈 → `loadHistory` 拉回终态（顺带拿到 `job_ids`）。

### 变体 · 回来时已经跑完（最常见）

`status !== "running"` → **不订阅**，直接渲染完整历史。恢复流程一步都不走。
这也是判定必须放在 `/messages` 之后的原因：先问「还需不需要接着听」。

### 变体 · 期间后端重启过

registry 进程内，重启即清空。DB 里 `status` 仍是 `running` 但
`registry.get(sid)` 返回 `None` → 改写为 `interrupted`，内容为断点精确位置
（逐帧落库）。前端渲染已有内容 + 「本轮已中断」+ 重试，**不订阅、不转圈**。
