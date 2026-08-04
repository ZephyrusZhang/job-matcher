"""Reusable LangGraph agent base class.

Generalized from the template's single ``LangGraphAgent`` so that defining a new
agent means declaring what makes it different — its name, tools, system prompt
and state — rather than rebuilding the graph, checkpointing, tracing, retry and
memory plumbing each time.

Minimal agent::

    class MyAgent(BaseAgent):
        name = "my_agent"
        tools = [some_tool]

        def build_system_prompt(self, **kwargs) -> str:
            return "You are a helpful assistant."

    agent = MyAgent()
    reply = await agent.get_response([Message(role="user", content="hi")], session_id="abc")

Every agent gets, for free:

* stateful conversations — Postgres checkpointing keyed on ``session_id``
* long-term memory — mem0 lookup before the call, write-back after
* tool calling — parallel execution with retry
* observability — Langfuse tracing plus Prometheus metrics
"""

import asyncio
import time
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Optional,
    Sequence,
    Type,
    cast,
)

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    ToolMessage,
    convert_to_openai_messages,
)
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tools.base import BaseTool
from langgraph.errors import GraphInterrupt
from langgraph.graph import (
    END,
    StateGraph,
)
from langgraph.graph.state import (
    Command,
    CompiledStateGraph,
)
from langgraph.types import (
    RetryPolicy,
    StateSnapshot,
)
from pydantic import BaseModel

from app.core.config import settings
from app.core.langgraph.checkpointer import (
    clear_thread,
    get_checkpointer,
)
from app.core.logging import logger
from app.core.metrics import (
    agent_runs_total,
    agent_tool_calls_total,
    agent_tool_duration_seconds,
    agent_turns_total,
    llm_inference_duration_seconds,
)
from app.core.observability import langfuse_callback_handler
from app.schemas.agent import (
    GraphState,
    Message,
)
from app.services.llm import LLMService
from app.services.memory import memory_service
from app.utils.graph import (
    dump_messages,
    extract_text_content,
    prepare_messages,
    process_llm_response,
)


class AgentCancelled(Exception):
    """Raised inside a graph node when a run is cancelled cooperatively."""


