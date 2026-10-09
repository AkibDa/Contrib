# Contrib — Backend

<p align="center">
  <strong>Open source for open source.</strong>
  <br />
  From a GitHub issue to relevant code, clear reasoning, and a suggested patch.
</p>

<p align="center">
  Python · FastAPI · Multi-Agent System · Retrieval-Augmented Generation
</p>

---

## Overview

**Contrib** is an open-source contribution assistant that helps developers understand unfamiliar repositories and find a practical path toward resolving GitHub issues.

The backend powers Contrib's repository intelligence and issue-analysis capabilities. It coordinates a specialized multi-agent pipeline that analyzes an issue, retrieves relevant code, explains the implementation, and optionally generates a unified code patch.

Instead of sending an entire repository to a language model, Contrib follows a **retrieve-then-reason architecture**: locate the most relevant code first, then generate an explanation using the retrieved context.

## Core Features

- **GitHub Integration** — Fetch repository and issue information through the GitHub REST API.
- **Repository Ingestion** — Clone and index repositories for code retrieval.
- **Cached Repository Index** — Reuse indexed code for repeated issue analyses and repository-chat queries.
- **Issue Classification** — Identify issue type, estimate difficulty, determine required skills, hypothesize root causes, and list affected areas.
- **Hybrid Code Retrieval** — Combine semantic vector search and BM25 lexical search.
- **Neural Reranking** — Re-score candidate files to prioritize relevant code context.
- **Dependency-Aware Retrieval** — Expand context using code dependency relationships.
- **Code Explanation** — Produce understandable explanations and step-by-step reasoning.
- **Contribution Guidance** — Generate practical steps for investigating and addressing an issue.
- **Optional Patch Generation** — Produce a unified diff that developers can review.
- **Repository Chat** — Reuse the repository index to answer follow-up questions.

## System Architecture

```text
                ┌─────────────────────────┐
                │       React Frontend    │
                │      App.jsx / Chatbox  │
                └────────────┬────────────┘
                             │ HTTPS
                             ▼
                ┌─────────────────────────┐
                │    FastAPI Backend      │
                │  main.py / api.py       │
                │  Validation & Routing   │
                └────────────┬────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │ Multi-Agent Orchestrator│
                │       services.py       │
                └────────────┬────────────┘
                             │
               ┌─────────────┼─────────────┐
               ▼             ▼             ▼
        ┌────────────┐ ┌────────────┐ ┌────────────┐
        │   Issue    │ │ Retrieval  │ │ Reasoning  │
        │  Analyzer  │ │   Agent    │ │   Agent    │
        └────────────┘ └─────┬──────┘ └─────┬──────┘
                             │              │
                             ▼              ▼
                    ┌────────────────┐ ┌─────────────┐
                    │ Hybrid Search  │ │ LLM Provider│
                    │ ChromaDB/BM25  │ │ Explanation │
                    └───────┬────────┘ │ & Patch     │
                            │          └──────┬──────┘
                            ▼                 │
                    ┌────────────────┐        │
                    │ Rerank +       │        │
                    │ Dependency     │        │
                    │ Expansion      │        │
                    └───────┬────────┘        │
                            └────────┬─────────┘
                                     ▼
                           ┌──────────────────┐
                           │ Structured Result│
                           │ Explanation, Files│
                           │ Steps, Optional  │
                           │ Patch            │
                           └──────────────────┘
```

The three agents are coordinated by the backend; the embedding model, reranking model, search infrastructure, GitHub integration, and LLM provider support their execution.

## Multi-Agent Pipeline

When a request reaches `POST /api/analyze-issue`, the backend coordinates three specialized agents.

### 1. Issue Analyzer Agent

**Function:** `run_issue_analyzer`

The first agent interprets the GitHub issue and creates a structured understanding of the problem.

Responsibilities:

- Classify the issue, such as a bug or feature request.
- Estimate implementation difficulty.
- Identify relevant skills.
- Hypothesize the root cause.
- Identify affected repository areas.

**Output:** An issue breakdown that informs the retrieval and reasoning stages.

### 2. Retrieval Agent

**Function:** `run_retrieval_agent`

The retrieval agent identifies the most relevant repository context for the issue.

Responsibilities:

- Build a structured retrieval plan.
- Extract relevant symbols and modules from the issue.
- Search using ChromaDB vector embeddings and BM25 lexical matching.
- Rank candidate files.
- Expand context through dependency relationships.
- Return the most relevant code and supporting context.

**Output:** Ranked files, retrieved code context, and dependency insights.

### 3. Reasoning Agent

**Function:** `run_reasoning_agent`

The reasoning agent uses the issue and retrieved context to prepare an actionable response.

Responsibilities:

- Explain what the relevant code does.
- Produce a step-by-step reasoning trace.
- Describe a practical contribution path.
- Explain how the identified code relates to the issue.
- Optionally generate a unified code patch (diff).

**Output:** A structured explanation, relevant files, contribution steps, and an optional patch.

The generated patch is a suggestion for developer review, not a guarantee that the issue is resolved or that the code passes tests.

## Retrieval Architecture

Contrib combines multiple retrieval stages to balance recall and precision.

| Component | Responsibility |
|---|---|
| Repository Loader | Clone and prepare the repository for indexing |
| Cached Repository Index | Avoid rebuilding the index for every request when reuse is possible |
| Embedding Server | Represent code and queries as vectors |
| ChromaDB | Store and search vector embeddings |
| BM25 Search | Retrieve lexical matches for exact terms and identifiers |
| Rerank Server | Re-score candidate files for greater relevance |
| Dependency Graph | Expand context to related code and dependencies |

### Why Hybrid Retrieval?

