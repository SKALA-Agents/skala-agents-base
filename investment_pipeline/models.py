from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


Stage = Literal["Seed", "Series A", "Series B", "Series C+"]
Recommendation = Literal["High Priority DD", "Selective DD", "Watchlist", "No DD"]
ReportBranch = Literal["top3", "hold"]


class CompanyProfile(BaseModel):
    name: str
    industry: str = "Semiconductor (반도체)"
    stage: Stage
    headquarters: Optional[str] = None
    business_model: str = ""
    product_summary: str = ""
    customer_focus: str = ""
    moat: str = ""
    risks: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    team_signal: int = Field(default=3, ge=1, le=5)
    market_signal: int = Field(default=3, ge=1, le=5)
    technology_signal: int = Field(default=3, ge=1, le=5)
    traction_signal: int = Field(default=3, ge=1, le=5)
    competition_signal: int = Field(default=3, ge=1, le=5)
    risk_signal: int = Field(default=3, ge=1, le=5)
    team_summary: str = ""
    market_summary: str = ""
    technology_summary: str = ""
    traction_summary: str = ""
    competition_summary: str = ""
    risk_summary: str = ""


class MarketResearch(BaseModel):
    domain: str
    market_size_summary: str
    growth_drivers: List[str]
    regulatory_context: List[str]
    references: List[str]


class CompanyResearch(BaseModel):
    company_name: str
    stage: Stage
    company_overview: str
    business_model_status: str
    product_and_technology: str
    traction_summary: str
    team_summary: str
    competition_summary: str
    risk_summary: str
    references: List[str] = Field(default_factory=list)


class ResearchEvidence(BaseModel):
    title: str
    url: str
    source: str
    published_date: Optional[str] = None
    content: str
    score: Optional[float] = None
    category: str


class CompanyWebResearch(BaseModel):
    company_name: str
    stage: Stage
    industry: str
    search_queries: List[str]
    evidence: List[ResearchEvidence]


class MarketWebResearch(BaseModel):
    domain: str
    search_queries: List[str]
    evidence: List[ResearchEvidence]


class EvaluationResult(BaseModel):
    category: str
    score: int = Field(ge=1, le=5)
    weighted_score: float = Field(ge=0)
    summary: str
    evidence: List[str] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)


class InvestmentDecision(BaseModel):
    company_name: str
    stage: Stage
    final_score: int = Field(ge=0, le=100)
    recommendation: Recommendation
    strengths: List[str]
    weaknesses: List[str]
    summary: str
    technical_evaluation: EvaluationResult
    market_evaluation: EvaluationResult
    team_evaluation: EvaluationResult
    competition_evaluation: EvaluationResult
    risk_analysis: EvaluationResult
    references: List[str] = Field(default_factory=list)


class RankingSelection(BaseModel):
    branch: ReportBranch
    passed_companies: List[str]
    top_companies: List[str]
    score_threshold: int
    high_priority_threshold: int
    watchlist_companies: List[str]


class PipelineResult(BaseModel):
    report_markdown: str
    branch: ReportBranch
    ranking: RankingSelection
    decisions: List[InvestmentDecision]
    market_research: MarketResearch


class MarketResearchLLMOutput(BaseModel):
    market_size_summary: str
    growth_drivers: List[str]
    regulatory_context: List[str]
    references: List[str]


class CompanyResearchLLMOutput(BaseModel):
    company_overview: str
    business_model_status: str
    product_and_technology: str
    traction_summary: str
    team_summary: str
    competition_summary: str
    risk_summary: str


class EvaluationLLMOutput(BaseModel):
    summary: str
    evidence: List[str]
    follow_up_questions: List[str]
