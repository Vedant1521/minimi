import { describe, it, expect } from "vitest";
import { CitationVerifier } from "@/grounding/verifier";
import { SearchSnippet } from "@/tools/web-search";

describe("CitationVerifier (Evidence Grounding)", () => {
  const verifier = new CitationVerifier();

  const snippets: SearchSnippet[] = [
    {
      index: 1,
      title: "HubSpot Pricing",
      url: "https://hubspot.com/pricing",
      snippet: "HubSpot starts at $20/month per seat.",
    },
    {
      index: 2,
      title: "Pipedrive Pricing",
      url: "https://pipedrive.com/pricing",
      snippet: "Pipedrive starts at $14/month per user.",
    },
  ];

  it("verifies and extracts valid citation indices matching retrieved snippets", () => {
    const text = "HubSpot costs $20/month [1], while Pipedrive costs $14/month [2].";
    const result = verifier.verify(text, snippets);

    expect(result.citations.length).toBe(2);
    expect(result.citations[0].index).toBe(1);
    expect(result.citations[0].title).toBe("HubSpot Pricing");
    expect(result.citations[1].index).toBe(2);
    expect(result.citations[1].title).toBe("Pipedrive Pricing");
    expect(result.unverifiedIndices.length).toBe(0);
    expect(result.cleanedText).toContain("[1]");
    expect(result.cleanedText).toContain("[2]");
  });

  it("strips fabricated or out-of-bounds citation indices", () => {
    // Snippet 3 and 9 do not exist in the availableSnippets array
    const text = "HubSpot is popular [1], and another claim is cited here [9].";
    const result = verifier.verify(text, snippets);

    expect(result.citations.length).toBe(1);
    expect(result.citations[0].index).toBe(1);
    expect(result.unverifiedIndices).toEqual([9]);
    // [9] should be cleanly removed from the text
    expect(result.cleanedText).not.toContain("[9]");
    expect(result.cleanedText).toContain("[1]");
  });

  it("handles text without citations gracefully", () => {
    const text = "Hello! How can I help you today?";
    const result = verifier.verify(text, snippets);

    expect(result.citations.length).toBe(0);
    expect(result.unverifiedIndices.length).toBe(0);
    expect(result.cleanedText).toBe(text);
  });
});
