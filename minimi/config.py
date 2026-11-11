"""
Configuration management for Minimi.
"""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


@dataclass
class Config:
    """Application configuration for Minimi agent and services."""

    model: str = field(
        default_factory=lambda: os.getenv("MINIMI_MODEL", "openai/gpt-4o-mini")
    )
    temperature: float = field(
        default_factory=lambda: float(os.getenv("MINIMI_TEMPERATURE", "0.7"))
    )
    max_tokens: int = field(
        default_factory=lambda: int(os.getenv("MINIMI_MAX_TOKENS", "1024"))
    )
    max_iterations: int = field(
        default_factory=lambda: int(os.getenv("MINIMI_MAX_ITERATIONS", "5"))
    )
    tvly_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("TVLY_API_KEY")
    )
    db_path: Path = field(
        default_factory=lambda: Path(os.getenv("MINIMI_DB_PATH", "minimi.duckdb"))
    )

    def validate(self) -> list[str]:
        """Check configuration warnings or missing non-critical items."""
        warnings = []
        if not self.tvly_api_key:
            warnings.append("TVLY_API_KEY is not set. Web search tool will require an API key to fetch live results.")
        return warnings


def get_default_config() -> Config:
    """Return default application configuration."""
    return Config()
