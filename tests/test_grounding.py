"""
Tests for EvidenceGrounder, citation validation, hallucination stripping, and source attribution.
"""

from unittest.mock import MagicMock
import pytest

from minimi.agent import ConversationalAgent
from minimi.grounding import EvidenceGrounder, GroundingReport
from minimi.llm import LLMResponse, ToolCall
from minimi.search import Citation, SearchResponse, WebSearchEngine
from minimi.tools import register_default_tools


def test_extract_cited_indices():
    """Verify regex extraction of Markdown citation anchors."""
    text = "Recent findings in quantum computing [^1] demonstrate exponential speedups [^2]. Further analysis [^1] confirms [^5]."
    indices = EvidenceGrounder.extract_cited_indices(text)
    assert indices == [1, 2, 5]

    no_cites = "No citations present in this text."
    assert EvidenceGrounder.extract_cited_indices(no_cites) == []


def test_verify_all_valid_citations():
    """Verify formatting when all cited anchors exist in retrieved evidence."""
    citations = [
        Citation(index=1, title="Quantum Intro", url="https://quantum.org/intro", snippet="Intro to qubits."),
        Citation(index=2, title="Error Correction", url="https://quantum.org/qec", snippet="Surface codes."),
    ]
    text = "Quantum algorithms leverage superposition [^1] and fault tolerance [^2]."

    report = EvidenceGrounder.verify_and_format(text, citations)
    assert not report.has_hallucinations
    assert report.valid_indices == [1, 2]
    assert report.hallucinated_indices == []
    assert "**Sources:**" in report.grounded_response
    assert "[^1]: [Quantum Intro](https://quantum.org/intro)" in report.grounded_response
    assert "[^2]: [Error Correction](https://quantum.org/qec)" in report.grounded_response


def test_detect_and_strip_hallucinated_citations():
    """Verify that unsupported citation anchors are detected and stripped from final output."""
    citations = [
        Citation(index=1, title="Space Mission", url="https://space.org/mars", snippet="Mars landing."),
    ]
    # Model cites valid [^1] and hallucinated [^3] and [^99]
    text = "The rover touched down in Jezero crater [^1] and discovered fossil evidence [^3], as noted here [^99]."

    report = EvidenceGrounder.verify_and_format(text, citations)
    assert report.has_hallucinations
    assert report.valid_indices == [1]
    assert report.hallucinated_indices == [3, 99]

    # Cleaned text should not contain [^3] or [^99]
    assert "[^3]" not in report.cleaned_text
    assert "[^99]" not in report.cleaned_text
    assert "[^1]" in report.cleaned_text
    assert "[^1]: [Space Mission](https://space.org/mars)" in report.grounded_response
    assert "[^3]:" not in report.grounded_response


def test_no_citations_clean():
    """Verify text with no citations is returned without modification."""
    text = "The speed of light is approximately 299,792 km/s."
    report = EvidenceGrounder.verify_and_format(text, [])
    assert report.valid_indices == []
    assert report.hallucinated_indices == []
    assert report.sources_footer == ""
    assert report.grounded_response == text


def test_agent_grounding_integration(mock_config):
    """Verify agent automatically validates citations and appends source footers."""
    mock_gateway = MagicMock()

    # Step 1: Agent calls web_search
    step1 = LLMResponse(
        content="",
        model="mock/mock-model",
        tool_calls=[
            ToolCall(
                id="call_web_search",
                name="web_search",
                arguments={"query": "Voyager 1 location"},
            )
        ],
    )
    # Step 2: Agent responds citing [^1] and hallucinated [^4]
    step2 = LLMResponse(
        content="Voyager 1 is in interstellar space [^1] past the heliopause [^4].",
        model="mock/mock-model",
        tool_calls=[],
    )
    mock_gateway.complete.side_effect = [step1, step2]

    agent = ConversationalAgent(
        config=mock_config,
        llm_gateway=mock_gateway,
        auto_register_tools=False,
    )

    mock_engine = MagicMock(spec=WebSearchEngine)
    mock_engine.api_key = "mock-key"
    mock_engine.search.return_value = SearchResponse(
        query="Voyager 1 location",
        citations=[
            Citation(
                index=1,
                title="NASA Voyager Status",
                url="https://voyager.jpl.nasa.gov/mission/status/",
                snippet="Voyager 1 is currently operating in interstellar space.",
            )
        ],
    )
    register_default_tools(agent, search_engine=mock_engine)

    response = agent.step("Where is Voyager 1 currently?")

    # Hallucinated [^4] stripped, valid [^1] preserved with source footer
    assert "[^1]" in response
    assert "[^4]" not in response
    assert "**Sources:**" in response
    assert "[^1]: [NASA Voyager Status](https://voyager.jpl.nasa.gov/mission/status/)" in response
