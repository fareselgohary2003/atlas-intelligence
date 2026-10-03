#!/usr/bin/env bash
# Runs every test that needs no third-party packages. Integration tests (pytest + sqlalchemy + fastapi + httpx) are listed in docs/TESTING.md.
set -euo pipefail
cd "$(dirname "$0")/.."
(cd apps/api && python3 -m unittest tests.test_engine tests.test_persistence_contract tests.test_ssrf tests.test_fetch tests.test_extract_sources \
  tests.test_search tests.test_tool_registry tests.test_transport_local tests.test_architecture tests.test_verification_conflicts tests.test_evidence_service \
  tests.test_agents tests.test_factchecker tests.test_reporting tests.test_usage_llm tests.test_analyst_e2e tests.test_graph_catalog tests.test_security_core)
(cd apps/web && node --test tests/*.test.mjs)
