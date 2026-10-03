# Atlas Intelligence

### An Autonomous Enterprise Research & Intelligence Platform

**From complex questions to traceable intelligence.**

Atlas Intelligence is an agentic AI research platform designed to transform complex business questions into structured research workflows, evidence-backed findings, and cited executive reports.

Instead of treating research as a single conversation with a language model, Atlas coordinates specialized agents to plan research tasks, gather sources, extract evidence, evaluate claims, detect conflicting information, identify research gaps, and synthesize findings into an auditable report.

The platform is built around **traceability, evidence quality, explicit uncertainty, and controlled agent execution**.

> **Project Status:** The core research engine and selected application logic have automated test coverage. Database integrations, API runtime, background workers, Docker deployment, and live external-provider integrations remain unverified until the documented runtime checks have been executed. See [`docs/UNVERIFIED.md`](docs/UNVERIFIED.md) for details.

---

## Table of Contents

* [Overview](#overview)
* [Key Features](#key-features)
* [Example Use Case](#example-use-case)
* [How It Works](#how-it-works)
* [Agent Architecture](#agent-architecture)
* [Evidence and Claim Integrity](#evidence-and-claim-integrity)
* [Verification and Conflict Detection](#verification-and-conflict-detection)
* [Research Gaps and Replanning](#research-gaps-and-replanning)
* [Report Generation](#report-generation)
* [Technology Stack](#technology-stack)
* [Getting Started](#getting-started)
* [Demo Mode](#demo-mode)
* [Configuration](#configuration)
* [Testing](#testing)
* [Security](#security)
* [Known Limitations](#known-limitations)
* [Unverified Components](#unverified-components)
* [Roadmap](#roadmap)
* [Author](#author)
* [License](#license)

---

## Overview

Enterprise research often requires more than finding information. Teams must gather sources, compare claims, evaluate evidence quality, investigate conflicting figures, identify uncertainty, and produce reports that others can audit.

Atlas Intelligence is designed to coordinate that process through an agentic research workflow.

A user submits a complex business question. The Research Manager creates a plan, specialized agents investigate different dimensions, and the research engine coordinates tools and task dependencies. Sources, evidence, claims, and verification results are stored as separate records so findings can be traced back to their supporting material.

The resulting report distinguishes sourced findings from analytical inferences and unresolved questions.

### Design Principles

* **Evidence before conclusions:** Factual findings should be linked to stored evidence and source records.
* **Traceability:** Research outputs should be auditable from the final report back to the underlying evidence.
* **Explicit uncertainty:** Unsupported claims, conflicting information, and research gaps should remain visible.
* **Controlled autonomy:** Agents operate through registered capabilities and explicit tool permissions.
* **Bounded execution:** Retries, cancellation, and replanning follow defined execution rules.
* **Honest reporting:** Demo data and unverified integrations must not be presented as confirmed production results.

Atlas is designed as a research workflow platform, not simply a conversational interface.

---

## Key Features

### Multi-Agent Research Orchestration

* Decompose complex research objectives into specialized tasks.
* Represent task dependencies and execution state.
* Execute independent tasks concurrently where supported.
* Track task progress, failures, and execution events.
* Support pause, resume, and cancellation workflows in the implemented orchestration architecture.
* Bound retries and replanning to avoid uncontrolled execution.

### Specialized Research Agents

The platform defines nine agent roles:

1. Research Manager
2. Market Research Agent
3. Customer and Demand Agent
4. Competitor Intelligence Agent
5. Pricing Research Agent
6. Regulation Research Agent
7. Risk Analysis Agent
8. Fact Checker
9. Analyst Agent

Each agent has defined capabilities and an allow-list of tools. Tool access follows a default-deny model.

### Source Collection and Extraction

* Configurable web-search providers.
* URL fetching and content extraction.
* Source URL normalization.
* Duplicate-source handling.
* Content hashing.
* Bounded HTTP requests.
* Redirect validation.
* SSRF protections for external fetching.

Real-world source retrieval depends on provider configuration and requires live integration testing.

### Evidence and Claim Management

* Store sources separately from extracted evidence.
* Associate evidence with research claims.
* Require evidence excerpts to match text in stored source content.
* Track evidence quality.
* Preserve claim verification status.
* Identify supporting and contradicting evidence.
* Enforce research-level data isolation through the implemented integrity design.

### Fact Verification

The verification architecture combines deterministic integrity checks with optional language-model-assisted assessment.

Verification outcomes include:

* `supported`
* `partially_supported`
* `contradicted`
* `insufficient_evidence`

The intended workflow evaluates evidence grounding, research scope, numeric support, corroboration, contradictions, source quality, and freshness where applicable.

A model-generated assessment is not a substitute for source evidence or application-level integrity checks.

### Conflict Detection

The conflict system is designed to distinguish substantive contradictions from differences in research scope.

Potential classifications include:

* Direct contradiction.
* Numeric disagreement.
* Temporal disagreement.
* Definition mismatch.
* Geographic or population scope mismatch.
* Methodological difference.
* Insufficient information.

Different market estimates should not automatically be treated as contradictory when they measure different periods, populations, geographies, or market definitions.

### Evidence-Aware Replanning

The Research Manager can request additional research when important gaps remain.

Supported replanning reason identifiers include:

* `INSUFFICIENT_EVIDENCE`
* `VERIFICATION_FAILED`
* `LOW_SOURCE_QUALITY`
* `CONFLICT_DETECTED`
* `MISSING_DIMENSION`

Replanning is bounded by `MAX_REPLANS`.

### Executive Report Generation

The reporting layer is designed to produce structured reports containing:

* Executive summary.
* Research objective and methodology.
* Key findings.
* Market analysis.
* Customer and demand analysis.
* Competitor analysis.
* Pricing analysis.
* Regulatory considerations.
* Risk analysis.
* Opportunities.
* Conflicts and uncertainties.
* Evidence quality.
* Source references.

Factual findings should remain traceable to stored claims and evidence. Analytical inferences and uncertainties should be explicitly labelled.

### Report Export

Implemented export formats include:

* Markdown.
* JSON.
* PDF.

Export correctness, citation preservation, formatting, and language support require validation against the running application.

### Usage and Cost Tracking

The platform includes usage-metering functionality for model calls.

Depending on provider response data and configuration, tracked information can include:

* Model and provider.
* Input and output tokens.
* Execution duration.
* Errors.
* Estimated cost.

Unknown token counts and unavailable pricing should not be treated as confirmed zero usage or zero cost.

### Auditability and Observability

The architecture includes support for:

* Structured JSON logs.
* Request and execution correlation identifiers.
* Research, task, agent, and tool-execution identifiers.
* Audit events.
* Execution error metadata.

End-to-end runtime behavior must be confirmed using the documented validation procedures.

---

## Example Use Case

### Market Entry Research: B2B SaaS in Saudi Arabia

A user submits the following question:

> Analyze the opportunity for launching a B2B SaaS product targeting small and medium-sized businesses in Saudi Arabia.

The intended research workflow covers:

1. Market size, definitions, and growth trends.
2. Customer pain points and unmet needs.
3. Competitor products and positioning.
4. Pricing models and available pricing evidence.
5. Relevant regulatory requirements.
6. Market-entry and operational risks.
7. Potential underserved segments.
8. Evidence verification and conflicting estimates.
9. Unresolved questions and research gaps.
10. An executive report with traceable citations.

The system should distinguish sourced findings from estimates, hypotheses, and analytical inferences.

The workflow can be demonstrated using the deterministic demo corpus. Real external research requires configured providers and successful runtime validation.

---

## How It Works

```text
Research Question
       |
       v
Research Manager
       |
       v
Research Plan and Task Dependencies
       |
       v
Specialized Research Agents
       |
       v
Tool Registry
       |
       v
Search -> Fetch -> Extract -> Normalize
       |
       v
Source Records
       |
       v
Verbatim Evidence Extraction
       |
       v
Proposed Claims
       |
       v
Fact Checker
       |
       +----> Verification Results
       |
       +----> Conflict Detection
       |
       +----> Research Gap Detection
                    |
                    v
             Bounded Replanning
                    |
                    v
              Analyst Agent
                    |
                    v
           Evidence-Aware Report
                    |
                    v
         Markdown / JSON / PDF
```

This diagram describes the intended research architecture. Individual integrations and the complete production workflow remain subject to runtime validation.

### Source-to-Report Traceability

```text
Source
  |
  v
Evidence
  |
  v
Claim
  |
  v
Verification
  |
  v
Report Finding
```

A report finding should not be treated as verified merely because a language model generated it. Its status should reflect the available evidence and verification results.

---

## Agent Architecture

| Agent                         | Responsibility                                                                        |
| ----------------------------- | ------------------------------------------------------------------------------------- |
| Research Manager              | Plans research tasks, coordinates execution, and requests bounded follow-up research. |
| Market Research Agent         | Investigates market structure, estimates, and industry trends.                        |
| Customer and Demand Agent     | Investigates customer needs, adoption drivers, and demand evidence.                   |
| Competitor Intelligence Agent | Collects and compares competitor information.                                         |
| Pricing Research Agent        | Investigates pricing models and available pricing evidence.                           |
| Regulation Research Agent     | Researches relevant regulations and compliance requirements.                          |
| Risk Analysis Agent           | Identifies and evaluates evidence-backed business risks.                              |
| Fact Checker                  | Evaluates claim support, evidence quality, and conflicts.                             |
| Analyst Agent                 | Synthesizes sourced findings into labelled analysis and inferences.                   |

Agent definitions specify capabilities and permitted tools. Tool execution is routed through the shared tool registry.

See [`docs/AGENTS.md`](docs/AGENTS.md) for implementation details.

---

## Evidence and Claim Integrity

Atlas separates sources, evidence, claims, and verification records.

### Sources

A source represents retrieved or registered source material. Metadata may include its URL, publisher, content hash, and retrieval information.

### Evidence

Evidence represents a specific excerpt extracted from stored source content.

The evidence service is designed to reject excerpts that cannot be found verbatim in the associated source text.

### Claims

Claims represent statements proposed from research findings. Creating a claim does not automatically make it verified.

### Verification

Verification records capture the result of evaluating a claim against available evidence and applicable checks.

The design includes append-only verification records and database integrity protections intended to prevent cross-research references.

See [`docs/EVIDENCE.md`](docs/EVIDENCE.md).

---

## Verification and Conflict Detection

| Outcome                 | Meaning                                                                                |
| ----------------------- | -------------------------------------------------------------------------------------- |
| `supported`             | Available evidence supports the claim under the implemented verification rules.        |
| `partially_supported`   | Evidence supports only part of the claim or leaves material qualifications unresolved. |
| `contradicted`          | Relevant evidence conflicts with the claim.                                            |
| `insufficient_evidence` | Available evidence is not sufficient to establish the claim.                           |

These outcomes do not guarantee that a statement is universally true. Verification quality depends on source reliability, evidence coverage, research scope, and the implemented evaluation rules.

### Conflict Classification

Two findings may disagree because they refer to different years, market definitions, countries, customer segments, or methodologies.

The platform is designed to investigate these differences before treating them as direct contradictions.

---

## Research Gaps and Replanning

A research task can expose missing evidence, low-quality sources, unsupported claims, or conflicting findings.

The Research Manager can use these signals to request additional research, subject to the configured replanning limit.

Research gaps should remain visible in the final report rather than being silently converted into assumptions.

---

## Report Generation

The reporting layer is designed to combine sourced findings, verification outcomes, labelled inferences, and unresolved questions into an executive-readable document.

A report may include:

* Executive Summary.
* Research Objective.
* Methodology.
* Key Findings.
* Market Analysis.
* Customer and Demand Analysis.
* Competitor Analysis.
* Pricing Analysis.
* Regulation.
* Risk Analysis.
* Opportunities.
* Conflicts and Uncertainties.
* Evidence Quality.
* Sources.

### Export Formats

| Format   | Intended use                                          |
| -------- | ----------------------------------------------------- |
| Markdown | Version control, review, and technical documentation. |
| JSON     | Structured downstream processing and integration.     |
| PDF      | Sharing executive reports as documents.               |

**Known limitation:** The current PDF export is documented as Latin-1 only, so Arabic characters may appear as question marks.

---

## Technology Stack

| Layer                             | Technology                                 |
| --------------------------------- | ------------------------------------------ |
| Frontend                          | Next.js, React, TypeScript                 |
| Styling                           | Tailwind CSS and component-based UI        |
| Backend API                       | FastAPI and Python                         |
| Research orchestration            | Stateful agent/task execution engine       |
| Agent tooling                     | Tool registry with explicit permissions    |
| Database                          | PostgreSQL                                 |
| Background execution              | Celery                                     |
| Broker and caching infrastructure | Redis                                      |
| Research sources                  | Configurable web-search and fetch adapters |
| Reporting                         | Markdown, JSON, PDF                        |
| Testing                           | Python unit tests and Node-based tests     |
| Deployment                        | Docker and Docker Compose                  |

This table describes the repository's intended stack. It does not imply that every dependency, service, or deployment path has been successfully executed.

---

## Getting Started

### Prerequisites

For the full containerized application, the documented setup expects:

* Git.
* Docker.
* Docker Compose.
* An environment configuration based on `.env.example`.

Production mode additionally requires valid credentials for the configured language-model and web-search providers.

The complete Docker startup flow has not been verified in the authoring environment. See [`docs/UNVERIFIED.md`](docs/UNVERIFIED.md) for outstanding validation steps.

### 1. Clone the Repository

```bash
git clone https://github.com/fareselgohary2003/atlas-intelligence.git
cd atlas-intelligence
```

### 2. Configure Environment Variables

Linux, macOS, Git Bash, or WSL:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Review `.env.example` and the setup documentation before starting the services.

Use unique, strong secrets for your environment. Never commit the real `.env` file or API credentials.

### 3. Start the Application

The documented container startup command is:

```bash
docker compose up --build
```

The intended service layout includes the database, Redis, API, background worker, and web frontend.

**Runtime status:** The complete Docker workflow was not executed in the authoring sandbox. Validate it locally before assuming the entire stack starts successfully.

### 4. Open the Application

The documented endpoints are:

* Web application: http://localhost:3000
* API documentation: http://localhost:8000/docs

Confirm the actual ports and service health after startup.

---

## Demo Mode

Atlas includes a deterministic demo mode intended to demonstrate the research workflow without requiring live LLM or external search services.

Consult [`docs/DEMO.md`](docs/DEMO.md) for the exact startup commands and configuration.

The documented demo configuration uses:

```dotenv
DEMO_MODE=true
WEB_SEARCH_PROVIDER=demo
LLM_PROVIDER=demo
```

Check `.env.example` for the complete set of variables expected by the current implementation.

### Demo Data Policy

Demo sources use fictional content and reserved `.invalid` domains.

Demo records should be marked as `is_demo` and displayed as `MOCK` or `DEMO` in the interface and generated reports.

**Demo statistics and findings are fictional and must not be interpreted as real market research.**

---

## Configuration

Review `.env.example` for the authoritative list of supported environment variables.

Configuration areas include:

| Area                        | Purpose                                              |
| --------------------------- | ---------------------------------------------------- |
| Demo mode                   | Select demo or production integrations.              |
| LLM provider                | Configure the language-model adapter.                |
| LLM credentials             | Authenticate to the selected model service.          |
| Model and base URL          | Select the model and API endpoint.                   |
| Web-search provider         | Select the search adapter.                           |
| Web-search credentials      | Authenticate to the configured search service.       |
| Database URL                | Configure PostgreSQL connectivity.                   |
| Redis URL                   | Configure broker and rate-limiting infrastructure.   |
| Session and cookie settings | Configure authentication and secure cookie behavior. |
| Cost configuration          | Supply pricing information for cost estimation.      |

### Production Mode

Production mode is intended to use configured external providers.

Missing required credentials should result in an explicit configuration error rather than silently switching to fictional research data.

Live model behavior and live web-search integration remain unverified until tested with real provider credentials.

---

## Testing

The project documentation records the following test results from the authoring environment:

| Test group                                            | Recorded result        |
| ----------------------------------------------------- | ---------------------- |
| Python tests executed                                 | 214 passed, 0 failures |
| Node tests executed                                   | 9 passed, 0 failures   |
| Additional test functions for unverified integrations | 40 not executed        |

These are recorded results, not a guarantee that every test has been rerun against the latest repository revision.

### Run the Test Script

From the repository root:

```bash
bash scripts/run_tests.sh
```

On Windows, use Git Bash or WSL if required by the script.

Check the script's dependencies and output to confirm exactly which test groups were executed.

### Additional Validation

Before treating the full application as production-ready, validate:

* PostgreSQL migrations and constraints.
* SQL repository integration tests.
* FastAPI routes and authorization.
* SSE streaming and reconnect behavior.
* Celery worker execution.
* Redis behavior.
* Frontend dependency installation and production build.
* Docker image builds.
* Docker Compose startup and health checks.
* End-to-end research execution.
* Real search-provider integration.
* Real LLM integration.
* Report export integrity.

See [`docs/UNVERIFIED.md`](docs/UNVERIFIED.md) for outstanding checks.

---

## Security

Security is a core design consideration because the platform fetches external content, stores research data, and coordinates tools with different permissions.

The implementation includes security components intended to support:

* Explicit agent tool permissions.
* SSRF protections for external fetching.
* Redirect validation.
* Workspace and research-level access isolation.
* Role-based access control.
* HTTP-only cookie-based sessions.
* CSRF protection.
* Rate limiting.
* Secret redaction in logs.
* Database integrity constraints.
* Source-grounded evidence validation.

The presence of security code does not establish that every deployment configuration is secure.

Validate authentication flows, cookie flags, CSRF enforcement, rate limiting, database permissions, and cross-workspace authorization before exposing the application publicly.

See [`docs/SECURITY.md`](docs/SECURITY.md).

---

## Known Limitations

### Runtime Validation

The following areas have not been fully validated in the authoring environment:

* PostgreSQL migrations and SQL repositories.
* FastAPI routes and SSE behavior.
* Celery and Redis worker execution.
* The complete Next.js application and Docker deployment.
* Live LLM and web-search provider integrations.

### PDF and Language Support

* The current PDF export is documented as Latin-1 only.
* Arabic characters may appear as question marks in exported PDFs.
* Arabic PDF support requires an appropriate Unicode-capable font and export implementation.

### Research Retrieval

* JavaScript-rendered pages are not supported by the documented fetcher.
* PDF source ingestion is not implemented in the documented source pipeline.
* Robots.txt handling is not implemented.
* SSRF protections require validation against the actual runtime network environment.

### Verification

* Numeric comparisons do not automatically normalize units.
* Differences in definitions or methodology may require additional research and interpretation.
* Evidence quality depends on the available source content and evaluation rules.

### Authentication and Account Management

* Password reset is not implemented in the documented feature set.
* Email verification is not implemented in the documented feature set.
* Two-factor authentication is not implemented in the documented feature set.
* Sessions are documented as stateless, without server-side revocation.

See [`docs/UNVERIFIED.md`](docs/UNVERIFIED.md), [`docs/SECURITY.md`](docs/SECURITY.md), [`docs/EVIDENCE.md`](docs/EVIDENCE.md), and [`docs/TOOLS.md`](docs/TOOLS.md).

---

## Unverified Components

The following areas require explicit runtime validation before they can be treated as working end to end.

| Area               | Validation required                                                           |
| ------------------ | ----------------------------------------------------------------------------- |
| PostgreSQL         | Apply migrations, validate constraints, and run repository integration tests. |
| FastAPI            | Start the application and exercise API routes.                                |
| SSE                | Verify event delivery, reconnect behavior, and terminal states.               |
| Celery and Redis   | Start the worker and validate queued research execution.                      |
| Next.js            | Install dependencies, run the application, and execute a production build.    |
| Docker             | Build images, start services, and validate health checks.                     |
| External search    | Run queries through the configured live search provider.                      |
| External LLM       | Validate model requests, structured output, errors, and usage reporting.      |
| Full research flow | Execute a complete run and trace report findings back to their sources.       |
| Report exports     | Validate content, citations, encoding, and output files.                      |

An unverified component is not necessarily broken; it means its behavior has not yet been demonstrated under the relevant conditions.

See [`docs/UNVERIFIED.md`](docs/UNVERIFIED.md) for exact outstanding checks and commands.

---

## Roadmap

Potential future improvements include:

* Unicode-capable PDF export with Arabic support.
* Password reset and email verification.
* Two-factor authentication.
* Server-side session revocation.
* Robots.txt handling where appropriate.
* JavaScript-rendered page support.
* PDF document ingestion.
* Numeric unit normalization for claim comparison.
* Broader end-to-end testing.
* Production validation and deployment hardening.

These items describe potential improvements, not features claimed to be complete.

---

## Repository

**GitHub:** https://github.com/fareselgohary2003/atlas-intelligence

---

## Author

**Fares Elgohary**

GitHub: [@fareselgohary2003](https://github.com/fareselgohary2003)

---

## License

No license is asserted by this README.

Add an appropriate `LICENSE` file before distributing the repository for public reuse.

---

## Project Philosophy

Atlas Intelligence explores how agentic AI can support complex research workflows while making evidence, uncertainty, and execution visible.

The goal is not simply to generate a convincing answer. It is to build a system where readers can inspect the research process, trace findings to sources, evaluate verification outcomes, and understand what remains unknown.

**Atlas Intelligence — From complex questions to traceable intelligence.**
