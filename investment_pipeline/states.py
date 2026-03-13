from __future__ import annotations

from typing import Dict, List, Optional, TypedDict

from .models import (
    CompanyProfile,
    CompanyResearch,
    EvaluationResult,
    InvestmentDecision,
    MarketResearch,
    RankingSelection,
)


class PipelineState(TypedDict, total=False):
    pipeline_meta_state: Dict[str, str]
    domain_definition_state: str
    candidate_company_pool_state: List[CompanyProfile]
    domain_market_research_state: MarketResearch
    investment_decision_state: List[InvestmentDecision]
    ranking_selection_state: RankingSelection
    final_report_markdown: str


class CompanyAnalysisState(TypedDict, total=False):
    selected_company_context_state: CompanyProfile
    supervisor_route_state: str
    company_research_state: CompanyResearch
    technical_evaluation_state: EvaluationResult
    technical_additional_research_state: List[str]
    technical_recheck_completed_state: bool
    market_evaluation_state: EvaluationResult
    market_additional_research_state: List[str]
    market_recheck_completed_state: bool
    team_evaluation_state: EvaluationResult
    risk_analysis_state: EvaluationResult
    competition_evaluation_state: EvaluationResult
    investment_decision_state: InvestmentDecision
    domain_market_research_state: MarketResearch
