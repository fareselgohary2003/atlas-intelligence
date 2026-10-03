"""Enforces: Agents -> ToolRegistry -> tool implementations -> providers. Agent code may not reach around the registry."""
import ast
import pathlib
import unittest

AGENTS = pathlib.Path(__file__).resolve().parents[1] / "app" / "agents"
NETWORK = {"requests", "httpx", "aiohttp", "urllib.request", "http.client", "socket", "ssl", "openai", "anthropic"}
ALLOWED_TOOL_IMPORTS = {"app.tools.base", "app.tools.registry"}
EXEMPT = {"llm.py"}  # the LLM provider adapter is the boundary for LLM traffic, behind LLMProvider


def imports(path):
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module
            yield from (f"{node.module}.{a.name}" for a in node.names)


class ArchitectureTests(unittest.TestCase):
    def test_agent_code_depends_only_on_the_registry(self):
        for f in AGENTS.glob("*.py"):
            if f.name in EXEMPT:
                continue
            for m in imports(f):
                self.assertNotIn(m, NETWORK, f"{f.name} imports network library {m}")
                if m.startswith("app.tools."):
                    self.assertTrue(any(m == a or m.startswith(a + ".") for a in ALLOWED_TOOL_IMPORTS),
                                    f"{f.name} imports tool implementation {m}")

    def test_engine_and_state_know_nothing_about_tools_or_persistence(self):
        for name in ("graph.py", "state.py", "manager.py"):
            for m in imports(AGENTS / name):
                self.assertFalse(m.startswith(("app.tools", "app.repositories", "sqlalchemy", "app.models")), f"{name}: {m}")


if __name__ == "__main__":
    unittest.main()
