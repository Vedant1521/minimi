# Project Milestones: Minimi

This document defines the sequential development milestones for the **Minimi** conversational agent. Each milestone represents an incremental, logically isolated unit of work with clear verification gates and commit conventions.

---

## Milestone Roadmap Summary

| Milestone | Title | Focus Area | Status |
|:---:|:---|:---|:---:|
| **M0** | Planning & Repository Bootstrap | Git initialization, planning specs, README | **Current** |
| **M1** | Application Structure & Environment Scaffolding | Package manifest, module layout, CLI entrypoint | Planned |
| **M2** | Core Conversational Agent Loop & LLM Abstraction | ReAct agent loop, LiteLLM gateway, prompt template | Planned |
| **M3** | Consolidated Web Search Tool & Source Attribution | Tavily integration, citation parsing, deduplication | Planned |
| **M4** | Timestamped Conversation Message Persistence | DuckDB/SQLite persistence store, schema migrations | Planned |
| **M5** | Chronological Memory Retrieval | Temporal range queries, relative time resolution | Planned |
| **M6** | Cross-Session Historical Question Recall | Cross-session index, semantic/keyword recall | Planned |
| **M7** | Evidence-Grounded Response Generation | Grounding verifier, inline citation tags `[^n]` | Planned |
| **M8** | Search Orchestration & Streaming Optimization | Token streaming, async tool execution, latency tuning | Planned |
| **M9** | Temporal Memory Evaluation & Regression Suite | Automated evaluation runner, temporal test sets | Planned |
| **M10** | Security Hardening & Final Verification | Injection protection, test coverage, final documentation | Planned |

---

## Detailed Milestone Specifications

### Milestone 0: Planning & Repository Bootstrap (Current Phase)
- **Scope**:
  - Initialize independent Git repository on `main` branch.
  - Configure remote origin: `https://github.com/Vedant1521/minimi.git`.
  - Establish `.gitignore` and `README.md`.
  - Author planning documents: `plan.md`, `milestones.md`, `design.md`.
- **Deliverables**:
  - `README.md`
  - `.gitignore`
  - `plan.md`
  - `milestones.md`
  - `design.md`
- **Verification**:
  - Repository has clean working directory with correct remote origin.
  - Planning documents are internally consistent.
- **Suggested Commit**:
  - `docs: add project architecture and implementation roadmap`

---

### Milestone 1: Application Structure & Environment Scaffolding
- **Scope**:
  - Configure `pyproject.toml` with `uv` package management.
  - Create standard package structure under `minimi/`:
    - `minimi/__init__.py`
    - `minimi/cli.py`
    - `minimi/config.py`
  - Configure basic CLI interface (`argparse` or `typer` / `click`).
  - Establish `tests/` directory with `conftest.py`.
- **Deliverables**:
  - `pyproject.toml`
  - `minimi/__init__.py`
  - `minimi/cli.py`
  - `minimi/config.py`
  - `tests/conftest.py`
  - `tests/test_cli.py`
- **Verification**:
  - `uv sync` installs cleanly.
  - `uv run pytest tests/` executes and passes CLI smoke tests.
- **Suggested Commit**:
  - `feat: initialize independent application structure`

---

### Milestone 2: Core Conversational Agent Loop & LLM Abstraction
- **Scope**:
  - Implement `minimi/llm.py` supporting LiteLLM multi-provider gateway.
  - Implement `minimi/agent.py` conversation loop with state tracking.
  - Implement system prompt manager in `minimi/prompts.py`.
  - Provide fallback logic for offline/unconfigured environments.
- **Deliverables**:
  - `minimi/llm.py`
  - `minimi/agent.py`
  - `minimi/prompts.py`
  - `tests/test_agent.py`
- **Verification**:
  - Unit tests verify conversational turns, state updates, and mock LLM calls.
- **Suggested Commit**:
  - `feat: implement core conversational agent`

---

### Milestone 3: Consolidated Web Search Tool & Source Attribution
- **Scope**:
  - Implement `minimi/search.py` wrapping Tavily search.
  - Provide structured output: title, URL, raw snippet, normalized citation index.
  - Consolidate agent tool calling to seamlessly query search when needed.
  - Implement mock search fixtures for deterministic testing.
- **Deliverables**:
  - `minimi/search.py`
  - `minimi/tools.py`
  - `tests/test_search.py`
