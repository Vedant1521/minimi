"""
Evidence grounding verification, citation validation, and source footnote formatting.
"""

from dataclasses import dataclass, field
import re
from typing import List, Optional

from minimi.search import Citation

# Match Markdown footnote citation anchors like [^1], [^2], [^10]
CITATION_PATTERN = re.compile(r"\[\^(\d+)\]")


@dataclass
class GroundingReport:
    """Detailed report of evidence grounding and citation verification."""
    cited_indices: list[int] = field(default_factory=list)
    valid_indices: list[int] = field(default_factory=list)
    hallucinated_indices: list[int] = field(default_factory=list)
    cleaned_text: str = ""
    sources_footer: str = ""
    grounded_response: str = ""

    @property
    def has_hallucinations(self) -> bool:
        return len(self.hallucinated_indices) > 0


class EvidenceGrounder:
    """Validates citations in generated responses against retrieved evidence and appends verified sources."""

    @classmethod
    def extract_cited_indices(cls, text: str) -> list[int]:
        """Extract all unique numerical citation anchor indices from markdown text in order of appearance."""
        seen = set()
        result = []
        for match in CITATION_PATTERN.finditer(text):
            idx = int(match.group(1))
            if idx not in seen:
                seen.add(idx)
                result.append(idx)
        return result

    @classmethod
    def verify_and_format(
        cls,
        response_text: str,
        available_citations: list[Citation],
    ) -> GroundingReport:
        """Verify cited anchors against available citations and append formatted footnotes."""
        cited = cls.extract_cited_indices(response_text)
        citation_map = {c.index: c for c in available_citations}

        valid_indices: list[int] = []
        hallucinated_indices: list[int] = []

        for idx in cited:
            if idx in citation_map:
                valid_indices.append(idx)
            else:
                hallucinated_indices.append(idx)

        # Clean text by removing hallucinated citation anchors
        cleaned_text = response_text
        for bad_idx in hallucinated_indices:
            pattern = re.compile(rf"\[\^{bad_idx}\]")
            cleaned_text = pattern.sub("", cleaned_text)

        # Build clean sources footnote footer if valid citations exist
        sources_footer = ""
        if valid_indices:
            footer_lines = ["\n\n---\n**Sources:**"]
            for idx in valid_indices:
                cit = citation_map[idx]
                footer_lines.append(cit.to_citation_line())
            sources_footer = "\n".join(footer_lines)

        final_response = cleaned_text.rstrip() + sources_footer if sources_footer else cleaned_text

        return GroundingReport(
            cited_indices=cited,
            valid_indices=valid_indices,
            hallucinated_indices=hallucinated_indices,
            cleaned_text=cleaned_text,
            sources_footer=sources_footer,
            grounded_response=final_response,
        )
