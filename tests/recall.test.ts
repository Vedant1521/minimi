import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { MemoryStore } from "@/memory/store";
import { CrossSessionRecallEngine } from "@/memory/recall";
import { TemporalRange } from "@/memory/temporal";

describe("CrossSessionRecallEngine", () => {
  let store: MemoryStore;
  let recall: CrossSessionRecallEngine;

  beforeEach(() => {
    store = new MemoryStore(":memory:");
    recall = new CrossSessionRecallEngine(store);
  });

  afterEach(() => {
    store.close();
  });

  it("recalls Monday CRM shortlist from a prior conversation session (Scenario A)", () => {
    // 1. Seed past conversation from Monday
    const mondayConv = store.createConversation("sess-monday", "Sales CRM Shortlist");
    const userMsg = store.saveMessage({
      conversation_id: mondayConv.id,
      role: "user",
      content: "Shortlist 5 CRM tools for a 20-person sales team",
      timestamp: "2026-11-09T10:00:00.000Z",
      entities: ["HubSpot", "Pipedrive", "Close", "Freshsales", "Zoho CRM"],
    });

    const assistantMsg = store.saveMessage({
      conversation_id: mondayConv.id,
      role: "assistant",
      content: "Here are 5 CRM tools: 1. HubSpot ($20/seat), 2. Pipedrive ($14/seat), 3. Close ($49/seat), 4. Freshsales ($15/seat), 5. Zoho CRM ($14/seat).",
      timestamp: "2026-11-09T10:01:00.000Z",
    });

    store.saveSearchEvidence({
      message_id: assistantMsg.id,
      query: "CRM pricing 2026",
      url: "https://hubspot.com/pricing",
      title: "HubSpot Pricing",
      snippet: "Starter plan: $20/month per seat.",
    });

    // 2. Later session asks: "On Monday we shortlisted 5 CRM tools..."
    const mondayRange: TemporalRange = {
      startDateUtc: "2026-11-09T00:00:00.000Z",
      endDateUtc: "2026-11-09T23:59:59.999Z",
      label: "Monday (2026-11-09)",
      originalText: "on Monday",
    };

    const result = recall.recallByTemporalWindow(mondayRange);
    expect(result.turns.length).toBe(1);
    expect(result.turns[0].conversationTitle).toBe("Sales CRM Shortlist");
    expect(result.turns[0].userMessage.content).toContain("20-person sales team");
    expect(result.turns[0].entities).toContain("HubSpot");
    expect(result.turns[0].entities).toContain("Pipedrive");
    expect(result.turns[0].evidence.length).toBe(1);

    const formatted = recall.formatHistoricalContext(result);
    expect(formatted).toContain("<historical_memory>");
    expect(formatted).toContain("HubSpot Pricing");
    expect(formatted).toContain("Identified Entities: HubSpot, Pipedrive, Close, Freshsales, Zoho CRM");
  });

  it("recalls historical question and answer from 3 November (Scenario B)", () => {
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
      content: "Axum is currently the most popular and actively maintained Rust web framework.",
      timestamp: "2026-11-03T14:31:00.000Z",
    });

    const nov3Range: TemporalRange = {
      startDateUtc: "2026-11-03T00:00:00.000Z",
      endDateUtc: "2026-11-03T23:59:59.999Z",
      label: "2026-11-03",
      originalText: "on 3 November",
    };

    const result = recall.recallByTemporalWindow(nov3Range);
    expect(result.turns.length).toBe(1);
    expect(result.turns[0].userMessage.content).toBe("What is the best Rust web framework in 2026?");
    expect(result.turns[0].assistantMessage?.content).toContain("Axum");
  });

  it("recalls topic across sessions using FTS5 when no date is mentioned", () => {
    const conv1 = store.createConversation("sess-1", "Database Comparison");
    store.saveMessage({
      conversation_id: conv1.id,
      role: "user",
      content: "Tell me about Postgres hosting options like Supabase and Neon",
      entities: ["Postgres", "Supabase", "Neon"],
    });
    store.saveMessage({
      conversation_id: conv1.id,
      role: "assistant",
      content: "Supabase offers managed Postgres with Auth and storage, starting with a free tier. Neon offers serverless branching.",
    });

    const result = recall.recallByTopic("Postgres hosting");
    expect(result.turns.length).toBeGreaterThan(0);
    expect(result.turns[0].conversationTitle).toBe("Database Comparison");
    expect(result.turns[0].entities).toContain("Supabase");
  });
});
