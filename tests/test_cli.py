"""
Tests for Minimi command-line interface and configuration.
"""

import pytest
from minimi import __version__
from minimi.cli import build_parser, main
from minimi.config import Config, get_default_config


def test_version_output(capsys):
    """Test CLI version option."""
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_parser_options():
    """Test CLI options parsing."""
    parser = build_parser()
    args = parser.parse_args(["--model", "gemini/gemini-2.0-flash", "--query", "hello world", "-s", "test-session"])
    assert args.model == "gemini/gemini-2.0-flash"
    assert args.query == "hello world"
    assert args.session_id == "test-session"


def test_default_config():
    """Test default configuration loading."""
    config = get_default_config()
    assert isinstance(config, Config)
    assert config.max_iterations >= 1
    assert config.temperature >= 0.0


def test_cli_single_query(capsys):
    """Test non-interactive query flag via main()."""
    exit_code = main(["--query", "What is the capital of France?"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "What is the capital of France?" in captured.out
