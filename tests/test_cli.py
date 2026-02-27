"""Tests for the Typer CLI."""

from pathlib import Path

from typer.testing import CliRunner

from ats_checker.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Analyse a resume" in result.output


def test_file_not_found():
    result = runner.invoke(app, ["nonexistent.pdf"])
    assert result.exit_code == 1
    assert "File not found" in result.output


def test_unsupported_extension(tmp_path: Path):
    f = tmp_path / "resume.txt"
    f.write_text("hello")
    result = runner.invoke(app, [str(f)])
    assert result.exit_code == 1
    assert "Only PDF and DOCX" in result.output


def test_successful_check(sample_docx: Path):
    result = runner.invoke(app, [str(sample_docx)])
    assert result.exit_code == 0
    assert "ATS Score" in result.output
    assert "Score Breakdown" in result.output
