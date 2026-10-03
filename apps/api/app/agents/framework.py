"""Agent contract + AgentRegistry. Agents see only the ToolRegistry (via AgentContext); the engine owns the lifecycle."""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    name: str
    description: str
    capabilities: tuple
    allowed_tools: tuple


@dataclass
class AgentTask:
    id: str
    title: str
    agent: str
    research_id: str
    workspace_id: str
    goal: str
    attempt: int = 1


@dataclass
class AgentResult:
    status: str                      # completed | insufficient
    summary: str                     # concise activity summary, never reasoning
    created_sources: list = field(default_factory=list)    # ids created OR matched to an existing source
    created_evidence: list = field(default_factory=list)
    created_claims: list = field(default_factory=list)
    follow_up_tasks: list = field(default_factory=list)    # proposals for the Research Manager
    confidence: str | None = None    # mean evidence quality level; claims stay unverified
    metadata: dict = field(default_factory=dict)

    def to_dict(self, tool_calls: int = 0) -> dict:
        return {"status": self.status, "summary": self.summary, "confidence": self.confidence,
                "counts": {"tool_calls": tool_calls, "sources": len(self.created_sources),
                           "evidence": len(self.created_evidence), "claims": len(self.created_claims)},
                "created_sources": self.created_sources, "created_evidence": self.created_evidence,
                "created_claims": self.created_claims, "follow_up_tasks": self.follow_up_tasks, "metadata": self.metadata}


class AgentContext:
    def __init__(self, task: AgentTask, tools: ToolRegistry, tool_ctx: ToolContext, llm, follow_ups):
        self.task, self.tools, self.tool_ctx, self.llm, self.follow_ups, self.tool_calls = task, tools, tool_ctx, llm, follow_ups, 0

    def call(self, name: str, args: dict) -> dict:
        """Strict: failures raise (retryable ones as TransientError, so the engine retries the task)."""
        self.tool_calls += 1
        return self.tools.execute(name, args, self.tool_ctx).unwrap()

    def try_call(self, name: str, args: dict):
        """Tolerant: returns (data | None, ToolResult) so an agent can record a per-item failure and continue."""
        self.tool_calls += 1
        r = self.tools.execute(name, args, self.tool_ctx)
        return (r.data if r.ok else None), r

    def event(self, kind: str, **fields):
        """Lifecycle event (SOURCE_SAVED, CLAIM_CREATED, VERIFICATION_*...). Only whitelisted fields survive public_event()."""
        if self.tool_ctx.emit:
            try:
                self.tool_ctx.emit(kind, agent=self.tool_ctx.agent, task_id=self.task.id, **fields)
            except Exception:
                logging.getLogger("atlas.agents").exception("agent event emit failed")

    def progress(self, pct: int, note: str):
        self.try_call("update_task", {"progress": pct, "note": note})


class Agent(ABC):
    definition: AgentDefinition

    @abstractmethod
    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult: ...


class AgentRegistry:
    def __init__(self, tools: ToolRegistry):
        self.tools, self._agents = tools, {}

    def register(self, agent: Agent) -> None:
        d = agent.definition
        if not d.id or not d.capabilities:
            raise ValueError("Agent needs an id and at least one capability")
        if d.id in self._agents:
            raise ValueError(f"Agent '{d.id}' is already registered")
        missing = [t for t in d.allowed_tools if t not in self.tools.names()]
        if missing:
            raise ValueError(f"Agent '{d.id}' requests unregistered tools: {missing}")
        self.tools.grant(d.id, list(d.allowed_tools))
        self._agents[d.id] = agent

    def get(self, agent_id: str) -> Agent:
        if agent_id not in self._agents:
            raise ValueError(f"Unknown agent '{str(agent_id)[:30]}'")
        return self._agents[agent_id]

    def names(self) -> tuple:
        return tuple(sorted(self._agents))

    def runners(self, llm_factory, follow_ups, recorder=None, prices=None) -> dict:
        """Engine-facing runners: runner(state, task) -> result dict. The registry resolves the agent, not the graph."""
        def make(agent_id):
            def runner(state, task):
                from app.observability.logging import bind_context, clear_context
                clear_context()  # pool threads are reused: never inherit another task's ids
                bind_context(research_id=state.research_id, workspace_id=state.workspace_id, task_id=task.id, agent=agent_id, attempt=task.attempts)
                agent = self.get(agent_id)
                tctx = ToolContext(agent=agent_id, task_id=task.id, research_id=state.research_id,
                                   workspace_id=state.workspace_id, emit=state.emit)
                atask = AgentTask(task.id, task.title, agent_id, state.research_id, state.workspace_id, state.user_goal, task.attempts)
                llm = llm_factory()
                if recorder is not None:
                    from app.observability.usage import MeteredLLM
                    llm = MeteredLLM(llm, recorder, research_id=state.research_id, workspace_id=state.workspace_id, agent=agent_id, task_key=task.id, prices=prices)
                ctx = AgentContext(atask, self.tools, tctx, llm, follow_ups)  # ConfigError here fails the task visibly
                return agent.run(atask, ctx).to_dict(ctx.tool_calls)
            return runner
        return {a: make(a) for a in self._agents}
