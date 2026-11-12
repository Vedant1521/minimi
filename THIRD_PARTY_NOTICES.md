# Third-Party Notices & Upstream Provenance

## Upstream Project & Attribution
Minimi's conceptual design was informed by the open-source project **Pravah**:
* **Repository**: https://github.com/jayshah5696/pravah
* **Original Author**: Jay Shah
* **Original License**: Apache License 2.0 (January 2004)

---

## Architectural Comparison & Component Categorization

### 1. Conceptual Patterns Inspired by Upstream
* **ReAct Agent Loop**: The prompt-driven function calling loop and conversational state tracking were inspired by architectural patterns in Pravah.
* **Tavily Search Integration**: Pravah's pattern of utilizing Tavily for web retrieval informed Minimi's live search integration.

### 2. Significant Modifications & Architectural Divergence
* **Runtime & Stack**: Migrated entirely from Python/uv/Streamlit to a production TypeScript application on Node.js and Next.js.
* **Single-Tool Enforcement**: Consolidated all agent capabilities into strictly one model-callable tool: `web_search`. Memory, database, and temporal operations were moved entirely to internal application services.
* **Embedded Relational Storage & FTS5**: Replaced session-level TF-IDF caching with persistent SQLite (`better-sqlite3`), Write-Ahead Logging (WAL), and FTS5 full-text indexing.
* **Timezone-Aware Temporal Engine**: Added deterministic calendar date and relative weekday parsing ("on Monday", "last Tuesday", "3 November") with canonical UTC ISO-8601 storage.
* **Cross-Session Question Recall**: Engineered cross-session recall linking user questions, assistant responses, extracted entities, and search evidence snapshots in single-query lookups.
* **Citation Verification**: Implemented strict grounding verification to match output citation tags against retrieved search snippets.
* **Real Incremental Streaming**: Implemented native Server-Sent Events (SSE) streaming for incremental token delivery and tool lifecycle status.

---

## License Notice
This project is licensed under the terms of the Apache License, Version 2.0.
A copy of the license is available at https://www.apache.org/licenses/LICENSE-2.0.