Semantic search can find conceptually related code even when issue wording differs from the implementation. BM25 complements it by matching exact identifiers, symbols, and keywords.

The reranking stage then prioritizes candidate results before the reasoning agent consumes the retrieved context.

```text
Issue Text
    │
    ▼
Retrieval Plan
    │
    ├──► ChromaDB Vector Search
    │
    └──► BM25 Lexical Search
                 │
                 ▼
         Candidate Results
                 │
                 ▼
             Reranking
                 │
                 ▼
       Dependency Expansion
                 │
                 ▼
       Relevant Code Context
                 │
                 ▼
          Reasoning Agent
```

## Backend Request Flow

1. **Receive:** The React frontend submits a repository and issue for analysis.
2. **Validate:** The API applies request validation and configured request controls.
3. **Fetch:** GitHub integration obtains the required repository and issue information.
4. **Analyze:** The Issue Analyzer Agent classifies the issue and identifies affected areas.
5. **Retrieve:** The Retrieval Agent performs hybrid search, reranking, and dependency expansion.
6. **Reason:** The Reasoning Agent produces explanations, contribution steps, and an optional patch.
7. **Respond:** The backend returns the analysis to the frontend.
8. **Follow up:** Repository chat can reuse the cached index for further questions.

The precise ordering and error-handling behavior should follow the implemented orchestration in `api.py` and `services.py`.

## Technology Stack

| Layer | Technologies |
|---|---|
| Language | Python 3.10+ |
| API Framework | FastAPI |
| ASGI Server | Uvicorn |
| API Organization | `api.py`, `schemas.py`, `config.py`, `limiter.py` |
| Agent Orchestration | `services.py` |
| Semantic Retrieval | Embedding model, ChromaDB |
| Lexical Retrieval | BM25 |
| Result Optimization | Dedicated reranking model |
| Code Context | Dependency graph expansion |
| Repository Integration | GitHub REST API |
| Generation | Configured LLM provider |

## Project Structure

The following is a logical overview of the main components; retain the actual directory layout of your repository.

```text
backend/
├── main.py          # Application entry point
├── api.py           # API routes and request coordination
├── services.py      # Multi-agent orchestration
├── schemas.py       # Request and response validation
├── config.py        # Application configuration
├── limiter.py       # Rate-limiting logic
├── requirements.txt # Python dependencies, if present
└── README.md
```

The embedding and reranking services may run separately from the API process. Their deployment configuration should be documented alongside the actual model-serving setup.

## Getting Started

### Prerequisites

- Python 3.10 or newer
- Git
- Access to the required GitHub resources
- The configured LLM provider and model services
- Access to the repository's required Python dependencies

### 1. Navigate to the Backend

```bash
cd backend
```

If your backend directory has a different name or location, adjust the path accordingly.

### 2. Create a Virtual Environment

```bash
python -m venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

If the repository contains `requirements.txt`:

```bash
pip install -r requirements.txt
```

Otherwise, use the dependency manager and lockfile maintained by the project.

### 4. Configure the Services

Review `config.py` and the existing project configuration to identify the required values for:

- GitHub access and API settings.
- LLM provider credentials and configuration.
- Embedding and reranking service addresses.
- Repository index and cache locations.
- Rate limits and other application settings.

Use the actual environment-variable names defined by the code. Keep credentials out of source control and provide a local environment template without real secrets.

### 5. Start the API

If `main.py` exposes the FastAPI application as `app`, start the development server using:

```bash
uvicorn main:app --reload
```

Run this from the directory where `main.py` is importable. Use the project's actual application object and startup instructions if they differ.

### 6. Verify the API

The main issue-analysis endpoint is:

```text
POST /api/analyze-issue
```

Once the server is running, check the configured API documentation route, if enabled, and use the request schema in `schemas.py` to construct a valid request.

The embedding, reranking, and LLM services must also be reachable for the corresponding analysis stages to work successfully.

## Design Rationale

Contrib uses a fixed retrieve-then-reason pipeline rather than giving an autonomous agent unrestricted control over the workflow.

- **Localization first:** Identify relevant files before generating a solution.
- **Hybrid retrieval:** Combine semantic similarity with lexical matching.
- **Reranking:** Refine candidate results before sending context to the LLM.
- **Cached indexing:** Reuse repository data across analysis and follow-up chat.
- **Human in the loop:** Explain the suggested changes instead of silently applying them.
- **Separation of concerns:** Keep API coordination, agent logic, retrieval, and model serving distinct.

This approach is designed to make issue analysis more focused, transparent, and useful to contributors. Its effectiveness still needs to be measured on real repository issues.

## Current Limitations and Future Improvements

- **Patch validation:** Add automated test execution and patch validation before reporting a fix as verified.
- **Cross-file reasoning:** Improve dependency-aware retrieval for changes that span multiple modules.
- **Retrieval evaluation:** Measure whether the relevant files appear among the top-ranked results.
- **Operational complexity:** Monitor the overhead of running separate embedding and reranking model services.
- **Reliability:** Add clear error handling for GitHub failures, unavailable model services, empty retrieval results, and malformed requests.
- **Evaluation:** Compare retrieval quality with and without reranking across a representative sample of closed GitHub issues.

## Contributing

Contributions to Contrib are welcome.

1. Identify the relevant API, service, or retrieval component.
2. Keep changes focused and consistent with the existing architecture.
3. Add or update tests for changed behavior.
4. Run the available test suite and code-quality checks.
5. Document configuration changes and new service requirements.

## License

Refer to the repository's root-level `LICENSE` file for the applicable license.

---

<p align="center">
  <strong>Contrib</strong>
  <br />
  Helping developers understand the code before changing it.
</p>
