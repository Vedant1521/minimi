# Minimi

> High-performance, evidence-grounded conversational agent featuring a strict single-tool web search architecture, timezone-aware temporal memory, and cross-session question recall.

Built with **TypeScript** on **Node.js**, Minimi combines live web search with persistent relational conversation memory. It solves complex comparative queries across past discussions (e.g. *"On Monday we shortlisted 5 CRM tools... has any of them changed pricing since?"*) without hallucinating past context or exposing memory as an auxiliary agent tool.

---

## 1. Problem Statement

Most modern conversational agents suffer from two recurring structural failure modes:
1. **Tool Over-proliferation**: Exposing separate tools for memory retrieval, database lookups, and web search confuses the agent's action space, increases multi-hop latency, and causes tool hallucination.
2. **Temporal Amnesia**: Standard chat systems treat each session as an isolated silo. When asked about past decisions or previous discussions ("What did I ask you on 3 November?", "Did any pricing change since last Tuesday?"), they fail to recover the exact historical baseline or hallucinate past events.

---

## 2. Why Minimi Is Interesting

* **Strict Single Model-Callable Tool**: Exposes **strictly one** model-callable tool: `web_search`. Memory retrieval, database queries, and context assembly run as internal application services prior to synthesis.
* **Deterministic Temporal Resolution**: Resolves relative phrases ("on Monday", "last Tuesday", "yesterday") and calendar dates ("3 November") into exact UTC ISO-8601 windows using the user's configured IANA timezone.
* **Cross-Session Knowledge Continuity**: Employs an embedded SQLite database (`better-sqlite3`) with Write-Ahead Logging (WAL) and FTS5 full-text indexing to retrieve historical user questions, assistant answers, and evidence snapshots across session boundaries in a single query (zero N+1 scans).
* **Verifiable Grounding & Citation Validation**: All search results are deduplicated and assigned citation indices (`[1]`, `[2]`). An inline verification engine ensures the model cannot fabricate citation markers.
* **True Incremental Streaming**: End-to-end token streaming over Server-Sent Events (SSE) with live tool status badges (`Searching the web: "..."`) and interactive citation cards.

---

## 3. Key Features

* **Interactive Web Chat Interface**: Clean, responsive browser chat built with Next.js and Tailwind CSS.
* **Session Resumption & Switching**: Instant switching across past conversations with full historical context.
* **Headless CLI Mode**: Terminal REPL and single-query execution for developer workflows.
* **Zero Native Build Dependencies**: Runs cleanly on standard Node.js without requiring external vector databases or native compilation tools.
* **Comprehensive Benchmark Suite**: Automated evaluation runner validating critical take-home scenarios with 100% pass rate.

---

## 4. Architecture Overview

```
                          ┌────────────────────────┐
                          │   Browser Web UI /     │
                          │   Headless CLI REPL    │
                          └───────────┬────────────┘
                                      │  (SSE Stream)
                                      ▼
                       ┌─────────────────────────────┐
                       │  Next.js / Node.js Server   │
                       └──────────────┬──────────────┘
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            │                                                   │
            ▼                                                   ▼
┌───────────────────────┐                           ┌───────────────────────┐
│ Internal App Services │                           │   Agent Orchestrator  │
│ (Non-Callable)        │                           │   (ReAct Loop)        │
├───────────────────────┤                           └───────────┬───────────┘
│ - TemporalEngine      │                                       │
│   (IANA Timezones)    │                                       │ (Strictly 1 Tool)
│ - CrossSessionRecall  │                                       ▼
│   (FTS5 Search)       │                           ┌───────────────────────┐
│ - CitationVerifier    │                           │ Model-Callable Tool   │
│   (Attribution)       │                           │ {"web_search"}        │
└───────────┬───────────┘                           └───────────┬───────────┘
            │                                                   │
            ▼                                                   ▼
┌───────────────────────┐                           ┌───────────────────────┐
│ Embedded SQLite DB    │                           │ Tavily Live Search    │
│ (better-sqlite3, WAL) │                           │ API Engine            │
└───────────────────────┘                           └───────────────────────┘
```

