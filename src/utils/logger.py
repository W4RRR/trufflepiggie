"""
Centralized logging module using Rich library for beautiful console output.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.theme import Theme
from rich import box

# Custom theme for TrufflePiggie
PIGGIE_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "highlight": "magenta",
    "dim": "dim white",
    "banner": "bold cyan",
    "token": "bold yellow",
    "rate": "bold blue",
})

console = Console(theme=PIGGIE_THEME)


def load_banner() -> str:
    """
    Load ASCII art banner from file.
    
    Returns:
        str: The ASCII art banner string.
    """
    banner_path = Path(__file__).parent.parent.parent / "ASCII_ART_TRUFFLEPIGGIE.txt"
    
    try:
        with open(banner_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # Fallback banner if file not found
        return """
╔═══════════════════════════════════════════════════╗
║          TRUFFLEPIGGIE - GitHub OSINT Tool        ║
║                    @by W4R                        ║
╚═══════════════════════════════════════════════════╝
"""


def print_banner() -> None:
    """Display the TrufflePiggie ASCII art banner."""
    banner = load_banner()
    console.print(f"[banner]{banner}[/banner]")
    console.print(
        Panel(
            "[dim]GitHub Repository & Gist OSINT Scanner for TruffleHog[/dim]",
            box=box.DOUBLE_EDGE,
            style="cyan",
        )
    )
    console.print()


def info(message: str, prefix: str = "ℹ") -> None:
    """
    Print an info message.
    
    Args:
        message: The message to display.
        prefix: Prefix character for the message.
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    console.print(f"[dim]{timestamp}[/dim] [{prefix}] [info]{message}[/info]")


def success(message: str, prefix: str = "✓") -> None:
    """
    Print a success message.
    
    Args:
        message: The message to display.
        prefix: Prefix character for the message.
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    console.print(f"[dim]{timestamp}[/dim] [{prefix}] [success]{message}[/success]")


def warning(message: str, prefix: str = "⚠") -> None:
    """
    Print a warning message.
    
    Args:
        message: The message to display.
        prefix: Prefix character for the message.
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    console.print(f"[dim]{timestamp}[/dim] [{prefix}] [warning]{message}[/warning]")


def error(message: str, prefix: str = "✗") -> None:
    """
    Print an error message.
    
    Args:
        message: The message to display.
        prefix: Prefix character for the message.
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    console.print(f"[dim]{timestamp}[/dim] [{prefix}] [error]{message}[/error]")


def highlight(message: str, prefix: str = "→") -> None:
    """
    Print a highlighted message.
    
    Args:
        message: The message to display.
        prefix: Prefix character for the message.
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    console.print(f"[dim]{timestamp}[/dim] [{prefix}] [highlight]{message}[/highlight]")


def token_status(token_id: str, remaining: int, reset_time: str) -> None:
    """
    Display current token status.
    
    Args:
        token_id: Masked token identifier.
        remaining: Remaining requests.
        reset_time: Time until reset.
    """
    console.print(
        f"[token]Token:[/token] {token_id} | "
        f"[rate]Remaining:[/rate] {remaining} | "
        f"[dim]Reset:[/dim] {reset_time}"
    )


def create_progress() -> Progress:
    """
    Create a Rich progress bar for tracking operations.
    
    Returns:
        Progress: Configured progress bar instance.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        expand=False,
    )


def create_results_table(title: str = "Search Results") -> Table:
    """
    Create a table for displaying results.
    
    Args:
        title: Table title.
        
    Returns:
        Table: Configured Rich table.
    """
    table = Table(
        title=title,
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold cyan",
    )
    table.add_column("Type", style="yellow", width=10)
    table.add_column("Repository/Gist", style="green")
    table.add_column("URL", style="blue")
    table.add_column("Date", style="dim", width=12)
    
    return table


def print_stats(
    total_repos: int,
    total_gists: int,
    duration: float,
    output_file: Optional[str] = None
) -> None:
    """
    Print final statistics panel.
    
    Args:
        total_repos: Total repositories found.
        total_gists: Total gists found.
        duration: Search duration in seconds.
        output_file: Output file path if saved.
    """
    stats = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    stats.add_column("Label", style="dim")
    stats.add_column("Value", style="bold")
    
    stats.add_row("Repositories Found", f"[green]{total_repos}[/green]")
    stats.add_row("Gists Found", f"[green]{total_gists}[/green]")
    stats.add_row("Total Results", f"[cyan]{total_repos + total_gists}[/cyan]")
    stats.add_row("Duration", f"[yellow]{duration:.2f}s[/yellow]")
    
    if output_file:
        stats.add_row("Output File", f"[magenta]{output_file}[/magenta]")
    
    console.print()
    console.print(Panel(stats, title="[bold]Scan Complete[/bold]", box=box.DOUBLE))


def countdown(seconds: int, message: str = "Waiting for rate limit reset") -> None:
    """
    Display a countdown timer.
    
    Args:
        seconds: Number of seconds to count down.
        message: Message to display during countdown.
    """
    import time
    
    with console.status(f"[yellow]{message}...[/yellow]") as status:
        for remaining in range(seconds, 0, -1):
            mins, secs = divmod(remaining, 60)
            status.update(f"[yellow]{message}... {mins:02d}:{secs:02d}[/yellow]")
            time.sleep(1)

