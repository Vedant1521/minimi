import { SearchSnippet } from "@/tools/web-search";

export interface CitationReference {
  index: number;
  title: string;
  url: string;
  snippet: string;
  verified: boolean;
}

export interface VerificationResult {
  cleanedText: string;
  citations: CitationReference[];
  unverifiedIndices: number[];
}

export class CitationVerifier {
  /**
   * Validates citations in the model text against retrieved search snippets.
   * Strips out-of-bounds citations and maps valid citations to full metadata.
   */
  public verify(text: string, availableSnippets: SearchSnippet[]): VerificationResult {
    const snippetMap = new Map<number, SearchSnippet>();
    for (const s of availableSnippets) {
      snippetMap.set(s.index, s);
    }

    const citationRegex = /\[(\d+)\]/g;
    const citedIndices = new Set<number>();
    const unverifiedIndices: number[] = [];

    // Find all citation numbers in text
    let match;
    while ((match = citationRegex.exec(text)) !== null) {
      const idx = parseInt(match[1], 10);
      citedIndices.add(idx);
      if (!snippetMap.has(idx)) {
        unverifiedIndices.push(idx);
      }
    }

    // Replace unverified citations or clean up text
    let cleanedText = text;
    for (const badIdx of unverifiedIndices) {
      // Remove hallucinated bracket like [9]
      cleanedText = cleanedText.replace(new RegExp(`\\[${badIdx}\\]`, "g"), "");
    }

    // Build verified citation list in ascending order of index
    const verifiedCitations: CitationReference[] = [];
    for (const idx of Array.from(citedIndices).sort((a, b) => a - b)) {
      const snippet = snippetMap.get(idx);
      if (snippet) {
        verifiedCitations.push({
          index: snippet.index,
          title: snippet.title,
          url: snippet.url,
          snippet: snippet.snippet,
          verified: true,
        });
      }
    }

    return {
      cleanedText: cleanedText.replace(/\s{2,}/g, " ").trim(),
      citations: verifiedCitations,
      unverifiedIndices,
    };
  }
}
