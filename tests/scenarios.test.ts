import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { MemoryStore } from "@/memory/store";
import { AgentOrchestrator } from "@/agent/orchestrator";
import { WebSearchService } from "@/tools/web-search";
import { ToolRegistry } from "@/tools/index";

describe("Critical Assignment Scenarios (A, B, C)", () => {
  let store: MemoryStore;
  let orchestrator: AgentOrchestrator;

  beforeEach(() => {
    store = new MemoryStore(":memory:");

    const mockSearch = new WebSearchService();
    mockSearch.search = async (query: string) => {
      const q = query.toLowerCase();
      if (q.includes("crm") || q.includes("hubspot")) {
        return {
          query,
          results: [
            {
              index: 1,
              title: "HubSpot Pricing & Plans 2026",
              url: "https://hubspot.com/pricing",
              snippet: "HubSpot Starter is $20/month per seat.",
            },
          ],
        };
      }
      if (q.includes("rust") || q.includes("axum")) {
        return {
          query,
          results: [
            {
              index: 1,
              title: "Rust Web Ecosystem 2026",
              url: "https://tokio.rs/blog/2026-rust-web",
              snippet: "Axum remains the leading Rust web framework.",
            },
          ],
        };
      }
      return { query, results: [] };
    };

    const toolRegistry = new ToolRegistry(mockSearch);
    orchestrator = new AgentOrchestrator({ store, toolRegistry });

    // Seed historical conversations
    const mondayConv = store.createConversation("sess-monday", "Sales CRM Shortlist");
    store.saveMessage({
      conversation_id: mondayConv.id,
      role: "user",
      content: "Shortlist 5 CRM tools for a 20-person sales team",
      timestamp: "2026-11-09T10:00:00.000Z",
      entities: ["HubSpot", "Pipedrive", "Close", "Freshsales", "Zoho CRM"],
    });
    store.saveMessage({
      conversation_id: mondayConv.id,
      role: "assistant",
      content: "Here are 5 CRM tools: 1. HubSpot ($20), 2. Pipedrive ($14), 3. Close ($49), 4. Freshsales ($15), 5. Zoho CRM ($14).",
      timestamp: "2026-11-09T10:01:00.000Z",
    });

    const nov3Conv = store.createConversation("sess-nov3", "Rust Web Frameworks");
    store.saveMessage({
      conversation_id: nov3Conv.id,
      role: "user",
      content: "What is the best Rust web framework in 2026?",
      timestamp: "2026-11-03T14:30:00.000Z",
    });
    store.saveMessage({
      conversation_id: nov3Conv.id,
      role: "assistant",
      content: "Axum is currently the most popular and ergonomic Rust web framework.",
      timestamp: "2026-11-03T14:31:00.000Z",
    });

    const tueConv = store.createConversation("sess-tue", "Postgres Hosting Comparison");
    store.saveMessage({
      conversation_id: tueConv.id,
      role: "user",
      content: "What are the best Postgres hosting options?",
      timestamp: "2026-11-10T11:00:00.000Z",
      entities: ["Postgres", "Supabase", "Neon"],
    });
    store.saveMessage({
      conversation_id: tueConv.id,
      role: "assistant",
      content: "Supabase ($25/mo) and Neon ($19/mo) are top managed Postgres providers.",
      timestamp: "2026-11-10T11:01:00.000Z",
    });
  });

  afterEach(() => {
    store.close();
  });

  it("Scenario A: Recovers Monday CRM shortlist and checks current changes", async () => {
    const result = await orchestrator.processTurn(
      "sess-a",
      "On Monday we shortlisted 5 CRM tools for a 20-person sales team. Has any of them changed pricing or shipped something big since?"
    );

    expect(result.historicalRetrieved).toBe(true);
    expect(result.text).toContain("20-person");
    expect(result.text).toContain("HubSpot");
    expect(result.citations.length).toBeGreaterThan(0);
  });

  it("Scenario B: Recovers 3 November question and evaluates current correctness", async () => {
    const result = await orchestrator.processTurn(
      "sess-b",
      "What did I ask you on 3 November? Is your answer still correct today?"
    );

    expect(result.historicalRetrieved).toBe(true);
    expect(result.text).toContain("Axum");
    expect(result.citations.length).toBeGreaterThan(0);
  });

  it("Scenario C: Recovers previous Tuesday Postgres hosting discussion", async () => {
    const result = await orchestrator.processTurn(
      "sess-c",
      "Last Tuesday I asked you about Postgres hosting. Has any pricing changed since then?"
    );

    expect(result.historicalRetrieved).toBe(true);
    expect(result.text.toLowerCase()).toContain("postgres");
  });
});
