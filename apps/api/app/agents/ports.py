from typing import Protocol

from app.agents.state import ResearchState


class RunStore(Protocol):
    """Everything the executor needs from persistence. The engine itself never sees this."""
    def claim(self, research_id: str) -> bool: ...          # atomic; False if another worker owns the run
    def load_state(self, research_id: str) -> ResearchState: ...
    def record(self, state: ResearchState, event: dict) -> None: ...  # event + task/run rows + audit, one transaction
    def poll_control(self, research_id: str) -> str | None: ...       # None | 'pause' | 'cancel' (also heartbeats)
    def finish(self, state: ResearchState, status: str, error: str | None = None) -> None: ...
