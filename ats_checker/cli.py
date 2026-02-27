"""CLI entry point for ATS Resume Checker."""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .checker import ATSReport, CheckResult, analyse_resume
from .parser import extract_text

app = typer.Typer(help="ATS Resume Checker — score and improve your resume.")
console = Console()


def _score_color(score: int) -> str:
    if score >= 75:
        return "green"
    if score >= 50:
        return "yellow"
    return "red"


def _render_check(check: CheckResult) -> None:
    pct = round(check.score / check.max_score * 100) if check.max_score else 0
    color = _score_color(pct)

    header = Text()
    header.append(f"  {check.name}  ", style="bold")
    header.append(f"[{check.score}/{check.max_score}]", style=f"bold {color}")
    console.print(header)

    for msg in check.passed:
        console.print(f"    [green]✓[/green] {msg}")
    for msg in check.warnings:
        console.print(f"    [red]✗[/red] {msg}")
    for msg in check.suggestions:
        console.print(f"    [yellow]→[/yellow] {msg}")
    console.print()


def _render_report(report: ATSReport, filepath: Path) -> None:
    color = _score_color(report.overall_score)

    console.print()
    console.print(
        Panel(
            f"[bold {color}]{report.overall_score} / 100[/bold {color}]",
            title=f"ATS Score — {filepath.name}",
            border_style=color,
            expand=False,
        )
    )
    console.print()

    for check in report.checks:
        _render_check(check)

    # Summary table
    table = Table(title="Score Breakdown", show_lines=True)
    table.add_column("Check", style="bold")
    table.add_column("Score", justify="center")
    table.add_column("Max", justify="center")
    for check in report.checks:
        pct = round(check.score / check.max_score * 100) if check.max_score else 0
        c = _score_color(pct)
        table.add_row(check.name, f"[{c}]{check.score}[/{c}]", str(check.max_score))
    table.add_row("[bold]Total[/bold]", f"[bold {color}]{report.overall_score}[/bold {color}]", "100")
    console.print(table)
    console.print()


@app.command()
def check(
    resume: Path = typer.Argument(..., help="Path to resume file (PDF or DOCX)."),
) -> None:
    """Analyse a resume for ATS compatibility and suggest improvements."""
    if not resume.exists():
        console.print(f"[red]Error:[/red] File not found: {resume}")
        raise typer.Exit(code=1)

    if resume.suffix.lower() not in (".pdf", ".docx", ".doc"):
        console.print("[red]Error:[/red] Only PDF and DOCX files are supported.")
        raise typer.Exit(code=1)

    with console.status("Parsing resume…"):
        try:
            text = extract_text(resume)
        except Exception as exc:
            console.print(f"[red]Error reading file:[/red] {exc}")
            raise typer.Exit(code=1)

    if not text.strip():
        console.print("[red]Error:[/red] Could not extract any text from the file.")
        raise typer.Exit(code=1)

    report = analyse_resume(text)
    _render_report(report, resume)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
