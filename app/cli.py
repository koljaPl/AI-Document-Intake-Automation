"""Command Line Interface for AI Document Intake Automation using Typer and Rich."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from app.config import get_settings
from app.extraction.ai_extractor import AIExtractor
from app.extraction.pdf_extractor import PDFExtractor
from app.models.processing_result import DocumentProcessingResult
from app.pipeline.cache import IntakeCache
from app.pipeline.processor import DocumentPipeline
from app.validation.rules import InvoiceValidator

app = typer.Typer(
    name="ai-intake",
    help="AI Document Intake Automation — Production-grade document ingestion pipeline with structured AI extraction, multi-layer validation, and exception routing.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


@app.command(name="process", help="Batch process a directory of PDF invoice documents.")
def process(
    directory: Path = typer.Argument(
        ...,
        help="Path to directory containing PDF invoices to process",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Target folder for validated CSV/JSON and exception outputs (default: ./output)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force re-processing of documents even if their SHA-256 hash exists in cache",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-d",
        help="Inspect folder against SQLite cache and show estimated API calls without extracting",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="OpenAI model name to use for extraction (default: from .env or gpt-4o-mini)",
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db-path",
        help="Path to SQLite cache database (default: ./intake_cache.db)",
    ),
    confidence_floor: Optional[float] = typer.Option(
        None,
        "--confidence-floor",
        help="Minimum extraction confidence threshold (default: 0.80)",
    ),
) -> None:
    """Batch processes PDF invoices with structured LLM extraction, business rules, and caching."""
    settings = get_settings()

    target_output_dir = output_dir or settings.default_output_dir
    target_db_path = db_path or settings.cache_db_path
    target_model = model or settings.openai_model
    target_confidence = (
        confidence_floor
        if confidence_floor is not None
        else settings.confidence_floor
    )

    cache = IntakeCache(db_path=target_db_path)
    pdf_extractor = PDFExtractor()
    validator = InvoiceValidator(confidence_floor=target_confidence)

    # Initialize pipeline
    # Note: If in dry-run, we don't need OpenAI API key validation
    ai_extractor = None
    if not dry_run:
        try:
            ai_extractor = AIExtractor(
                api_key=settings.openai_api_key,
                model=target_model,
            )
        except Exception as err:
            console.print(f"[bold red]Configuration Error:[/bold red] {err}")
            raise typer.Exit(code=1)

    pipeline = DocumentPipeline(
        cache=cache,
        pdf_extractor=pdf_extractor,
        ai_extractor=ai_extractor,
        validator=validator,
        output_dir=target_output_dir,
    )

    # Scan directory
    try:
        files = pipeline.scan_directory(directory)
    except Exception as err:
        console.print(f"[bold red]Scan Error:[/bold red] {err}")
        raise typer.Exit(code=1)

    if not files:
        console.print(f"[yellow]No PDF documents found in directory: {directory}[/yellow]")
        return

    # Handle --dry-run
    if dry_run:
        stats = pipeline.dry_run(directory)
        console.print(f"[bold cyan][DRY RUN][/bold cyan] {stats['total_documents']} documents found.")
        console.print(f"  - [green]{stats['new_documents']}[/green] new documents to process")
        console.print(f"  - [blue]{stats['already_cached']}[/blue] already cached (will be skipped)")
        console.print(f"  - [bold yellow]Estimated API calls:[/bold yellow] {stats['estimated_api_calls']}")
        return

    # Normal live execution
    console.print(
        Panel.fit(
            f"[bold green]AI Document Intake Pipeline[/bold green]\n"
            f"[dim]Directory:[/dim] {directory}\n"
            f"[dim]Output Folder:[/dim] {target_output_dir}\n"
            f"[dim]Model:[/dim] {target_model} | [dim]Confidence Floor:[/dim] {target_confidence:.2f} | [dim]Force:[/dim] {force}",
            border_style="cyan",
        )
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Processing documents...", total=len(files))

        def on_file_processed(res: DocumentProcessingResult) -> None:
            if res.status == "OK":
                assert res.invoice is not None
                console.print(
                    f"  [bold green]✓[/bold green] [bold]{res.file_name}[/bold] "
                    f"[dim]({res.invoice.supplier_name} • {res.invoice.invoice_number})[/dim] "
                    f"[green](OK)[/green]"
                )
            elif res.status == "FLAGGED":
                assert res.invoice is not None
                console.print(
                    f"  [bold yellow]![/bold yellow] [bold]{res.file_name}[/bold] "
                    f"[yellow](REVIEW)[/yellow] "
                    f"[dim]— {res.message}[/dim]"
                )
            elif res.status == "EXCEPTION":
                issue_tag = res.exception.issue_type if res.exception else "FAILED"
                details = res.exception.details if res.exception else res.message
                console.print(
                    f"  [bold red]✗[/bold red] [bold]{res.file_name}[/bold] "
                    f"[red](FAILED)[/red] "
                    f"[dim]— [{issue_tag}] {details}[/dim]"
                )
            elif res.status == "SKIPPED_CACHED":
                console.print(
                    f"  [bold blue]↷[/bold blue] [bold]{res.file_name}[/bold] "
                    f"[blue](CACHED)[/blue] "
                    f"[dim]— skipped via hash[/dim]"
                )
            progress.advance(task, 1)

        summary, _ = pipeline.process_batch(
            directory=directory,
            force=force,
            on_progress=on_file_processed,
        )

    # Render Summary Table matching the specification
    table = Table(
        title="Pipeline Execution Summary",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_style="bold magenta",
    )
    table.add_column("Metric", style="bold white", width=32)
    table.add_column("Count", justify="right", style="cyan", width=10)

    table.add_row("Total Documents Scanned", str(summary.total_scanned))
    table.add_row("Successfully Processed (OK)", f"[green]{summary.processed_ok}[/green]")
    table.add_row("Flagged for Human Review", f"[yellow]{summary.flagged_review}[/yellow]")
    table.add_row("Extraction Failures", f"[red]{summary.exceptions_count}[/red]")
    table.add_row("Skipped (Already Cached)", f"[blue]{summary.skipped_cached}[/blue]")

    console.print()
    console.print(table)
    console.print()

    console.print(f"[bold]Output generated in:[/bold] [green]{target_output_dir}/[/green]")
    console.print(f"  - [dim]{summary.output_files.get('invoices_csv')}[/dim]")
    console.print(f"  - [dim]{summary.output_files.get('invoices_json')}[/dim]")
    console.print(f"  - [dim]{summary.output_files.get('exceptions_csv')}[/dim]")
    console.print(f"  - [dim]{summary.output_files.get('run_summary_json')}[/dim]")
    console.print()


@app.command(name="stats", help="Display cache database processing history and status statistics.")
def stats(
    db_path: Optional[Path] = typer.Option(
        None,
        "--db-path",
        help="Path to SQLite cache database",
    ),
) -> None:
    """Display statistics of records stored in the SQLite cache."""
    settings = get_settings()
    target_db = db_path or settings.cache_db_path
    cache = IntakeCache(db_path=target_db)

    stat_dict = cache.get_cache_stats()

    table = Table(title=f"Cache Database Statistics ({target_db})", box=box.ROUNDED)
    table.add_column("Status / Category", style="bold white")
    table.add_column("Count", justify="right", style="cyan")

    for status_key, count in stat_dict.items():
        table.add_row(status_key, str(count))

    console.print(table)


@app.command(name="cache-clear", help="Clear all stored file hashes and history from SQLite cache.")
def cache_clear(
    db_path: Optional[Path] = typer.Option(
        None,
        "--db-path",
        help="Path to SQLite cache database",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Confirm deletion without prompting",
    ),
) -> None:
    """Clear all records from the SQLite cache table."""
    settings = get_settings()
    target_db = db_path or settings.cache_db_path
    cache = IntakeCache(db_path=target_db)

    if not yes:
        confirm = typer.confirm(f"Are you sure you want to clear all cache in {target_db}?")
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            return

    cache.clear()
    console.print(f"[green]Successfully cleared cache database at: {target_db}[/green]")


@app.command(name="version", help="Show CLI version.")
def version() -> None:
    """Display version information."""
    console.print("[bold cyan]AI Document Intake Automation[/bold cyan] version [bold green]0.1.0[/bold green]")


if __name__ == "__main__":
    app()
