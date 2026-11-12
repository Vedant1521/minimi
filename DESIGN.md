# System Design: Minimi

## 1. System Overview & Core Message Lifecycle
Minimi is a high-performance conversational agent built with TypeScript on Node.js. It grounds its dialogue in live web evidence while maintaining persistent chronological memory and cross-session question recall, strictly exposing **exactly one model-callable tool: `web_search`**.

The end-to-end turn lifecycle executes deterministically:
1. **Turn Ingestion & Temporal Resolution**: The user prompt is ingested alongside the active conversation ID and user timezone. `TemporalEngine` parses explicit dates ("3 November") and relative expressions ("on Monday", "last Tuesday") in the user's IANA timezone, calculating exact start/end-of-day boundaries and converting them to canonical UTC ISO-8601 windows.
2. **Internal Memory Retrieval**: `CrossSessionRecallEngine` queries embedded SQLite (`better-sqlite3`) using indexed timestamp ranges and FTS5 full-text search. It retrieves matching dialogue turns, historical assistant answers, extracted entities, and past evidence snapshots without dispatching any model tools.
3. **Context Construction & Prompt Grounding**: System instructions anchor the canonical UTC time, user timezone, and format retrieved records into a structured `<historical_memory>` block. The historical records serve as the factual baseline for comparative queries.
4. **ReAct Reasoning & Single Tool Execution**: The model receives the context and strictly one callable tool schema: `web_search`. If fresh facts, current pricing, or verification of past answers are required, the model invokes `web_search(query)`. The tool deduplicates results, extracts clean snippets, and formats numbered citation indices (`[1]`, `[2]`).
5. **Attribution & Streaming Persistence**: `CitationVerifier` validates model citation anchors against retrieved snippets, stripping hallucinated references. Tokens, tool status badges, and source cards stream to the client via Server-Sent Events (SSE). The completed turn, citations, and search evidence snapshots are persisted to SQLite.

## 2. Why the Single-Tool Architecture Works
Exposing memory operations as model tools introduces action-space confusion, tool hallucination, and multi-hop latency penalties. In Minimi, memory is an **internal application service executed deterministically prior to model synthesis**. The model focuses entirely on reasoning over grounded historical records and using `web_search` when fresh external facts are needed. An automated test explicitly enforces that the model-facing tool registry strictly equals `{"web_search"}`.

## 3. Temporal Recall & Information Comparison
When a user asks: *"On Monday we shortlisted 5 CRM tools for a 20-person sales team. Has any of them changed pricing or shipped something big since?"*:
- `TemporalEngine` resolves "Monday" to its exact date window.
- `CrossSessionRecallEngine` recovers the Monday dialogue, identifying the 5 CRM tools, the 20-person constraint, and baseline pricing from stored records.
- The model receives this baseline in prompt context and uses `web_search` to query current vendor status.
- The response contrasts the historical baseline with current web evidence, highlighting verified differences with fresh citations without asking the user to repeat past context.

## 4. Key Architectural Decisions & Rejected Alternatives
- **Node.js & Next.js vs. Streamlit/Python**: Adopted Next.js App Router for single-command zero-friction evaluation (`npm run dev`), native Web Streams for true SSE token streaming, and an integrated browser UI with session switching.
- **SQLite (better-sqlite3) + FTS5 vs. Vector Databases**: Dedicated vector stores introduce deployment friction, cold starts, and non-deterministic semantic drift. SQLite with Write-Ahead Logging (`WAL`), B-tree indexes on `(timestamp, conversation_id, role)`, and FTS5 yields sub-2ms lookups, zero configuration, and deterministic chronological filtering.
- **Deterministic Timezone Mapping vs. LLM Date Guessing**: LLMs fail at boundary arithmetic across timezones. Minimi computes local day boundaries using `Intl.DateTimeFormat` and normalizes to UTC storage.

## 5. Performance & Accuracy Trade-offs
- **Search Latency vs. Recency**: Single-call search consolidation keeps end-to-end response times under 1.5s while avoiding redundant API queries.
- **Strict Verification vs. Open Generation**: `CitationVerifier` strips unverified citation tags to eliminate phantom sourcing, prioritizing verifiable provenance over decorative citations.

## 6. What Would Be Done With Another Week
- Implement speculative parallel search queries across multi-entity shortlists.
- Add headless web-page extraction for deeper DOM inspection beyond API snippets.
- Add client-side dark/light theme persistence and conversation export (JSON/Markdown).