### The Strict Single-Tool Boundary
The model tool registry contains strictly:
```json
[
  {
    "type": "function",
    "function": {
      "name": "web_search",
      "description": "Search the live web for current facts, recent events, product announcements, pricing, documentation, and real-time updates.",
      "parameters": {
        "type": "object",
        "properties": {
          "query": { "type": "string", "description": "Specific search query" },
          "days": { "type": "number", "description": "Optional recency filter in days" }
        },
        "required": ["query"]
      }
    }
  }
]
```
Memory retrieval, storage operations, and date parsing operate purely as application services and are **never** exposed as callable tools to the model.

---

## 5. Technology Stack

* **Runtime**: Node.js >= 20.0.0
* **Language**: TypeScript (strict type checking enabled)
* **Package Manager**: standard `npm` (tracked with `package-lock.json`)
* **Framework**: Next.js 14 (App Router) + React 18 + Tailwind CSS
* **Database**: `better-sqlite3` (WAL mode + FTS5 full-text indexing)
* **LLM Client**: `openai` SDK (compatible with OpenAI, Groq, Ollama, OpenRouter)
* **Search API**: Tavily Search Engine REST integration
* **Testing & Evaluation**: `vitest`, `tsx`

---

## 6. Prerequisites

* **Node.js**: Version 20.x or 22.x installed ([Download Node.js](https://nodejs.org/)).
* **npm**: Version 10+ (bundled with Node.js).
* **API Keys**:
  * An OpenAI-compatible API key (`OPENAI_API_KEY`) or Groq key.
  * A Tavily Search API key (`TVLY_API_KEY`) for live web search ([tavily.com](https://tavily.com)).

---

## 7. Installation & Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/Vedant1521/minimi.git
cd minimi
```

### 2. Install dependencies
```bash
npm install
```

### 3. Configure the environment
Create your local `.env` file from the provided template:

**PowerShell (Windows):**
```powershell
Copy-Item .env.example .env
```

**Bash / macOS / Linux:**
```bash
cp .env.example .env
```

Edit `.env` and supply your credentials:
```env
OPENAI_API_KEY=your_openai_or_groq_api_key_here
TVLY_API_KEY=your_tavily_api_key_here
MINIMI_MODEL=gpt-4o-mini
MINIMI_TIMEZONE=UTC
```

### 4. Start the interactive application
```bash
npm run dev
```
Open your browser at `http://localhost:3000` to interact with Minimi.

---

## 8. CLI & Headless Usage

Run single queries directly from your terminal:
```bash
npm run cli -- --query "What are the latest developments in AI inference?"
```

Resume a specific conversation session by ID:
```bash
npm run cli -- --session-id "YOUR_SESSION_UUID"
```

Start an interactive terminal REPL:
```bash
npm run cli
```

---

## 9. Solving the Target Assignment Scenarios

### Scenario A — CRM Shortlist on Monday & Subsequent Changes
* **User Prompt**: *"On Monday we shortlisted 5 CRM tools for a 20-person sales team. Has any of them changed pricing or shipped something big since?"*
* **How Minimi Solves It**:
  1. `TemporalEngine` resolves "Monday" to its exact date window in the configured timezone.
  2. `CrossSessionRecallEngine` fetches the Monday dialogue, recovering the 5 CRM tools (HubSpot, Pipedrive, Close, Freshsales, Zoho CRM), the 20-person team constraint, and baseline pricing.
  3. The model receives this baseline in its prompt and executes `web_search` for current pricing and product updates.
  4. The model provides a verified comparison with citations without asking the user to repeat the shortlist.

### Scenario B — Historical Question on 3 November & Current Validity
* **User Prompt**: *"What did I ask you on 3 November? Is your answer still correct today?"*
* **How Minimi Solves It**:
  1. `TemporalEngine` resolves "3 November" to the calendar boundary.
  2. `CrossSessionRecallEngine` recovers the user's historical question, previous assistant answer, and original source evidence.
  3. The model queries current web status via `web_search` to verify whether the previous recommendation remains valid.
  4. The response explains what remains accurate and what has evolved with fresh citations.

### Scenario C — Previous Tuesday's Postgres Hosting Discussion
* **User Prompt**: *"Last Tuesday I asked you about Postgres hosting. Has any pricing changed since then?"*
* **How Minimi Solves It**:
  1. `TemporalEngine` resolves "last Tuesday" relative to current time.
  2. `CrossSessionRecallEngine` retrieves the previous Tuesday's discussion and provider shortlist (e.g. Supabase, Neon).
  3. The model triggers `web_search` to inspect current pricing tiers.
  4. The response highlights verified pricing status with source citations.

---

## 10. Automated Testing & Evaluation

### Run Unit & Integration Tests
```bash
npm test
```
Executes all 34 test cases across tool boundary enforcement, temporal parsing, database persistence, cross-session recall, citation verification, and incremental SSE streaming.

### Run Scenario Benchmark
```bash
npm run eval
```
Executes the automated scenario runner validating Scenarios A, B, and C against persistent storage with 100% pass rate.

### Run TypeScript Typecheck
```bash
npm run typecheck
```

### Production Build
```bash
npm run build
```

---

## 11. Project Structure

```
minimi/
├── .github/
│   └── workflows/
│       └── ci.yml               # Multi-OS CI workflow (Ubuntu, Windows)
├── scripts/
│   └── eval-scenarios.ts        # Automated evaluation runner for Scenarios A, B, C
├── src/
│   ├── app/                     # Next.js App Router
│   │   ├── api/
│   │   │   ├── chat/route.ts    # SSE streaming chat endpoint
│   │   │   └── sessions/        # Session listing & message history endpoints
│   │   ├── globals.css          # Tailwind CSS styling
│   │   ├── layout.tsx           # Application shell
│   │   └── page.tsx             # Interactive chat interface & citation cards
│   ├── agent/                   # Conversational agent core
│   │   ├── orchestrator.ts      # ReAct loop, tool dispatch, memory injection
│   │   └── prompts.ts           # System prompt & temporal context templates
│   ├── tools/                   # Model-callable tool registry (STRICTLY ONE)
│   │   ├── index.ts             # Tool registry exposing {"web_search"}
│   │   └── web-search.ts        # Tavily search wrapper & citation indexer
│   ├── memory/                  # Internal memory services (non-callable)
│   │   ├── store.ts             # SQLite storage engine (better-sqlite3 + FTS5)
│   │   ├── temporal.ts          # Timezone-aware date parsing & UTC boundary math
│   │   └── recall.ts            # Cross-session recall & entity retrieval
│   ├── grounding/               # Attribution & verification
│   │   └── verifier.ts          # Citation validation & hallucination prevention
│   ├── cli.ts                   # Headless CLI entrypoint
│   └── config.ts                # Environment configuration loader
├── tests/
│   ├── tool-boundary.test.ts    # Strict enforcement: exactly 1 tool {"web_search"}
│   ├── temporal.test.ts         # Timezone, date parsing, midnight boundary tests
│   ├── store.test.ts            # SQLite schema, WAL mode, FTS5 tests
│   ├── recall.test.ts           # Cross-session recall tests
│   ├── grounding.test.ts        # Citation verification tests
│   ├── streaming.test.ts        # Incremental SSE streaming tests
│   └── scenarios.test.ts        # Verification of Scenarios A, B, and C
├── .env.example                 # Environment configuration template
├── .gitignore                   # Ignore node_modules, .env, data/*.db, .next
├── DESIGN.md                    # Exact 1-page system design document
├── THIRD_PARTY_NOTICES.md       # Upstream provenance & attribution
├── package.json                 # npm manifest
├── tsconfig.json                # TypeScript configuration
└── README.md                    # Comprehensive onboarding guide
```

---

## 12. Design Documentation

Detailed technical architecture, message lifecycles, and trade-off rationales are documented in [`DESIGN.md`](file:///C:/Projects/minimi/assignment/DESIGN.md).

---

## 13. Limitations

* **Search API Quotas**: Live search depends on external Tavily API availability and rate limits.
* **JavaScript DOM Execution**: The search tool processes structured web snippets provided by Tavily; it does not execute client-side JavaScript on target websites.
* **Timezone Scope**: Relative date phrases resolve against the configured `MINIMI_TIMEZONE` or the browser's detected local timezone.

---

## 14. Upstream Provenance & Licensing

* **Upstream Provenance**: Architectural patterns and search concepts were inspired by the open-source project **Pravah** by Jay Shah. Full details and modifications are documented in [`THIRD_PARTY_NOTICES.md`](file:///C:/Projects/minimi/assignment/THIRD_PARTY_NOTICES.md).
* **License**: Licensed under the Apache License, Version 2.0.
