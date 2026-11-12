import { MemoryStore, MessageRecord, SearchEvidenceRecord } from "./store";
import { TemporalRange } from "./temporal";

export interface HistoricalTurn {
  conversationId: string;
  conversationTitle: string;
  userMessage: MessageRecord;
  assistantMessage?: MessageRecord;
  evidence: SearchEvidenceRecord[];
  entities: string[];
}

export interface HistoricalRecallResult {
  turns: HistoricalTurn[];
  source: "temporal" | "fts" | "hybrid" | "none";
  temporalRange?: TemporalRange;
}

export class CrossSessionRecallEngine {
  private store: MemoryStore;

  constructor(store: MemoryStore) {
    this.store = store;
  }

  /**
   * Retrieves historical conversation turns within a specific temporal window.
   */
  public recallByTemporalWindow(
    range: TemporalRange,
    topicFilter?: string
  ): HistoricalRecallResult {
    const messages = this.store.findMessagesByDateRange(range.startDateUtc, range.endDateUtc);

    if (messages.length === 0) {
      return { turns: [], source: "temporal", temporalRange: range };
    }

    const turns = this.groupMessagesIntoTurns(messages, topicFilter);
    return {
      turns,
      source: "temporal",
      temporalRange: range,
    };
  }

  /**
   * Retrieves historical conversation turns across any past session matching query keywords/entities.
   */
  public recallByTopic(query: string, limit: number = 5): HistoricalRecallResult {
    const ftsResults = this.store.searchMessagesFTS(query, { limit: limit * 2 });

    if (ftsResults.length === 0) {
      return { turns: [], source: "fts" };
    }

    // Collect all matched messages and fetch their conversation turns
    const turns: HistoricalTurn[] = [];
    const seenTurnKeys = new Set<string>();

    for (const msg of ftsResults) {
      const convId = msg.conversation_id;
      const conv = this.store.getConversation(convId);
      const convTitle = conv?.title || msg.conversation_title || `Session ${convId.slice(0, 8)}`;

      // Fetch adjacent context around this message
      const allConvMessages = this.store.getMessages(convId);
      const msgIndex = allConvMessages.findIndex((m) => m.id === msg.id);

      if (msgIndex === -1) continue;

      let userMsg: MessageRecord;
      let assistantMsg: MessageRecord | undefined;

      if (msg.role === "user") {
        userMsg = msg;
        const nextMsg = allConvMessages[msgIndex + 1];
        if (nextMsg && nextMsg.role === "assistant") {
          assistantMsg = nextMsg;
        }
      } else if (msg.role === "assistant") {
        assistantMsg = msg;
        const prevMsg = allConvMessages[msgIndex - 1];
        if (prevMsg && prevMsg.role === "user") {
          userMsg = prevMsg;
        } else {
          continue;
        }
      } else {
        continue;
      }

      const turnKey = `${convId}:${userMsg.id}`;
      if (seenTurnKeys.has(turnKey)) continue;
      seenTurnKeys.add(turnKey);

      // Fetch linked evidence
      const evidence = assistantMsg ? this.store.getSearchEvidenceForMessage(assistantMsg.id) : [];

      let entities: string[] = [];
      if (userMsg.entities) {
        try { entities.push(...JSON.parse(userMsg.entities)); } catch { /* ignore */ }
      }
      if (assistantMsg?.entities) {
        try { entities.push(...JSON.parse(assistantMsg.entities)); } catch { /* ignore */ }
      }

      turns.push({
        conversationId: convId,
        conversationTitle: convTitle,
        userMessage: userMsg,
        assistantMessage: assistantMsg,
        evidence,
        entities: Array.from(new Set(entities)),
      });

      if (turns.length >= limit) break;
    }

    return {
      turns,
      source: "fts",
    };
  }

  /**
   * Internal helper to pair chronological messages into turns with conversation context and evidence.
   */
  private groupMessagesIntoTurns(messages: MessageRecord[], topicFilter?: string): HistoricalTurn[] {
    const turns: HistoricalTurn[] = [];

    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i];
      if (msg.role === "user") {
        const nextMsg = messages[i + 1];
        const assistantMsg = (nextMsg && nextMsg.role === "assistant" && nextMsg.conversation_id === msg.conversation_id)
          ? nextMsg
          : undefined;

        // If topic filter is provided, check if either user or assistant mentions it
        if (topicFilter) {
          const lowerFilter = topicFilter.toLowerCase();
          const matchesUser = msg.content.toLowerCase().includes(lowerFilter);
          const matchesAssistant = assistantMsg?.content.toLowerCase().includes(lowerFilter) || false;
          const matchesEntities = (msg.entities?.toLowerCase().includes(lowerFilter) || false) ||
                                  (assistantMsg?.entities?.toLowerCase().includes(lowerFilter) || false);

          if (!matchesUser && !matchesAssistant && !matchesEntities) {
            continue;
          }
        }

        const conv = this.store.getConversation(msg.conversation_id);
        const convTitle = conv?.title || `Session ${msg.conversation_id.slice(0, 8)}`;
        const evidence = assistantMsg ? this.store.getSearchEvidenceForMessage(assistantMsg.id) : [];

        let entities: string[] = [];
        if (msg.entities) {
          try { entities.push(...JSON.parse(msg.entities)); } catch { /* ignore */ }
        }
        if (assistantMsg?.entities) {
          try { entities.push(...JSON.parse(assistantMsg.entities)); } catch { /* ignore */ }
        }

        turns.push({
          conversationId: msg.conversation_id,
          conversationTitle: convTitle,
          userMessage: msg,
          assistantMessage: assistantMsg,
          evidence,
          entities: Array.from(new Set(entities)),
        });
      }
    }

    return turns;
  }

  /**
   * Formats retrieved historical turns into a structured XML block for injection into the LLM context.
   */
  public formatHistoricalContext(result: HistoricalRecallResult): string {
    if (result.turns.length === 0) {
      return "";
    }

    const lines: string[] = [];
    lines.push("<historical_memory>");
    lines.push("The following verifiable records were retrieved from past conversations:");

    for (const [idx, turn] of result.turns.entries()) {
      lines.push(`\n--- Record #${idx + 1} [Session: "${turn.conversationTitle}" (${turn.conversationId})] ---`);
      lines.push(`Timestamp (UTC): ${turn.userMessage.timestamp}`);
      lines.push(`User Question: ${turn.userMessage.content}`);

      if (turn.assistantMessage) {
        lines.push(`Assistant Answer: ${turn.assistantMessage.content}`);
      }

      if (turn.entities.length > 0) {
        lines.push(`Identified Entities: ${turn.entities.join(", ")}`);
      }

      if (turn.evidence.length > 0) {
        lines.push("Historical Sources & Evidence:");
        for (const ev of turn.evidence) {
          lines.push(`  - [${ev.title}] (${ev.url}): "${ev.snippet}"`);
        }
      }
    }

    lines.push("\n</historical_memory>");
    return lines.join("\n");
  }
}