class BaseAgent:
    """Base class for every agent in this project.

    Subclasses override the class attributes and ``build_system_prompt``.

    Attributes:
        name: Identifier used in logs, metrics and Langfuse traces.
        tools: Tools bound to the model and executed by the tool node.
        state_schema: Pydantic state model; defaults to ``GraphState``.
        max_turns: Maximum LLM turns before the graph aborts.
        use_memory: Whether to consult and update long-term memory.
        max_history_tokens: Token budget for trimmed history; ``None`` uses
            ``settings.MAX_TOKENS``.
    """

    name: str = "agent"
    tools: Sequence[BaseTool] = ()
    state_schema: Type[BaseModel] = GraphState
    max_turns: int = 32
    use_memory: bool = True
    max_history_tokens: Optional[int] = None
    # Tools that end the turn. Calling one routes to END instead of back to
    # chat, which lets an agent declare an explicit exit point (see the
    # ``final_answer`` pattern) rather than ending on "no tool calls".
    terminal_tools: frozenset[str] = frozenset()
    # Stream tokens from the model. Required for callback-driven UIs; agents
    # that only consume the final result leave it off.
    streaming: bool = False

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        tools: Optional[Sequence[BaseTool]] = None,
        max_turns: Optional[int] = None,
        model: Optional[str] = None,
    ):
        """Build the agent and bind its tools to a dedicated LLM service.

        Each agent owns its own ``LLMService`` so that one agent's model
        fallback never mutates another agent's tool bindings.

        Args:
            name: Overrides the class-level name.
            tools: Overrides the class-level tools.
            max_turns: Overrides the class-level turn limit.
            model: Overrides the default model for this agent.
        """
        if name is not None:
            self.name = name
        if tools is not None:
            self.tools = tools
        if max_turns is not None:
            self.max_turns = max_turns

        self.llm_service = LLMService()
        if model:
            self.llm_service.set_model(model)
        if self.tools:
            self.llm_service.bind_tools(list(self.tools))
        if self.streaming:
            self.llm_service.enable_streaming()

        self.tools_by_name: dict[str, BaseTool] = {tool.name: tool for tool in self.tools}
        self._graph: Optional[CompiledStateGraph] = None

        logger.info(
            "agent_initialized",
            agent=self.name,
            tool_count=len(self.tools),
            max_turns=self.max_turns,
            model=model or settings.DEFAULT_LLM_MODEL,
        )

    # ── Override points ───────────────────────────────────────────────────

    def build_system_prompt(self, **kwargs: Any) -> str:
        """Return the system prompt for this agent.

        Args:
            **kwargs: Context supplied by the caller — ``username`` and
                ``long_term_memory`` are always present.

        Returns:
            The system prompt.

        Raises:
            NotImplementedError: When a subclass does not override this.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement build_system_prompt()")

    def initial_state(self, messages: list[Message], long_term_memory: str) -> dict:
        """Build the graph input for a fresh run.

        Subclasses with extra state fields extend the returned dict.

        Args:
            messages: The conversation to seed the run with.
            long_term_memory: Memories retrieved for this user.

        Returns:
            The graph input mapping.
        """
        return {"messages": dump_messages(messages), "long_term_memory": long_term_memory}

    def compact_history(self, messages: list, system_prompt: str) -> list:
        """Fit the conversation into the model's context before each LLM call.

        The default drops the oldest messages once the token budget is exceeded.
        Agents whose histories must stay structurally intact — for example
        because dropping a message would orphan a tool result — override this.

        Args:
            messages: The current conversation state.
            system_prompt: The system prompt to prepend.

        Returns:
            The messages to send, system prompt first.
        """
        return prepare_messages(messages, system_prompt, self.max_history_tokens)

    # ── Graph construction ────────────────────────────────────────────────

    async def _chat(self, state: Any, config: RunnableConfig) -> Command:
        """Call the LLM and route to tools or to the end of the graph."""
        metadata = config.get("metadata") or {}
        configurable = config.get("configurable") or {}
        thread_id = configurable.get("thread_id")

        cancel_check = configurable.get("cancel_check")
        if callable(cancel_check) and cancel_check():
            raise AgentCancelled(f"{self.name} run cancelled")

        turn = len([m for m in state.messages if isinstance(m, AIMessage)]) + 1
        if turn > self.max_turns:
            logger.warning("agent_max_turns_reached", agent=self.name, session_id=thread_id, max_turns=self.max_turns)
            return Command(update={}, goto=END)

        system_prompt = self.build_system_prompt(
            username=metadata.get("username"),
            long_term_memory=getattr(state, "long_term_memory", ""),
            state=state,
        )
        messages = self.compact_history(state.messages, system_prompt)

        model_name = settings.DEFAULT_LLM_MODEL
        current_llm = self.llm_service.get_llm()
        if current_llm is not None and hasattr(current_llm, "model_name"):
            model_name = current_llm.model_name

        try:
            with llm_inference_duration_seconds.labels(model=model_name).time():
                response_message = await self.llm_service.call(dump_messages(messages))

            response_message = process_llm_response(response_message)
            logger.info("llm_response_generated", agent=self.name, session_id=thread_id, model=model_name, turn=turn)

            goto = "tool_call" if isinstance(response_message, AIMessage) and response_message.tool_calls else END
            return Command(update={"messages": [response_message]}, goto=goto)
        except Exception as e:
            logger.error("llm_call_failed_all_models", agent=self.name, session_id=thread_id, error=str(e))
            raise

    async def _tool_call(self, state: Any, config: RunnableConfig) -> Command:
        """Execute every tool call from the last message, then return to chat."""
        configurable = config.get("configurable") or {}
        cancel_check = configurable.get("cancel_check")
        if callable(cancel_check) and cancel_check():
            raise AgentCancelled(f"{self.name} run cancelled")

        tool_calls = state.messages[-1].tool_calls

        async def _execute_tool(tool_call: dict) -> ToolMessage:
            tool_name = tool_call["name"]
            tool = self.tools_by_name.get(tool_name)
            started = time.time()

            if tool is None:
                agent_tool_calls_total.labels(agent=self.name, tool=tool_name, status="error").inc()
                return ToolMessage(
                    content=f'{{"error": "unknown tool: {tool_name}"}}',
                    name=tool_name,
                    tool_call_id=tool_call["id"],
                )

            try:
                result = await tool.ainvoke(tool_call["args"])
                status = "success"
            except Exception as e:
                logger.exception("agent_tool_failed", agent=self.name, tool=tool_name, error=str(e))
                result = f'{{"error": {str(e)!r}}}'
                status = "error"

            agent_tool_calls_total.labels(agent=self.name, tool=tool_name, status=status).inc()
            agent_tool_duration_seconds.labels(agent=self.name, tool=tool_name).observe(time.time() - started)

            return ToolMessage(content=result, name=tool_name, tool_call_id=tool_call["id"])

        terminal = [tc for tc in tool_calls if tc["name"] in self.terminal_tools]
        others = [tc for tc in tool_calls if tc["name"] not in self.terminal_tools]

        # A terminal tool only ends the turn when the model committed to it
        # alone. Mixed with real work it means the model called it prematurely,
        # so run the work and let it decide again with those results in hand.
        deferred: list[ToolMessage] = []
        if terminal and others:
            logger.warning(
                "terminal_tool_deferred",
                agent=self.name,
                terminal=[tc["name"] for tc in terminal],
                alongside=[tc["name"] for tc in others],
            )
            to_run = others
            goto = "chat"
            # Every tool_call needs a matching ToolMessage or the provider
            # rejects the next request, so answer the deferred call too.
            deferred = [
                ToolMessage(
                    content="skipped: call this alone once the other tool results are in",
                    name=tc["name"],
                    tool_call_id=tc["id"],
                )
                for tc in terminal
            ]
        else:
            to_run = tool_calls
            goto = END if terminal else "chat"

        if len(to_run) == 1:
            outputs = [await _execute_tool(to_run[0])]
        else:
            outputs = list(await asyncio.gather(*[_execute_tool(tc) for tc in to_run]))

        return Command(update={"messages": outputs + deferred}, goto=goto)

    async def create_graph(self) -> Optional[CompiledStateGraph]:
        """Build and compile the agent graph, reusing it on later calls.

        Returns:
            The compiled graph, or ``None`` when initialization failed in
            production.

        Raises:
            Exception: Propagated outside production.
        """
        if self._graph is not None:
            return self._graph

        try:
            graph_builder = StateGraph(self.state_schema)
            graph_builder.add_node("chat", self._chat, destinations=("tool_call", END))
            graph_builder.add_node(
                "tool_call",
                self._tool_call,
                destinations=("chat",),
                retry_policy=RetryPolicy(max_attempts=3),
            )
            graph_builder.set_entry_point("chat")
            graph_builder.set_finish_point("chat")

            checkpointer = await get_checkpointer()
            self._graph = graph_builder.compile(
                checkpointer=checkpointer,
                name=f"{settings.PROJECT_NAME} {self.name} ({settings.ENVIRONMENT.value})",
            )
            logger.info("graph_created", agent=self.name, has_checkpointer=checkpointer is not None)
            return self._graph
        except Exception as e:
            logger.error("graph_creation_failed", agent=self.name, error=str(e))
            raise

    async def _get_graph(self) -> CompiledStateGraph:
        """Return the compiled graph, building it on first access.

        Raises:
            RuntimeError: When graph initialization failed.
        """
        graph = self._graph or await self.create_graph()
        if graph is None:
            raise RuntimeError(f"graph initialization failed for agent {self.name}")
        return graph

    # ── Invocation ────────────────────────────────────────────────────────

    def _build_config(
        self,
        session_id: str,
        user_id: Optional[str],
        username: Optional[str],
        callbacks: Optional[list[BaseCallbackHandler]],
        cancel_check: Optional[Callable[[], bool]],
    ) -> RunnableConfig:
        """Assemble the RunnableConfig shared by every invocation path."""
        handlers: list[BaseCallbackHandler] = list(callbacks or [])
        if langfuse_callback_handler is not None:
            handlers.append(langfuse_callback_handler)

        return {
            "configurable": {"thread_id": session_id, "cancel_check": cancel_check},
            "callbacks": handlers,
            # Each turn costs two super-steps (chat + tool_call), plus one to
            # let the final chat node finish.
            "recursion_limit": self.max_turns * 2 + 2,
            "metadata": {
                "agent": self.name,
                "user_id": user_id,
                "username": username,
                "session_id": session_id,
                "environment": settings.ENVIRONMENT.value,
            },
        }

    async def _resolve_input(self, graph, config: RunnableConfig, messages: list[Message], user_id: Optional[str]):
        """Return the graph input, resuming an interrupt when one is pending."""
        state, relevant_memory = await asyncio.gather(
            graph.aget_state(config),
            memory_service.search(user_id, messages[-1].content) if self.use_memory else _empty_string(),
        )

        if state.next:
            logger.info("resuming_interrupted_graph", agent=self.name, next_nodes=state.next)
            return Command(resume=messages[-1].content)

        return self.initial_state(messages, relevant_memory or "No relevant memory found.")

    async def run(
        self,
        messages: list[Message],
        session_id: str,
        *,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        callbacks: Optional[list[BaseCallbackHandler]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> dict:
        """Run the agent and return the final graph state.

        Use this for non-conversational agents that care about accumulated state
        rather than a chat reply. ``get_response`` wraps this for chat use.

        Args:
            messages: The conversation to run.
            session_id: LangGraph thread ID.
            user_id: Memory partition and trace attribution.
            username: Display name available to the system prompt.
            callbacks: Extra LangChain callback handlers for this run.
            cancel_check: Polled between nodes; returning ``True`` aborts.

        Returns:
            The final state mapping.

        Raises:
            AgentCancelled: When ``cancel_check`` requested cancellation.
        """
        graph = await self._get_graph()
        config = self._build_config(session_id, user_id, username, callbacks, cancel_check)
        started = time.time()

        try:
            graph_input = await self._resolve_input(graph, config, messages, user_id)
            response = await graph.ainvoke(graph_input, config=config)

            turns = len([m for m in response.get("messages", []) if isinstance(m, AIMessage)])
            agent_turns_total.labels(agent=self.name).observe(turns)
            agent_runs_total.labels(agent=self.name, status="success").inc()

            if self.use_memory and user_id:
                openai_msgs = cast(list[dict], convert_to_openai_messages(response["messages"]))
                asyncio.create_task(memory_service.add(user_id, openai_msgs, config.get("metadata")))

            logger.info(
                "agent_run_completed",
                agent=self.name,
                session_id=session_id,
                turns=turns,
                duration_s=round(time.time() - started, 2),
            )
            return response
        except AgentCancelled:
            agent_runs_total.labels(agent=self.name, status="cancelled").inc()
            logger.info("agent_run_cancelled", agent=self.name, session_id=session_id)
            raise
        except Exception as e:
            agent_runs_total.labels(agent=self.name, status="error").inc()
            logger.exception("agent_run_failed", agent=self.name, session_id=session_id, error=str(e))
            raise

    async def get_response(
        self,
        messages: list[Message],
        session_id: str,
        *,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        callbacks: Optional[list[BaseCallbackHandler]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> list[Message]:
        """Run the agent and return the conversation messages.

        Args:
            messages: The conversation to run.
            session_id: LangGraph thread ID.
            user_id: Memory partition and trace attribution.
            username: Display name available to the system prompt.
            callbacks: Extra LangChain callback handlers for this run.
            cancel_check: Polled between nodes; returning ``True`` aborts.

        Returns:
            The user and assistant messages after the run.
        """
        graph = await self._get_graph()
        config = self._build_config(session_id, user_id, username, callbacks, cancel_check)

        try:
            response = await self.run(
                messages,
                session_id,
                user_id=user_id,
                username=username,
                callbacks=callbacks,
                cancel_check=cancel_check,
            )
        except GraphInterrupt:
            state = await graph.aget_state(config)
            interrupt_value = state.tasks[0].interrupts[0].value if state.tasks else "Waiting for input."
            return [Message(role="assistant", content=str(interrupt_value))]

        state = await graph.aget_state(config)
        if state.next:
            interrupt_value = state.tasks[0].interrupts[0].value if state.tasks else "Waiting for input."
            logger.info("graph_interrupted", agent=self.name, session_id=session_id)
            return [Message(role="assistant", content=str(interrupt_value))]

        return self._process_messages(response["messages"])

    async def get_stream_response(
        self,
        messages: list[Message],
        session_id: str,
        *,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        callbacks: Optional[list[BaseCallbackHandler]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream the agent's reply token by token.

        Args:
            messages: The conversation to run.
            session_id: LangGraph thread ID.
            user_id: Memory partition and trace attribution.
            username: Display name available to the system prompt.
            callbacks: Extra LangChain callback handlers for this run.
            cancel_check: Polled between nodes; returning ``True`` aborts.

        Yields:
            Text chunks of the assistant reply.
        """
        graph = await self._get_graph()
        config = self._build_config(session_id, user_id, username, callbacks, cancel_check)

        try:
            graph_input = await self._resolve_input(graph, config, messages, user_id)

            async for token, _ in graph.astream(graph_input, config, stream_mode="messages"):
                if not isinstance(token, (AIMessage, AIMessageChunk)):
                    continue
                text = extract_text_content(token.content)
                if text:
                    yield text

            state = await graph.aget_state(config)
            if state.next:
                interrupt_value = state.tasks[0].interrupts[0].value if state.tasks else "Waiting for input."
                yield str(interrupt_value)
            elif self.use_memory and user_id and state.values and "messages" in state.values:
                openai_msgs = cast(list[dict], convert_to_openai_messages(state.values["messages"]))
                asyncio.create_task(memory_service.add(user_id, openai_msgs, config.get("metadata")))
        except GraphInterrupt:
            state = await graph.aget_state(config)
            interrupt_value = state.tasks[0].interrupts[0].value if state.tasks else "Waiting for input."
            yield str(interrupt_value)
        except Exception as e:
            logger.exception("stream_processing_failed", agent=self.name, session_id=session_id, error=str(e))
            raise

    async def get_state(self, session_id: str) -> StateSnapshot:
        """Return the raw checkpointed state for a session."""
        graph = await self._get_graph()
        return await graph.aget_state(config={"configurable": {"thread_id": session_id}})

    async def get_chat_history(self, session_id: str) -> list[Message]:
        """Return the user/assistant history for a session."""
        state = await self.get_state(session_id)
        return self._process_messages(state.values["messages"]) if state.values else []

    async def clear_chat_history(self, session_id: str) -> None:
        """Delete all checkpointed state for a session."""
        await clear_thread(session_id)

    def _process_messages(self, messages: list[BaseMessage]) -> list[Message]:
        """Keep only non-empty user and assistant messages."""
        openai_style_messages = convert_to_openai_messages(messages)
        return [
            Message(role=message["role"], content=str(message["content"]))
            for message in openai_style_messages
            if message["role"] in ("assistant", "user") and message["content"]
        ]


async def _empty_string() -> str:
    """Awaitable returning an empty string, for gathering when memory is off."""
    return ""
