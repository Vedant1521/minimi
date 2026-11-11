"""
Command-line interface for Minimi conversational agent.
"""

import argparse
import sys
from rich.console import Console
from rich.markdown import Markdown

from minimi import __version__
from minimi.config import Config, get_default_config


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="minimi",
        description="Minimi: Conversational Agent with Temporal Memory & Evidence Grounding",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"minimi {__version__}"
    )
    parser.add_argument(
        "-m", "--model", type=str, default=None, help="LLM model identifier (LiteLLM format)"
    )
    parser.add_argument(
        "-q", "--query", type=str, default=None, help="Single query to execute non-interactively"
    )
    parser.add_argument(
        "-s", "--session-id", type=str, default=None, help="Conversation session UUID to resume or use"
    )
    return parser


def run_interactive(config: Config, console: Console) -> None:
    """Run interactive REPL loop."""
    console.print(
        f"[bold cyan]Minimi AI Agent v{__version__}[/bold cyan] (Model: [yellow]{config.model}[/yellow])"
    )
    console.print("Type your message, or [dim]'exit' / 'quit'[/dim] to leave.\n")

    warnings = config.validate()
    for warning in warnings:
        console.print(f"[dim yellow]Notice: {warning}[/dim yellow]")

    while True:
        try:
            prompt = console.input("[bold green]minimi>[/bold green] ").strip()
            if not prompt:
                continue
            if prompt.lower() in {"exit", "quit", ":q"}:
                console.print("[dim]Goodbye![/dim]")
                break

            # Placeholder response until Agent loop is wired in Milestone 2
            console.print(Markdown(f"**Minimi received:** {prompt}"))
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session closed.[/dim]")
            break


def main(args: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    parsed = parser.parse_args(args)

    config = get_default_config()
    if parsed.model:
        config.model = parsed.model

    console = Console()

    if parsed.query:
        console.print(Markdown(f"**Query:** {parsed.query}"))
        return 0

    run_interactive(config, console)
    return 0


if __name__ == "__main__":
    sys.exit(main())
