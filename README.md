# Atlas Intelligence

### An Autonomous Enterprise Research & Intelligence Platform

**From complex questions to traceable intelligence.**

Atlas Intelligence is an agentic AI research platform designed to transform complex business questions into structured research workflows, evidence-backed findings, and cited executive reports.

Instead of treating research as a single conversation with a language model, Atlas coordinates specialized agents to plan research tasks, gather sources, extract evidence, evaluate claims, detect conflicting information, identify research gaps, and synthesize findings into an auditable report.

The platform is built around **traceability, evidence quality, explicit uncertainty, and controlled agent execution**.

> **Project status:** The core research engine and selected application logic have automated test coverage. Database integrations, API runtime, background workers, Docker deployment, and live external-provider integrations remain unverified until the documented runtime checks have been executed. See [`docs/UNVERIFIED.md`](docs/UNVERIFIED.md) for details.

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
* [Application Interface](#application-interface)
* [Technology Stack](#technology-stack)
* [Architecture](#architecture)
* [Repository Structure](#repository-structure)
* [Getting Started](#getting-started)
* [Running the Offline Demo](#running-the-offline-demo)
* [Configuration](#configuration)
* [Testing](#testing)
* [Security](#security)
* [Observability](#observability)
* [Known Limitations](#known-limitations)
* [Unverified Components](#unverified-components)
* [Roadmap](#roadmap)
* [Contributing](#contributing)
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
* **Explicit uncertainty:** Unsupported claims, conflicting information, and research gaps should be visible.
* **Controlled autonomy:** Agents operate through registered capabilities and explicit tool permissions.
* **Bounded execution:** Retries, cancellation, and replanning should follow defined execution rules.
* **Honest reporting:** Demo data, estimated costs, and unverified integrations must not be presented as confirmed production results.

Atlas is designed as a research workflow platform, not simply a conversational interface. Its actual runtime capabilities depend on the configured services and the validation status documented in the repository.

---

## Key Features

### 1. Multi-Agent Research Orchestration

* Decompose complex research objectives into specialized tasks.
* Represent task dependencies and execution state.
* Execute independent tasks concurrently where supported.
* Track task progress, failures, and execution events.
* Support pause, resume, and cancellation workflows in the implemented orchestration architecture.
* Limit replanning through a configurable maximum.

### 2. Specialized Research Agents

The platform defines nine agent roles:

* Research Manager
* Market Research Agent
* Customer and Demand Agent
* Competitor Intelligence Agent
* Pricing Research Agent
* Regulation Research Agent
* Risk Analysis Agent
* Fact Checker
* Analyst Agent

Each agent has defined capabilities and an allow-list of tools. Tool access follows a default-deny model rather than allowing every agent to invoke every available tool.

### 3. Source Collection and Extraction

The research tool layer is designed to support:

* Configurable web search providers.
* URL fetching and content extraction.
* Source URL normalization.
* Duplicate-source handling.
* Content hashing.
* Bounded HTTP requests.
* Redirect validation.
* SSRF protections for external fetching.

Real-world source retrieval depends on the provider configuration and must be validated against the live service.

### 4. Evidence and Claim Management

* Store sources separately from extracted evidence.
* Associate evidence with research claims.
* Require evidence excerpts to match text in the stored source content.
* Track evidence quality.
* Preserve claim verification status.
* Identify supporting and contradicting evidence.
* Maintain research-level data isolation in the implemented integrity design.

### 5. Fact Verification

The verification architecture combines deterministic integrity checks with optional language-model-assisted assessment.

Verification outcomes include:

* `supported`
* `partially_supported`
* `contradicted`
* `insufficient_evidence`

The intended workflow checks evidence grounding, research scope, numeric support, corroboration, contradictions, source quality, and freshness where applicable.

A model-generated assessment is not a substitute for source evidence or the integrity checks enforced by the application.

### 6. Conflict Detection

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

### 7. Evidence-Aware Replanning

The Research Manager can request additional research when important gaps remain.

Supported replanning reason identifiers include:

* `INSUFFICIENT_EVIDENCE`
* `VERIFICATION_FAILED`
* `LOW_SOURCE_QUALITY`
* `CONFLICT_DETECTED`
* `MISSING_DIMENSION`

Replanning is bounded by `MAX_REPLANS` to prevent unbounded research loops.

### 8. Executive Report Generation

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

Factual findings should remain traceable to stored claims and evidence. Analytical inferences and uncertainties should be explicitly labelled rather than presented as independently verified facts.

### 9. Report Export

Implemented export formats include:

* Markdown.
* JSON.
* PDF.

Export correctness, formatting, citation preservation, and language support should be checked against the actual runtime implementation. The current PDF implementation has a documented limitation with Arabic text; see [Known Limitations](#known-limitations).

### 10. Usage and Cost Tracking

The platform includes usage-metering functionality for model calls.

Depending on provider response data and configuration, tracked information can include:

* Model and provider.
* Input tokens.
* Output tokens.
* Total tokens.
* Execution duration.
* Errors.
* Estimated cost.

Unknown token counts or unavailable pricing should not be treated as confirmed zero usage or zero cost.

### 11. Auditability and Observability

The application includes architecture and implementation for:

* Structured JSON logs.
* Request and execution correlation identifiers.
* Research, task, agent, and tool-execution identifiers.
* Audit events.
* Execution error metadata.

The extent of end-to-end runtime coverage must be confirmed using the documented validation procedures.

### 12. Deterministic Demo Mode

Demo mode is designed to demonstrate the research workflow without requiring live external search or language-model services.

It uses fictional sources on the reserved `.invalid` top-level domain and marks demo records as `is_demo`.

Demo records must remain clearly identifiable as `MOCK` or `DEMO` and must never be interpreted as real market research.

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

The system should distinguish verified source material from estimates, hypotheses, and analytical inferences.

The example can run against the deterministic demo corpus or, after provider configuration and runtime validation, against real external sources.

---

## How It Works

The conceptual research pipeline is:

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

This diagram describes the intended architecture. Individual integrations and the complete end-to-end production workflow remain subject to the runtime validation documented in `docs/UNVERIFIED.md`.

### Source-to-Report Traceability

The intended traceability chain is:

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

The project defines nine agent roles.

| Agent                         | Responsibility                                                                        |
| ----------------------------- | ------------------------------------------------------------------------------------- |
| Research Manager              | Plans research tasks, coordinates execution, and requests bounded follow-up research. |
| Market Research Agent         | Investigates market structure, market estimates, and industry trends.                 |
| Customer and Demand Agent     | Investigates customer needs, adoption drivers, and demand evidence.                   |
| Competitor Intelligence Agent | Collects and compares competitor information.                                         |
| Pricing Research Agent        | Investigates pricing models and available pricing evidence.                           |
| Regulation Research Agent     | Researches relevant regulations and compliance requirements.                          |
| Risk Analysis Agent           | Identifies and evaluates evidence-backed business risks.                              |
| Fact Checker                  | Evaluates claim support, evidence quality, and conflicts.                             |
| Analyst Agent                 | Synthesizes sourced findings into labelled analysis and inferences.                   |

Agent definitions specify capabilities and permitted tools. Tool execution is routed through the shared tool registry.

For additional implementation details, see [`docs/AGENTS.md`](docs/AGENTS.md).

---

## Evidence and Claim Integrity

Atlas separates sources, evidence, claims, and verification records.

### Sources

A source represents retrieved or otherwise registered source material. Its metadata may include a URL, publisher, content hash, and retrieval information.

### Evidence

Evidence represents a specific excerpt extracted from stored source content.

The evidence service is designed to reject excerpts that cannot be found verbatim in the associated source text.

### Claims

Claims represent statements proposed from research findings. Creating a claim does not automatically make it verified.

### Verification

Verification records capture the result of evaluating a claim against available evidence and applicable checks.

The implemented design includes append-only verification records and database integrity protections intended to prevent cross-research references.

See [`docs/EVIDENCE.md`](docs/EVIDENCE.md) for implementation details and documented limitations.

---

## Verification and Conflict Detection

Verification outcomes describe how well available evidence supports a claim.

| Outcome                 | Meaning                                                                                |
| ----------------------- | -------------------------------------------------------------------------------------- |
| `supported`             | Available evidence supports the claim under the implemented verification rules.        |
| `partially_supported`   | Evidence supports only part of the claim or leaves material qualifications unresolved. |
| `contradicted`          | Relevant evidence conflicts with the claim.                                            |
| `insufficient_evidence` | Available evidence is not sufficient to establish the claim.                           |

These outcomes should not be confused with a guarantee that a statement is universally true. Verification quality depends on source reliability, evidence coverage, research scope, and the implemented validation rules.

### Conflict Classification

The platform is designed to investigate why two findings disagree.

For example, two market estimates might differ because:

* They refer to different years.
* One measures SaaS revenue while another measures the broader cloud market.
* They cover different countries or customer segments.
* They use different market-sizing methodologies.

Such differences should be explained before treating the estimates as direct contradictions.

---

## Research Gaps and Replanning

A research task can expose missing evidence, low-quality sources, unsupported claims, or conflicting findings.

The Research Manager can use these signals to request additional research, subject to the configured replanning limit.

This approach is intended to reduce the risk of producing a confident report when critical questions remain unanswered.

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
* Conflicts.
* Uncertainties.
* Evidence Quality.
* Conclusion.
* Sources.

Reports should preserve source references and verification status so readers can distinguish what the evidence supports from what remains an analytical interpretation.

### Export Formats

| Format   | Intended use                                          |
| -------- | ----------------------------------------------------- |
| Markdown | Version control, review, and technical documentation. |
| JSON     | Structured downstream processing and integration.     |
| PDF      | Sharing executive reports as documents.               |

See the documented export limitations before relying on PDF output for Arabic-language reports.

---

## Application Interface

The frontend is designed around a research workspace rather than a conventional chat window.

The application includes interface areas for:

* Dashboard.
* Research projects.
* Live Research Workspace.
* Research Plan.
* Agent Activity.
* Evidence.
* Claims.
* Sources.
* Reports.
* Agents.
* Audit Log.
* Settings.
* Evidence Graph.

The live workspace is designed to display research execution and evidence relationships. Actual integration with backend events and persisted data must be validated in a running environment.

### Screenshots and Demo

Add screenshots or a short recording of the actual application here once available.

Recommended assets:

```text
docs/
  screenshots/
    dashboard.png
    research-workspace.png
    evidence-explorer.png
    claims.png
    report.png
```

Only include screenshots that represent the current implementation. Clearly label screenshots containing demo data.

---

## Technology Stack

The repository is organized around the following technologies.

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
| Research sources                  | Configurable web search and fetch adapters |
| Reporting                         | Markdown, JSON, and PDF export             |
| Testing                           | Python unit tests and Node-based tests     |
| Deployment                        | Docker and Docker Compose                  |

The table describes the repository's intended stack. It does not mean every dependency, service, or deployment path has been run successfully in the target environment.

---

## Architecture

The application separates research orchestration, agent logic, tool execution, evidence services, persistence, and the user interface.

### Backend

The backend contains the research engine, agents, tool registry, source retrieval, evidence management, verification logic, report generation, and API components.

### Frontend

The frontend provides the dashboard, research forms, execution workspace, evidence views, claims, reports, and graph visualization.

### Persistence

PostgreSQL is the intended persistent store for research projects, tasks, events, sources, evidence, claims, verification results, conflicts, and related records.

### Background Execution

Celery and Redis are intended to support background research execution.

### External Providers

Production mode uses configured language-model and search providers. Live provider compatibility, authentication, rate limits, and response behavior require real runtime tests.

---

## Repository Structure

The main repository areas are:

```text
.
├── apps/
│   ├── api/
│   │   └── app/
│   │       ├── agents/
│   │       ├── tools/
│   │       ├── evidence/
│   │       ├── reporting/
│   │       ├── services/
│   │       ├── repositories/
│   │       ├── api/
│   │       └── migrations/
│   └── web/
├── docs/
│   ├── AGENTS.md
│   ├── EVIDENCE.md
│   ├── SECURITY.md
│   ├── TOOLS.md
│   ├── DEMO.md
│   └── UNVERIFIED.md
├── scripts/
│   ├── run_tests.sh
│   ├── gen_api_doc.py
│   └── audit_repo.py
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

This is a structural overview. Check the actual repository before relying on any path or assuming that every listed module exists in the current revision.

---

## Getting Started

### Prerequisites

For the full containerized application, the documented setup expects:

* Git.
* Docker.
* Docker Compose.
* An environment configuration based on `.env.example`.

Production mode additionally requires valid credentials for the configured language-model and web-search providers.

The complete Docker startup flow has not been verified in the authoring environment. Follow `docs/UNVERIFIED.md` for the latest validation status and any required troubleshooting.

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/atlas-intelligence.git
cd atlas-intelligence
```

Replace `YOUR_USERNAME` with your GitHub username.

### 2. Configure Environment Variables

Copy the example configuration:

```bash
cp .env.example .env
```

On Windows PowerShell, you can use:

```powershell
Copy-Item .env.example .env
```

Review `.env.example` and the setup documentation before starting the services.

Use unique, strong secrets for local and production environments. Never commit the actual `.env` file or real credentials.

### 3. Start the Application

The documented container startup command is:

```bash
docker compose up --build
```

The intended service layout includes the database, Redis, API, background worker, and web frontend.

**Runtime status:** This command was not executed in the authoring sandbox. Do not assume that the complete stack starts successfully until it has been run and validated on your machine.

### 4. Open the Application

The configured development endpoints are documented as:

* Web application: `http://localhost:3000`
* API documentation: `http://localhost:8000/docs`

Confirm the actual ports and service health after startup.

---

## Running the Offline Demo

Atlas includes a deterministic demo mode intended to demonstrate the research workflow without a live LLM API or external web-search service.

Consult [`docs/DEMO.md`](docs/DEMO.md) for the exact environment variables and startup instructions.

The documented configuration uses:

```dotenv
DEMO_MODE=true
WEB_SEARCH_PROVIDER=demo
LLM_PROVIDER=demo
```

Check `.env.example` and `docs/DEMO.md` for the complete configuration expected by the current implementation.

### Demo Data Policy

Demo sources use fictional content and reserved `.invalid` domains.

All demo records should be marked as `is_demo` and presented as `MOCK` or `DEMO` in the interface and generated reports.

Demo statistics and findings are not real market data and must not be used as factual business research.

---

## Configuration

The project uses environment variables for application settings, credentials, provider selection, and infrastructure connectivity.

Review `.env.example` for the authoritative list of supported variables.

Typical configuration areas include:

| Configuration area          | Purpose                                                         |
| --------------------------- | --------------------------------------------------------------- |
| Demo mode                   | Select deterministic mock execution or production integrations. |
| LLM provider                | Configure the language-model adapter.                           |
| LLM credentials             | Authenticate to the selected model service.                     |
| LLM model and base URL      | Select the model and compatible API endpoint.                   |
| Web-search provider         | Select the search adapter.                                      |
| Web-search credentials      | Authenticate to the configured search service.                  |
| Database URL                | Configure PostgreSQL connectivity.                              |
| Redis URL                   | Configure broker and rate-limiting infrastructure.              |
| Session and cookie settings | Configure authentication and secure cookie behavior.            |
| Cost configuration          | Supply pricing information when cost estimation is required.    |

Do not copy example values into a public production deployment without reviewing their security implications.

### Production Mode

Production mode is intended to use configured external providers.

Missing required credentials should result in an explicit configuration error rather than silently switching to fictional research data.

Live model behavior and live web-search integration remain unverified until tested with real provider credentials.

---

## Testing

The project includes automated tests for core research logic and selected frontend logic.

The recorded test status in the current project documentation is:

| Test group                                                    | Recorded result        |
| ------------------------------------------------------------- | ---------------------- |
| Python tests executed in the authoring sandbox                | 214 passed, 0 failures |
| Node tests executed in the authoring sandbox                  | 9 passed, 0 failures   |
| Additional test functions written for unverified integrations | 40 not executed        |

**These are recorded results, not a guarantee that every test has been rerun against the latest repository revision.** Run the commands again to confirm the current state.

### Run the Available Test Script

From the repository root:

```bash
bash scripts/run_tests.sh
```

On Windows, use a compatible shell such as Git Bash or WSL if required by the script.

The script and its dependency requirements should be checked before execution. The exact test groups it runs may differ from the groups listed above.

### Additional Validation

Before claiming that the full application works, validate the following where the necessary dependencies and services are available:

* PostgreSQL migrations.
* SQL repository contracts.
* FastAPI route tests.
* Authentication and authorization.
* SSE streaming.
* Celery worker execution.
* Redis behavior.
* Frontend dependency installation and production build.
* Docker image builds.
* Docker Compose startup and health checks.
* End-to-end demo execution.
* Real search-provider integration.
* Real LLM integration.
* Report export integrity.

For exact unverified commands, see [`docs/UNVERIFIED.md`](docs/UNVERIFIED.md).

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
* Verifiable evidence grounding.

### Security Limitations

The presence of security code does not establish that every deployment configuration is secure.

Validate the actual runtime configuration, authentication flows, cookie flags, CSRF enforcement, rate limiting, database permissions, and cross-workspace authorization before exposing the application publicly.

See [`docs/SECURITY.md`](docs/SECURITY.md) for additional details and known limitations.

---

## Observability

The observability architecture uses structured logs and correlation identifiers to help trace execution across application components.

The intended trace follows:

```text
Request
  -> Research
    -> Task
      -> Agent Run
        -> Tool Execution
          -> Source
            -> Evidence
              -> Claim
                -> Verification
```

This structure is intended to make failures easier to investigate and to preserve context across a research run.

Logs should not contain API keys, session tokens, or unnecessary sensitive content.

End-to-end correlation and audit completeness must be verified in a running environment.

---

## Known Limitations

The following limitations are recorded in the current project description and should be reviewed against the latest implementation.

### Runtime Validation

* PostgreSQL migrations and SQL repositories have not been executed in the authoring sandbox.
* FastAPI routes and SSE behavior have not been fully runtime-validated there.
* Celery and Redis worker execution have not been validated there.
* The full Next.js application and Docker deployment have not been executed there.
* Live LLM and web-search provider adapters have not been tested against real services there.

### PDF and Language Support

* The current PDF export implementation is documented as Latin-1 only.
* Arabic characters may appear as question marks in exported PDFs.
* Arabic-language PDF output requires an appropriate Unicode-capable font and export implementation.

### Research Retrieval

* JavaScript-rendered pages are not supported by the documented fetcher.
* PDF source ingestion is not implemented in the documented source pipeline.
* Robots.txt handling is not implemented.
* SSRF protections require validation against the actual runtime network environment.

### Verification

* Numeric comparisons do not automatically normalize units.
* Differences in definitions or methodology may require additional research and careful interpretation.
* Evidence quality depends on the available source content and the implemented evaluation rules.

### Authentication and Account Management

* Password reset is not implemented in the documented feature set.
* Email verification is not implemented in the documented feature set.
* Two-factor authentication is not implemented in the documented feature set.
* Sessions are documented as stateless, without server-side revocation.

See [`docs/UNVERIFIED.md`](docs/UNVERIFIED.md), [`docs/SECURITY.md`](docs/SECURITY.md), [`docs/EVIDENCE.md`](docs/EVIDENCE.md), and [`docs/TOOLS.md`](docs/TOOLS.md) for additional detail.

---

## Unverified Components

The following areas require explicit runtime validation before they can be treated as working end to end:

| Area               | Validation required                                                             |
| ------------------ | ------------------------------------------------------------------------------- |
| PostgreSQL         | Apply migrations, validate constraints, and run repository integration tests.   |
| FastAPI            | Start the application and exercise API routes.                                  |
| SSE                | Verify event delivery, reconnect behavior, and terminal states.                 |
| Celery and Redis   | Start the worker and validate queued research execution.                        |
| Next.js            | Install dependencies, run the application, and execute a production build.      |
| Docker             | Build images, start services, and validate health checks.                       |
| External search    | Run queries through the configured live search provider.                        |
| External LLM       | Validate model requests, structured output, errors, and usage reporting.        |
| Full research flow | Execute a complete research run and verify traceability from sources to report. |
| Report exports     | Validate content, citations, encoding, and output files.                        |

The absence of runtime validation does not necessarily mean a component is broken. It means its behavior has not yet been demonstrated under the relevant conditions.

See [`docs/UNVERIFIED.md`](docs/UNVERIFIED.md) for the exact outstanding checks and commands.

---

## Roadmap

Potential follow-up work includes:

* Unicode-capable PDF export with Arabic support.
* Password reset and email verification.
* Two-factor authentication.
* Server-side session revocation.
* Robots.txt handling where appropriate.
* JavaScript-rendered page support.
* PDF document ingestion.
* Numeric unit normalization for claim comparison.
* Broader end-to-end testing across the complete infrastructure.
* Additional production validation and deployment hardening.

This roadmap describes areas for improvement, not a claim that these features are already implemented.

---

## Contributing

Contributions and technical feedback are welcome.

When contributing:

1. Keep evidence and claim integrity rules intact.
2. Add regression tests for bugs and security issues.
3. Do not introduce silent fallbacks from production to demo mode.
4. Preserve explicit uncertainty and source traceability.
5. Document new configuration variables.
6. Update `docs/UNVERIFIED.md` when runtime validation changes.
7. Avoid claiming tests passed unless they were actually executed.

---

## License

No license is asserted by this README.

Before publishing the repository for public reuse, choose a license appropriate for the project and add the corresponding `LICENSE` file.

---

## Project Philosophy

Atlas Intelligence explores how agentic AI can support complex research workflows while making evidence, uncertainty, and execution visible.

The goal is not simply to generate a convincing answer. It is to build a system where readers can inspect the research process, trace findings to sources, evaluate verification outcomes, and understand what remains unknown.

**Atlas Intelligence — From complex questions to traceable intelligence.**