- **Verification**:
  - Unit tests verify search result extraction, error handling on empty/malformed results, and mock tool execution.
- **Suggested Commit**:
  - `feat: consolidate agent capabilities into web search tool`
  - `feat: integrate web search with source attribution`

---

### Milestone 4: Timestamped Conversation Message Persistence
- **Scope**:
  - Implement `minimi/storage.py` using DuckDB / SQLite.
  - Create database schemas for `conversations` and `messages`.
  - Ensure every message record stores an explicit ISO-8601 UTC timestamp and metadata.
  - Add query methods for session retrieval and message appending.
- **Deliverables**:
  - `minimi/storage.py`
  - `tests/test_storage.py`
- **Verification**:
  - Database round-trip tests confirm microsecond timestamp fidelity and index validity.
- **Suggested Commit**:
  - `feat: persist timestamped conversation messages`

---

### Milestone 5: Chronological Memory Retrieval
- **Scope**:
  - Implement `minimi/temporal.py` for parsing temporal expressions (e.g., "today", "yesterday", "within the last 2 hours").
  - Implement time-range query filters in `minimi/storage.py`.
  - Integrate chronological memory retrieval into the agent context builder.
- **Deliverables**:
  - `minimi/temporal.py`
  - `tests/test_temporal.py`
- **Verification**:
  - Tests verify accurate relative time window translation and chronological message ordering.
- **Suggested Commit**:
  - `feat: implement chronological memory retrieval`

---

### Milestone 6: Cross-Session Historical Question Recall
- **Scope**:
  - Implement cross-session question indexing across conversations.
  - Create search and ranking mechanism combining lexical matching with temporal recency.
  - Enable the agent to recall and surface questions and answers from earlier sessions when referenced by the user.
- **Deliverables**:
  - `minimi/recall.py`
  - `tests/test_recall.py`
- **Verification**:
  - Tests simulate multiple sessions and confirm the agent successfully retrieves questions from prior sessions.
- **Suggested Commit**:
  - `feat: add cross-session historical question recall`

---

### Milestone 7: Evidence-Grounded Response Generation
- **Scope**:
  - Implement strict grounding prompts preventing unsupported claims.
  - Implement `minimi/grounding.py` for source validation and formatting inline citations (`[^1]`).
  - Add verification helper ensuring every cited index corresponds to an actual retrieved search snippet.
- **Deliverables**:
  - `minimi/grounding.py`
  - `tests/test_grounding.py`
- **Verification**:
  - Tests verify that grounded answers preserve accurate source URLs and flag hallucinated citations.
- **Suggested Commit**:
  - `feat: improve evidence-grounded response generation`

---

### Milestone 8: Search Orchestration & Streaming Optimization
- **Scope**:
  - Optimize agent loop for asynchronous tool execution and low-latency token streaming.
  - Implement real-time token generator yielding both text tokens and structured citation events.
  - Profile and benchmark orchestration latency.
- **Deliverables**:
  - Streaming updates in `minimi/agent.py` and `minimi/cli.py`.
  - `tests/test_streaming.py`
- **Verification**:
  - Streaming generator tests verify event ordering and response completion.
- **Suggested Commit**:
  - `perf: optimize search orchestration and response streaming`

---

### Milestone 9: Temporal Memory Evaluation & Regression Suite
- **Scope**:
  - Create automated evaluation script `scripts/eval_temporal.py`.
  - Build evaluation dataset covering temporal queries, historical recall, and search attribution.
  - Integrate evaluation harness into test suite.
- **Deliverables**:
  - `scripts/eval_temporal.py`
  - `tests/data/eval_temporal_cases.json`
  - `tests/test_eval_runner.py`
- **Verification**:
  - Automated eval passes baseline threshold (>90% accuracy on temporal test cases).
- **Suggested Commit**:
  - `test: add temporal memory evaluation coverage`

---

### Milestone 10: Security Hardening & Final Verification
- **Scope**:
  - Add regression tests for search query sanitization, prompt injection defenses, and environment secret protection.
  - Verify zero credential leakage.
  - Polish documentation and verify complete end-to-end functionality.
- **Deliverables**:
  - `tests/test_security.py`
  - Updated `README.md` and user guides.
- **Verification**:
  - Full test suite passes: `uv run pytest tests/ -v`.
  - Clean linting with Ruff: `uv run ruff check .`.
- **Suggested Commit**:
  - `test: add search reliability and security regression tests`
