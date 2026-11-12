import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { AgentOrchestrator } from "@/agent/orchestrator";
import { MemoryStore } from "@/memory/store";

describe("AgentOrchestrator", () => {
  let store: MemoryStore;
  let orchestrator: AgentOrchestrator;

  beforeEach(() => {
    store = new MemoryStore(":memory:");
    orchestrator = new AgentOrchestrator({ store });
  });

  afterEach(() => {
    store.close();
  });

  it("strictly registers only web_search in its callable tool registry", () => {
    const tools = orchestrator.getToolRegistry().getCallableTools();
    expect(tools.length).toBe(1);
    expect(tools[0].function.name).toBe("web_search");
  });

  it("internally resolves historical memory without invoking any LLM tool", () => {
    // Seed Monday conversation
    const mondayConv = store.createConversation("monday-session", "CRM Shortlist");
    store.saveMessage({
      conversation_id: mondayConv.id,
      role: "user",
      content: "Shortlist 5 CRM tools for a 20-person sales team",
      timestamp: "2026-11-09T10:00:00.000Z",
      entities: ["HubSpot", "Pipedrive", "Close", "Freshsales", "Zoho"],
    });

    store.saveMessage({
      conversation_id: mondayConv.id,
      role: "assistant",
      content: "1. HubSpot, 2. Pipedrive, 3. Close, 4. Freshsales, 5. Zoho",
      timestamp: "2026-11-09T10:01:00.000Z",
    });

    const userPrompt = "On Monday we shortlisted 5 CRM tools for a 20-person sales team. Has any of them changed pricing?";
    const memory = orchestrator.resolveInternalMemory(userPrompt, "UTC");

    expect(memory.retrieved).toBe(true);
    expect(memory.historicalContext).toContain("<historical_memory>");
    expect(memory.historicalContext).toContain("HubSpot");
    expect(memory.historicalContext).toContain("20-person sales team");
  });

  it("processes a conversation turn and persists messages to SQLite", async () => {
    const conv = store.createConversation("chat-1");
    const result = await orchestrator.processTurn(conv.id, "Hello Minimi!");

    expect(result.text).toBeDefined();
    expect(result.userMessage.content).toBe("Hello Minimi!");
    expect(result.assistantMessage.role).toBe("assistant");

    const messages = store.getMessages(conv.id);
    expect(messages.length).toBe(2);
    expect(messages[0].role).toBe("user");
    expect(messages[1].role).toBe("assistant");
  });

  it("streams token events during turn execution", async () => {
    const conv = store.createConversation("stream-test");
    const events: Array<{ type: string; data?: unknown }> = [];

    for await (const event of orchestrator.processTurnStream(conv.id, "Hello!")) {
      events.push(event);
    }

    const types = events.map((e) => e.type);
    expect(types).toContain("status");
    expect(types).toContain("token");
    expect(types).toContain("done");
  });
});
