from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field


class ServiceConfig(BaseModel):
    domain: str = "AI Semiconductor"
    md_glob: str = "*.md"
    chunk_size: int = 1200
    chunk_overlap: int = 200
    retrieval_k: int = 6
    embedding_model: str = "BAAI/bge-m3"
    llm_model: str = "gpt-4.1-mini"
    temperature: float = 0.1
    top_k_companies: int = 3
    recommendation_threshold: int = 20
    langsmith_tracing: bool = Field(
        default_factory=lambda: (
            os.getenv("LANGCHAIN_TRACING_V2", "").strip().lower()
            in {"1", "true", "yes", "on"}
        )
    )
    langsmith_api_key: str | None = Field(
        default_factory=lambda: os.getenv("LANGCHAIN_API_KEY")
        or os.getenv("LANGSMITH_API_KEY")
    )
    langsmith_project: str = Field(
        default_factory=lambda: os.getenv("LANGCHAIN_PROJECT")
        or os.getenv("LANGSMITH_PROJECT")
        or "langchain_project_develop"
    )
    langsmith_endpoint: str = Field(
        default_factory=lambda: os.getenv("LANGCHAIN_ENDPOINT")
        or os.getenv("LANGSMITH_ENDPOINT")
        or "https://api.smith.langchain.com"
    )
    langsmith_tags: str = Field(
        default_factory=lambda: os.getenv("LANGCHAIN_TAGS")
        or os.getenv("LANGSMITH_TAGS")
        or "agents"
    )


class CompanyList(BaseModel):
    companies: list[str] = Field(default_factory=list)


class AgentEvaluation(BaseModel):
    company_name: str
    score: int = Field(ge=1, le=5)
    rationale: str
    strengths: list[str]
    risks: list[str]
    diligence_questions: list[str]


class CompanyEvaluation(BaseModel):
    company_name: str
    thesis: str
    technology_score: int = Field(ge=1, le=5)
    market_score: int = Field(ge=1, le=5)
    business_score: int = Field(ge=1, le=5)
    team_score: int = Field(ge=1, le=5)
    risk_score: int = Field(ge=1, le=5)
    competition_score: int = Field(ge=1, le=5)
    strengths: list[str]
    risks: list[str]
    diligence_questions: list[str]

    @property
    def total_score(self) -> int:
        return (
            self.technology_score
            + self.market_score
            + self.business_score
            + self.team_score
            + self.risk_score
            + self.competition_score
        )


class GraphState(BaseModel):
    domain: str
    source_files: list[str] = Field(default_factory=list)
    market_context: str = ""
    market_analysis: str = ""
    companies: list[str] = Field(default_factory=list)
    company_contexts: dict[str, str] = Field(default_factory=dict)
    technology_evaluations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    market_evaluations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    business_evaluations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    team_evaluations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    risk_evaluations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    competition_evaluations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    evaluations: list[dict[str, Any]] = Field(default_factory=list)
    selected_companies: list[dict[str, Any]] = Field(default_factory=list)
    hold_companies: list[dict[str, Any]] = Field(default_factory=list)
    policy_decision: str = ""
    policy_reason: str = ""
    final_report: str = ""
    output_path: str = ""
