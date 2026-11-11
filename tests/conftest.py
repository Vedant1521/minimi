"""
Global pytest fixtures and test configurations for Minimi.
"""

import pytest
from minimi.config import Config


@pytest.fixture
def mock_config(tmp_path):
    """Provide an isolated Config instance with a temporary database path."""
    return Config(
        model="mock/mock-model",
        temperature=0.0,
        max_tokens=256,
        max_iterations=3,
        tvly_api_key="mock-tvly-key",
        db_path=tmp_path / "test_minimi.duckdb",
    )
