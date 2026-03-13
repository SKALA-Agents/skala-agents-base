from __future__ import annotations

from pathlib import Path
import json

import typer
from rich.console import Console

from .config import settings
from .graph import run_pipeline
from .pdf_export import export_markdown_to_pdf
from .report_polish import polish_report_to_korean
from .services import load_companies

app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def main(
    input: Path = typer.Option(settings.default_input_path, exists=True, readable=True),
    output: Path = typer.Option(settings.default_output_path),
    domain: str = typer.Option(settings.domain_name),
    live_research: bool = typer.Option(settings.enable_live_research),
    llm_enrichment: bool = typer.Option(settings.enable_llm_enrichment),
    polish_korean: bool = typer.Option(False),
) -> None:
    settings.enable_live_research = live_research
    settings.enable_llm_enrichment = llm_enrichment
    companies = load_companies(input)
    result = run_pipeline(domain=domain, companies=companies)
    report_markdown = result.report_markdown

    if polish_korean and settings.enable_llm_enrichment:
        polished = polish_report_to_korean(report_markdown)
        if polished:
            report_markdown = polished
            result.report_markdown = polished

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report_markdown, encoding="utf-8")
    export_markdown_to_pdf(output, output.with_suffix(".pdf"))

    state_output = output.with_suffix(".json")
    state_output.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    console.print(f"Report written to {output}")
    console.print(f"State snapshot written to {state_output}")
    console.print(f"Branch selected: {result.branch}")


if __name__ == "__main__":
    app()
