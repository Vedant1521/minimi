import { describe, it, expect, vi } from "vitest";
import { ToolRegistry } from "@/tools/index";
import { WebSearchService } from "@/tools/web-search";

describe("Strict Single-Tool Boundary & Web Search", () => {
  it("enforces that exactly one model-callable tool is exposed: web_search", () => {
    const registry = new ToolRegistry();
    const tools = registry.getCallableTools();

    expect(tools.length).toBe(1);
    expect(tools[0].type).toBe("function");
    expect(tools[0].function.name).toBe("web_search");
    expect(registry.getCallableToolNames()).toEqual(["web_search"]);

    // Memory and persistence functions must NOT be callable agent tools
    expect(registry.getCallableToolNames()).not.toContain("retrieve_memory");
    expect(registry.getCallableToolNames()).not.toContain("search_database");
    expect(registry.getCallableToolNames()).not.toContain("recall_history");
  });

  it("rejects execution of any tool other than web_search", async () => {
    const registry = new ToolRegistry();
    await expect(registry.executeTool("retrieve_memory", "{}")).rejects.toThrow(
      /Unauthorized or unknown tool/
    );
    await expect(registry.executeTool("sql_query", "{}")).rejects.toThrow(
      /Unauthorized or unknown tool/
    );
  });

  it("executes web_search with valid JSON arguments", async () => {
    const mockSearch = new WebSearchService();
    vi.spyOn(mockSearch, "search").mockResolvedValue({
      query: "HubSpot pricing 2026",
      results: [
        {
          index: 1,
          title: "HubSpot Pricing & Plans",
          url: "https://hubspot.com/pricing",
          snippet: "HubSpot Starter is $20/month per user.",
        },
      ],
    });

    const registry = new ToolRegistry(mockSearch);
    const result = await registry.executeTool(
      "web_search",
      JSON.stringify({ query: "HubSpot pricing 2026" })
    );

    expect(result.searchResult).toBeDefined();
    expect(result.searchResult?.results.length).toBe(1);
    expect(result.resultText).toContain('[1] "HubSpot Pricing & Plans"');
    expect(result.resultText).toContain("https://hubspot.com/pricing");
  });

  it("handles malformed JSON arguments gracefully", async () => {
    const registry = new ToolRegistry();
    await expect(registry.executeTool("web_search", "{invalid json")).rejects.toThrow(
      /Invalid JSON arguments/
    );
  });

  it("deduplicates search results with identical URLs", async () => {
    const searchService = new WebSearchService("test-key");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: [
          { title: "Result 1", url: "https://example.com/item", content: "Snippet 1" },
          { title: "Result 2", url: "https://example.com/item", content: "Duplicate Snippet" },
          { title: "Result 3", url: "https://example.com/other", content: "Unique Snippet" },
        ],
      }),
    });
    global.fetch = mockFetch;

    const res = await searchService.search("test query");
    expect(res.results.length).toBe(2);
    expect(res.results[0].url).toBe("https://example.com/item");
    expect(res.results[1].url).toBe("https://example.com/other");
    expect(res.results[0].index).toBe(1);
    expect(res.results[1].index).toBe(2);
  });
});
