# Master Implementation Plan: Minimi

## 1. Project Overview & Motivation

**Minimi** is a streamlined, search-grounded conversational agent featuring chronological memory retrieval and cross-session question recall. 

While reference projects like *Pravah* explore complex user interfaces, file uploads, and auxiliary calculation tools, Minimi refines conversational agent engineering down to its core value proposition:
1. Fast, reliable conversational orchestration.
2. High-precision web search with structured source attribution.
3. Timestamp-indexed conversation persistence.
4. Temporal querying and chronological memory slicing.
5. Cross-session recall of historical user questions and answers.
6. Rigorous evidence-grounding to eliminate hallucinations.

---

## 2. Comparative Analysis: Minimi vs. Pravah Reference

| Dimension | Pravah Reference | Minimi Implementation | Rationale |
|:---|:---|:---|:---|
| **Primary Interface** | Streamlit Web App (`app.py`) | Decoupled Core Agent + Clean CLI REPL | Maximizes testability, performance, and embedding flexibility. |
| **Tool Suite** | 8+ tools (`web_search`, `gemini_search`, `fetch_page`, `calculate`, `uploads`, etc.) | Consolidated `web_search` with built-in attribution and grounding | Reduces agent action-space confusion, improves latency, prevents tool hallucination. |
| **Document Ingestion** | Heavy document parsing (`markitdown`, pdf, docx, pptx) | Focused web retrieval + memory snippet cache | Zero bloat, instant startup, deterministic behavior. |
| **Memory System** | Session-level TF-IDF keyword search over fetched pages | Persistent temporal store with chronological query resolution & cross-session recall | Enables temporal reasoning ("what did I ask yesterday?") and multi-session knowledge continuity. |
| **Evidence Grounding** | Ad-hoc prompt instructions | Verified citation mapper linking model statements to retrieved source snippet indices | Ensures strict verifiable provenance for all factual claims. |
| **Package Management**| `uv` with Streamlit dependencies | `uv` with minimal, modern agent dependencies | Faster CI, smaller footprint, clean isolation. |

---

## 3. Technology Stack & Dependencies

- **Language & Runtime**: Python 3.11+
- **Package Manager**: `uv`
- **Model Orchestration**: `LiteLLM` (multi-provider support: OpenAI, Gemini, Anthropic, Groq, local Ollama)
- **Search Provider**: `Tavily Search API`
- **Data Persistence**: `DuckDB` / `SQLite` with indexed UTC timestamps
- **Testing & Verification**: `pytest`, `pytest-mock`, `pytest-asyncio`
- **Code Quality & Formatting**: `ruff`

---

## 4. Phased Execution Roadmap

Minimi will be executed across five distinct phases, divided into 11 discrete milestones (M0 through M10):

### Phase 1: Planning & Foundation (Milestone 0 — Current)
- Verify working directory and independent Git repository setup.
- Configure remote `origin` to `https://github.com/Vedant1521/minimi.git`.
- Establish documentation baseline (`plan.md`, `milestones.md`, `design.md`, `README.md`, `.gitignore`).
- Record initial local commit and prepare for user push approval.

### Phase 2: Core Agent & Search Tools (Milestones 1 – 3)
- Scaffold package structure (`minimi/`) and environment configs via `pyproject.toml`.
- Implement CLI entry point and configuration loading.
- Build LLM provider gateway and conversational agent loop.
- Implement consolidated web search tool with structured citation metadata.

### Phase 3: Temporal Memory & Cross-Session Recall (Milestones 4 – 6)
- Build database storage schema with microsecond timestamp tracking.
- Implement chronological memory retrieval and relative time phrase resolution (e.g., "today", "yesterday", "last week").
- Implement cross-session question and answer indexing, enabling historical query recall across session boundaries.

### Phase 4: Grounding & Performance Optimization (Milestones 7 – 8)
- Implement evidence-grounding engine with inline citation tags (`[^1]`).
- Add citation verification guardrails to detect unsupported assertions.
- Optimize agent execution loop for real-time token streaming and asynchronous tool execution.

### Phase 5: Evaluation, Security & Hardening (Milestones 9 – 10)
- Develop temporal memory evaluation suite (`scripts/eval_temporal.py`).
- Write comprehensive regression tests for temporal queries, search reliability, and injection prevention.
- Finalize documentation, run complete linting and test passes, and prepare production-ready codebase.

---

## 5. Risk Assessment & Mitigation

| Risk | Impact | Mitigation Strategy |
|:---|:---|:---|
| **Search API Rate Limits / Failures** | Agent fails to retrieve external information | Implement exponential backoff retry and graceful fallback to parametric knowledge with clear disclaimer. |
| **Temporal Query Ambiguity** | Incorrect time windows retrieved | Anchor all queries relative to current UTC time; provide explicit fallbacks if relative time resolution is low confidence. |
| **Citation Hallucination** | Agent invents sources not present in retrieved context | Verification pass checks that every citation index corresponds to an actual retrieved snippet in memory. |
| **Cross-Session Privacy / Isolation** | Inadvertent leakage across user sessions | Namespace session queries; require explicit opt-in for cross-session global recall queries. |

---

## 6. Git Governance & Push Protocol

1. **Incremental Atomic Commits**:
   - Commits are made at logical milestone boundaries upon successful verification of relevant tests.
   - Conventional Commits standard will be enforced (`feat:`, `fix:`, `docs:`, `test:`, `perf:`).
2. **Strict Zero-Push Without Approval**:
   - No remote push operation (`git push`, `git push -u origin main`, etc.) will ever be executed without prior, explicit user approval.
   - Before requesting approval, a full pre-push summary (branch, remote URL, commit log, diff summary, and test results) will be presented.
