from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    domain_name: str = "Semiconductor (반도체)"
    default_input_path: Path = Path("data/sample_companies.json")
    default_output_path: Path = Path("outputs/final_report.md")
    default_design_doc_path: Path = Path(
        "/Users/angj/Downloads/ExportBlock-856dd11e-46b6-4679-b841-64168447bcf2-Part-1/최종 산출물 32174d55d65b80a499bfd6af6e76c3d6.md"
    )
    openai_model: str = "gpt-4.1-mini"
    temperature: float = 0.0
    selective_dd_threshold: int = 65
    high_priority_threshold: int = 80
    enable_llm_enrichment: bool = False
    enable_live_research: bool = True
    tavily_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TAVILY_API_KEY", "TAVILY_APIKEY"),
    )
    tavily_max_results_per_query: int = 3
    research_cache_dir: Path = Path("outputs/research_cache")
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "OPEN_AI_API"),
    )


settings = Settings()
