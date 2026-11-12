import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { MemoryStore } from "@/memory/store";

describe("MemoryStore (SQLite Persistent Engine)", () => {
  let store: MemoryStore;

  beforeEach(() => {
    store = new MemoryStore(":memory:");
  });

  afterEach(() => {
    store.close();
  });

  it("creates and retrieves a conversation", () => {
    const conv = store.createConversation("session-1", "Test Conversation");
    expect(conv.id).toBe("session-1");
    expect(conv.title).toBe("Test Conversation");

    const fetched = store.getConversation("session-1");
    expect(fetched).not.toBeNull();
    expect(fetched?.title).toBe("Test Conversation");
  });

  it("saves and retrieves timestamped messages", () => {
    const conv = store.createConversation("session-1");
    const msg = store.saveMessage({
      conversation_id: conv.id,
      role: "user",
      content: "Shortlist 5 CRM tools for a 20-person sales team",
      timestamp: "2026-11-09T10:00:00.000Z",
      timezone: "UTC",
      entities: ["HubSpot", "Pipedrive", "Salesforce", "Zoho", "Freshsales"],
    });

    expect(msg.id).toBeDefined();
    expect(msg.role).toBe("user");

    const messages = store.getMessages(conv.id);
    expect(messages.length).toBe(1);
    expect(messages[0].content).toContain("CRM tools");
    expect(JSON.parse(messages[0].entities || "[]")).toEqual([
      "HubSpot",
      "Pipedrive",
      "Salesforce",
      "Zoho",
      "Freshsales",
    ]);
  });

  it("saves and links search evidence snapshots", () => {
    const conv = store.createConversation("session-1");
    const msg = store.saveMessage({
      conversation_id: conv.id,
      role: "assistant",
      content: "Here is the shortlist of CRM tools.",
      timestamp: "2026-11-09T10:01:00.000Z",
    });

    store.saveSearchEvidence({
      message_id: msg.id,
      query: "HubSpot pricing 2026",
      url: "https://www.hubspot.com/pricing",
      title: "HubSpot Official Pricing",
      snippet: "HubSpot CRM starts at $20/month per user.",
    });

    const evidence = store.getSearchEvidenceForMessage(msg.id);
    expect(evidence.length).toBe(1);
    expect(evidence[0].url).toBe("https://www.hubspot.com/pricing");
    expect(evidence[0].title).toBe("HubSpot Official Pricing");
  });

  it("filters messages deterministically by UTC date range", () => {
    const conv = store.createConversation("session-1");
    store.saveMessage({
      conversation_id: conv.id,
      role: "user",
      content: "Sunday Question",
      timestamp: "2026-11-08T15:00:00.000Z",
    });
    store.saveMessage({
      conversation_id: conv.id,
      role: "user",
      content: "Monday Morning Question",
      timestamp: "2026-11-09T09:30:00.000Z",
    });
    store.saveMessage({
      conversation_id: conv.id,
      role: "user",
      content: "Monday Afternoon Question",
      timestamp: "2026-11-09T14:15:00.000Z",
    });
    store.saveMessage({
      conversation_id: conv.id,
      role: "user",
      content: "Tuesday Question",
      timestamp: "2026-11-10T11:00:00.000Z",
    });

    // Query strictly for Monday (2026-11-09T00:00:00Z to 2026-11-09T23:59:59Z)
    const mondayMessages = store.findMessagesByDateRange(
      "2026-11-09T00:00:00.000Z",
      "2026-11-09T23:59:59.999Z"
    );

    expect(mondayMessages.length).toBe(2);
    expect(mondayMessages[0].content).toBe("Monday Morning Question");
    expect(mondayMessages[1].content).toBe("Monday Afternoon Question");
  });

  it("performs FTS5 full-text search across cross-session messages", () => {
    const conv1 = store.createConversation("session-1", "CRM Discussion");
    const conv2 = store.createConversation("session-2", "Postgres Discussion");

    store.saveMessage({
      conversation_id: conv1.id,
      role: "user",
      content: "What CRM tools are best for small teams?",
    });

    store.saveMessage({
      conversation_id: conv2.id,
      role: "user",
      content: "What are reliable Postgres hosting providers?",
      entities: ["Supabase", "Neon", "RDS"],
    });

    const crmResults = store.searchMessagesFTS("CRM");
    expect(crmResults.length).toBe(1);
    expect(crmResults[0].conversation_title).toBe("CRM Discussion");

    const postgresResults = store.searchMessagesFTS("Postgres");
    expect(postgresResults.length).toBe(1);
    expect(postgresResults[0].conversation_title).toBe("Postgres Discussion");

    const entityResults = store.searchMessagesFTS("Supabase");
    expect(entityResults.length).toBe(1);
  });
});
