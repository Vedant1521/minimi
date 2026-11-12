import { webSearchToolDefinition, WebSearchService, WebSearchResult } from "./web-search";

export class ToolRegistry {
  private searchService: WebSearchService;

  constructor(searchService?: WebSearchService) {
    this.searchService = searchService || new WebSearchService();
  }

  /**
   * Returns the exact list of tools callable by the LLM.
   * STRICT REQUIREMENT: This registry contains strictly ONE tool: "web_search".
   * Internal memory, database queries, and temporal lookups are internal services
   * and must NEVER appear here.
   */
  public getCallableTools() {
    return [webSearchToolDefinition];
  }

  public getCallableToolNames(): string[] {
    return this.getCallableTools().map((t) => t.function.name);
  }

  public async executeTool(name: string, argsJson: string): Promise<{ resultText: string; searchResult?: WebSearchResult }> {
    if (name !== "web_search") {
      throw new Error(`Unauthorized or unknown tool: "${name}". Only "web_search" is model-callable.`);
    }

    let parsedArgs: { query: string; days?: number };
    try {
      parsedArgs = JSON.parse(argsJson);
    } catch {
      throw new Error(`Invalid JSON arguments for tool "${name}": ${argsJson}`);
    }

    if (!parsedArgs.query) {
      throw new Error(`Tool "${name}" missing required "query" argument.`);
    }

    const searchResult = await this.searchService.search(parsedArgs.query, {
      days: parsedArgs.days,
    });

    if (searchResult.error) {
      return {
        resultText: `Search error: ${searchResult.error}`,
        searchResult,
      };
    }

    if (searchResult.results.length === 0) {
      return {
        resultText: `No search results found for query: "${parsedArgs.query}".`,
        searchResult,
      };
    }

    // Format snippets with numeric citation indices
    const formatted = searchResult.results
      .map((r) => `[${r.index}] "${r.title}" (${r.url}):\n${r.snippet}`)
      .join("\n\n");

    return {
      resultText: formatted,
      searchResult,
    };
  }
}
