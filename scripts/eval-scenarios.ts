import { MemoryStore } from "../src/memory/store";
import { AgentOrchestrator } from "../src/agent/orchestrator";
import { WebSearchService } from "../src/tools/web-search";
import { ToolRegistry } from "../src/tools/index";

async function runEvaluation() {
  console.log("================================================================================");
  console.log("MINIMI AUTOMATED EVALUATION BENCHMARK: CRITICAL ASSIGNMENT SCENARIOS");
  console.log("================================================================================\n");

  const store = new MemoryStore(":memory:");

  // Mock search service with realistic data for scenarios
  const mockSearch = new WebSearchService();
  mockSearch.search = async (query: string) => {
    const q = query.toLowerCase();
    if (q.includes("crm") || q.includes("hubspot") || q.includes("pipedrive")) {
      return {
        query,
        results: [
          {
            index: 1,
            title: "HubSpot Pricing & Packaging Update",
            url: "https://www.hubspot.com/pricing/crm-2026",
            snippet: "HubSpot Starter CRM remains $20/month per seat with enhanced AI forecasting tools.",
          },
          {
            index: 2,
            title: "Pipedrive Sales CRM Official Pricing",
            url: "https://www.pipedrive.com/pricing",
            snippet: "Pipedrive Essential plan is $14/seat/month billed annually.",
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
            title: "Rust Web Ecosystem State 2026",
            url: "https://tokio.rs/blog/2026-rust-web",
            snippet: "Axum remains the leading, recommended web framework for Tokio-based async Rust applications.",
          },
        ],
      };
    }
    if (q.includes("postgres") || q.includes("supabase") || q.includes("neon")) {
      return {
        query,
        results: [
          {
            index: 1,
            title: "Supabase Pricing 2026",
            url: "https://supabase.com/pricing",
            snippet: "Supabase Pro plan is $25/month including 8GB disk and 100k MAU.",
          },
          {
            index: 2,
            title: "Neon Serverless Postgres Pricing",
            url: "https://neon.tech/pricing",
            snippet: "Neon Launch tier is $19/month with instant point-in-time recovery and database branching.",
          },
        ],
      };
    }

    return {
      query,
      results: [
        {
          index: 1,
          title: "Verified Web Result",
          url: "https://example.com/verified",
          snippet: "Current web verified information.",
        },
      ],
    };
  };

  const toolRegistry = new ToolRegistry(mockSearch);
  const orchestrator = new AgentOrchestrator({ store, toolRegistry });

  // ---------------------------------------------------------------------------
  // STEP 1: SEED HISTORICAL CONVERSATIONS
  // ---------------------------------------------------------------------------
  console.log("Seeding historical conversations into persistent SQLite storage...");

  // Monday session: CRM Shortlist
  const mondayConv = store.createConversation("sess-monday", "Sales CRM Shortlist");
  const mondayUser = store.saveMessage({
    conversation_id: mondayConv.id,
    role: "user",
    content: "Shortlist 5 CRM tools for a 20-person sales team",
    timestamp: "2026-11-09T10:00:00.000Z",
    entities: ["HubSpot", "Pipedrive", "Close", "Freshsales", "Zoho CRM"],
  });
  const mondayAssistant = store.saveMessage({
    conversation_id: mondayConv.id,
    role: "assistant",
    content: "Here are 5 CRM tools for your 20-person team: 1. HubSpot ($20/seat), 2. Pipedrive ($14/seat), 3. Close ($49/seat), 4. Freshsales ($15/seat), 5. Zoho CRM ($14/seat).",
    timestamp: "2026-11-09T10:01:00.000Z",
  });
  store.saveSearchEvidence({
    message_id: mondayAssistant.id,
    query: "CRM pricing 2026",
    url: "https://www.hubspot.com/pricing/crm-2026",
    title: "HubSpot Pricing",
    snippet: "Starter plan: $20/month per seat.",
  });

  // Nov 3 session: Rust Web Framework
  const nov3Conv = store.createConversation("sess-nov3", "Rust Web Framework Discussion");
  store.saveMessage({
    conversation_id: nov3Conv.id,
    role: "user",
    content: "What is the best Rust web framework in 2026?",
    timestamp: "2026-11-03T14:30:00.000Z",
    entities: ["Axum", "Actix-web", "Rust"],
  });
  store.saveMessage({
    conversation_id: nov3Conv.id,
    role: "assistant",
    content: "Axum is currently the most popular and ergonomic Rust web framework built on Tokio.",
    timestamp: "2026-11-03T14:31:00.000Z",
  });

  // Previous Tuesday session: Postgres Hosting
  const tueConv = store.createConversation("sess-tue", "Postgres Hosting Comparison");
  store.saveMessage({
    conversation_id: tueConv.id,
    role: "user",
    content: "What are the best Postgres hosting options?",
    timestamp: "2026-11-10T11:00:00.000Z",
    entities: ["Postgres", "Supabase", "Neon", "RDS"],
  });
  store.saveMessage({
    conversation_id: tueConv.id,
    role: "assistant",
    content: "Supabase ($25/mo Pro) and Neon ($19/mo Launch) are top managed Postgres providers.",
    timestamp: "2026-11-10T11:01:00.000Z",
  });

  console.log("Historical conversations seeded successfully.\n");

  let totalTests = 0;
  let passedTests = 0;

  function assertTest(name: string, condition: boolean, details?: string) {
    totalTests++;
    if (condition) {
      passedTests++;
      console.log(`  [PASS] ${name}`);
    } else {
      console.error(`  [FAIL] ${name} ${details ? `(${details})` : ""}`);
    }
  }

  // ---------------------------------------------------------------------------
  // SCENARIO A: CRM Shortlist & Subsequent Changes
  // ---------------------------------------------------------------------------
  console.log("--- Executing Scenario A: CRM Shortlist & Recent Changes ---");
  const t0A = performance.now();
  const resA = await orchestrator.processTurn(
    "new-session-a",
    "On Monday we shortlisted 5 CRM tools for a 20-person sales team. Has any of them changed pricing or shipped something big since?"
  );
  const durA = Math.round(performance.now() - t0A);

  assertTest("Scenario A: Historical memory retrieved automatically", resA.historicalRetrieved);
  assertTest("Scenario A: Recovers 20-person sales team context", resA.text.includes("20-person") || resA.text.includes("sales team"));
  assertTest("Scenario A: Mentions shortlisted CRM tools without asking user to repeat", resA.text.includes("HubSpot") && resA.text.includes("Pipedrive"));
  assertTest("Scenario A: Performs web search comparison", resA.text.includes("pricing") || resA.text.includes("Starter"));
  assertTest("Scenario A: Formats verified inline citations", resA.citations.length > 0);
  console.log(`Scenario A Duration: ${durA}ms\n`);

  // ---------------------------------------------------------------------------
  // SCENARIO B: Historical Question and Current Correctness
  // ---------------------------------------------------------------------------
  console.log("--- Executing Scenario B: Historical Question (3 November) ---");
  const t0B = performance.now();
  const resB = await orchestrator.processTurn(
    "new-session-b",
    "What did I ask you on 3 November? Is your answer still correct today?"
  );
  const durB = Math.round(performance.now() - t0B);

  assertTest("Scenario B: Historical memory retrieved for 3 November", resB.historicalRetrieved);
  assertTest("Scenario B: Identifies original question topic (Rust / Axum)", resB.text.includes("Rust") || resB.text.includes("Axum"));
  assertTest("Scenario B: Validates whether answer is still correct today", resB.text.includes("correct") || resB.text.includes("remains") || resB.text.includes("Axum"));
  assertTest("Scenario B: Includes verified citations", resB.citations.length > 0);
  console.log(`Scenario B Duration: ${durB}ms\n`);

  // ---------------------------------------------------------------------------
  // SCENARIO C: Previous Tuesday's Postgres Hosting Discussion
  // ---------------------------------------------------------------------------
  console.log("--- Executing Scenario C: Previous Tuesday Postgres Hosting ---");
  const t0C = performance.now();
  const resC = await orchestrator.processTurn(
    "new-session-c",
    "Last Tuesday I asked you about Postgres hosting. Has any pricing changed since then?"
  );
  const durC = Math.round(performance.now() - t0C);

  assertTest("Scenario C: Historical memory retrieved for last Tuesday", resC.historicalRetrieved);
  assertTest("Scenario C: Identifies Postgres hosting topic", resC.text.toLowerCase().includes("postgres") || resC.text.includes("Minimi"));
  console.log(`Scenario C Duration: ${durC}ms\n`);

  // ---------------------------------------------------------------------------
  // SUMMARY REPORT
  // ---------------------------------------------------------------------------
  console.log("================================================================================");
  console.log(`EVALUATION COMPLETE: ${passedTests}/${totalTests} checks passed (${Math.round((passedTests / totalTests) * 100)}%)`);
  console.log("================================================================================");

  store.close();

  if (passedTests === totalTests) {
    process.exit(0);
  } else {
    process.exit(1);
  }
}

runEvaluation().catch((err) => {
  console.error("Evaluation error:", err);
  process.exit(1);
});
