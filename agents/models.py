from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ServiceConfig(BaseModel):
    domain: str = "AI Semiconductor"
    companies: list[str] = Field(default_factory=list)
    chunk_size: int = 1200
    chunk_overlap: int = 200
    retrieval_k: int = 6
    embedding_model: str = "BAAI/bge-m3"
    llm_model: str = "gpt-4.1-mini"
    temperature: float = 0.1
    top_k_companies: int = 3
    recommendation_threshold: int = 60
    web_search_results: int = 5
    web_request_timeout: int = 30
    max_page_chars: int = 6000
    max_research_urls_per_company: int = 5


class CompanyList(BaseModel):
    companies: list[str] = Field(default_factory=list)


class ResearchSource(BaseModel):
    title: str
    url: str
    snippet: str = ""


class CompanyResearch(BaseModel):
    company_name: str
    summary: str
    product_overview: str
    technology_overview: str
    business_model: str
    traction: str
    team: str
    competition: str
    risks: list[str]
    references: list[ResearchSource]


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

    @property
    def normalized_score(self) -> int:
        return round((self.total_score / 30) * 100)


class GraphState(BaseModel):
    domain: str
    input_companies: list[str] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    market_context: str = ""
    market_analysis: str = ""
    companies: list[str] = Field(default_factory=list)
    company_research: dict[str, dict[str, Any]] = Field(default_factory=dict)
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
