from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

from .config import settings
from .llm import llm_client
from .models import (
    CompanyProfile,
    CompanyResearch,
    CompanyResearchLLMOutput,
    CompanyWebResearch,
    EvaluationLLMOutput,
    EvaluationResult,
    MarketResearch,
    MarketResearchLLMOutput,
    MarketWebResearch,
    ResearchEvidence,
)
from .prompts import COMPANY_RESEARCH_PROMPT, EVALUATION_PROMPT, MARKET_PROMPT
from .retrieval import DesignDocumentKnowledgeBase, format_docs
from .scoring import weighted_score
from .tavily import tavily_client


_knowledge_base = None
_company_research_cache: Dict[str, CompanyWebResearch] = {}
_market_research_cache: Dict[str, MarketWebResearch] = {}


def get_knowledge_base() -> DesignDocumentKnowledgeBase | None:
    global _knowledge_base
    if _knowledge_base is not None:
        return _knowledge_base
    source_path = settings.default_design_doc_path
    if not source_path.exists():
        return None
    _knowledge_base = DesignDocumentKnowledgeBase.from_markdown(source_path)
    return _knowledge_base


def load_companies(path: Path) -> List[CompanyProfile]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [CompanyProfile.model_validate(item) for item in payload["companies"]]


def _compact_text(text: str, limit: int = 320) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")


def _merge_references(evidence: List[ResearchEvidence]) -> List[str]:
    refs: List[str] = []
    for item in evidence:
        ref = f"{item.title} - {item.url}"
        if ref not in refs:
            refs.append(ref)
    return refs


def _pick_summary(evidence: List[ResearchEvidence], fallback: str) -> str:
    for item in evidence:
        if item.content:
            return _compact_text(item.content)
    return fallback


def _score_from_evidence(evidence: List[ResearchEvidence], fallback: int) -> int:
    if not evidence:
        return fallback
    strong = 0
    medium = 0
    for item in evidence:
        text = item.content.lower()
        if any(
            keyword in text
            for keyword in [
                "customer",
                "partner",
                "founder",
                "patent",
                "benchmark",
                "funding",
                "pilot",
                "design partner",
                "foundry",
                "revenue",
            ]
        ):
            strong += 1
        elif len(text) > 80:
            medium += 1
    if strong >= 4:
        return 5
    if strong >= 2 or medium >= 4:
        return 4
    if strong >= 1 or medium >= 2:
        return 3
    return max(2, fallback - 1)


def _search_company(company: CompanyProfile) -> CompanyWebResearch:
    cache_key = f"{company.name}:{company.stage}"
    if cache_key in _company_research_cache:
        return _company_research_cache[cache_key]

    query_map = {
        "Team & Founders": [
            f"{company.name} founders executives semiconductor startup",
        ],
        "Market Attractiveness": [
            f"{company.name} ai semiconductor customers target market",
        ],
        "Technology & Product": [
            f"{company.name} AI accelerator architecture patent benchmark",
        ],
        "Traction & Commercialization": [
            f"{company.name} design partner pilot customers funding partnership",
        ],
        "Competitive Advantage": [
            f"{company.name} proprietary architecture patent moat",
        ],
        "Execution & Financing Risk": [
            f"{company.name} foundry manufacturing funding risk",
        ],
    }

    queries: List[str] = []
    evidence: List[ResearchEvidence] = []
    for category, category_queries in query_map.items():
        for query in category_queries:
            queries.append(query)
            evidence.extend(tavily_client.search(query, category=category, days=1825))

    researched = CompanyWebResearch(
        company_name=company.name,
        stage=company.stage,
        industry=company.industry,
        search_queries=queries,
        evidence=evidence,
    )
    _company_research_cache[cache_key] = researched
    return researched


def _search_market(domain: str) -> MarketWebResearch:
    if domain in _market_research_cache:
        return _market_research_cache[domain]

    queries = [
        f"{domain} market size growth report",
        f"{domain} data center accelerator demand report",
        f"{domain} venture capital evaluation framework deep tech",
    ]
    evidence: List[ResearchEvidence] = []
    for query in queries:
        category = "Industry" if "framework" not in query else "Framework"
        evidence.extend(tavily_client.search(query, category=category, days=3650))

    researched = MarketWebResearch(domain=domain, search_queries=queries, evidence=evidence)
    _market_research_cache[domain] = researched
    return researched


def build_market_research(domain: str) -> MarketResearch:
    kb = get_knowledge_base()
    context = format_docs(kb.search(f"{domain} market overview evaluation methodology")) if kb else ""
    market_live = _search_market(domain)
    live_context = "\n".join(
        f"<document><content>{item.content}</content><source>{item.url}</source></document>"
        for item in market_live.evidence[:6]
    )
    combined_context = "\n".join(part for part in [context, live_context] if part)
    if combined_context and llm_client.available:
        prompt = (
            f"{MARKET_PROMPT}\n\n"
            f"Domain: {domain}\n"
            f"Reference context:\n{combined_context}\n"
            "Return structured Korean output."
        )
        enriched = llm_client.invoke_structured(prompt, MarketResearchLLMOutput)
        if enriched:
            return MarketResearch(
                domain=domain,
                market_size_summary=enriched.market_size_summary,
                growth_drivers=enriched.growth_drivers,
                regulatory_context=enriched.regulatory_context,
                references=enriched.references,
            )

    return MarketResearch(
        domain=domain,
        market_size_summary=_pick_summary(
            [item for item in market_live.evidence if item.category == "Industry"],
            "AI semiconductor 시장은 생성형 AI 인프라 확장과 데이터센터 수요 증가에 힘입어 구조적 성장세를 보인다.",
        ),
        growth_drivers=[
            _pick_summary(market_live.evidence[0:1], "Generative AI 추론 수요 증가"),
            _pick_summary(market_live.evidence[1:2], "데이터센터 전력 효율 개선 압력"),
            _pick_summary(market_live.evidence[2:3], "GPU 외 대안 accelerator 수요 확대"),
        ],
        regulatory_context=[
            "첨단 반도체 공급망과 수출 규제 이슈가 존재한다.",
            "국가 단위 반도체 육성 정책과 보조금이 시장 진입 기회로 작동할 수 있다.",
        ],
        references=_merge_references(market_live.evidence)
        or [
            "McKinsey - Global Semiconductor Industry Reports",
            "NASA - Technology Readiness Level Framework",
            "Bessemer Venture Partners - Startup Investment Checklist",
        ],
    )


def build_company_research(company: CompanyProfile) -> CompanyResearch:
    kb = get_knowledge_base()
    context = format_docs(kb.search(f"{company.stage} startup evaluation technology market risk")) if kb else ""
    company_live = _search_company(company)
    live_context = "\n".join(
        f"<document><content>{item.content}</content><source>{item.url}</source></document>"
        for item in company_live.evidence[:8]
    )
    combined_context = "\n".join(part for part in [context, live_context] if part)
    if combined_context and llm_client.available:
        prompt = (
            f"{COMPANY_RESEARCH_PROMPT}\n\n"
            f"Company name: {company.name}\n"
            f"Stage: {company.stage}\n"
            f"Industry: {company.industry}\n"
            f"Business model: {company.business_model}\n"
            f"Product summary: {company.product_summary}\n"
            f"Customer focus: {company.customer_focus}\n"
            f"Moat: {company.moat}\n"
            f"Known risks: {', '.join(company.risks)}\n"
            f"Reference context:\n{combined_context}\n"
            "Return structured Korean output."
        )
        enriched = llm_client.invoke_structured(prompt, CompanyResearchLLMOutput)
        if enriched:
            return CompanyResearch(
                company_name=company.name,
                stage=company.stage,
                company_overview=enriched.company_overview,
                business_model_status=enriched.business_model_status,
                product_and_technology=enriched.product_and_technology,
                traction_summary=enriched.traction_summary,
                team_summary=enriched.team_summary,
                competition_summary=enriched.competition_summary,
                risk_summary=enriched.risk_summary,
                references=company.references,
            )

    by_category: Dict[str, List[ResearchEvidence]] = {}
    for item in company_live.evidence:
        by_category.setdefault(item.category, []).append(item)

    return CompanyResearch(
        company_name=company.name,
        stage=company.stage,
        company_overview=(
            _pick_summary(
                by_category.get("Technology & Product", []) + by_category.get("Market Attractiveness", []),
                f"{company.name}는 {company.product_summary or 'AI semiconductor 제품'}을 중심으로 {company.customer_focus or '목표 고객'}을 겨냥하는 {company.industry} 스타트업이다.",
            )
        ),
        business_model_status=_pick_summary(
            by_category.get("Traction & Commercialization", []),
            company.business_model,
        ),
        product_and_technology=_pick_summary(
            by_category.get("Technology & Product", []),
            company.technology_summary,
        ),
        traction_summary=_pick_summary(
            by_category.get("Traction & Commercialization", []),
            company.traction_summary,
        ),
        team_summary=_pick_summary(by_category.get("Team & Founders", []), company.team_summary),
        competition_summary=_pick_summary(
            by_category.get("Competitive Advantage", []),
            company.competition_summary,
        ),
        risk_summary=_pick_summary(
            by_category.get("Execution & Financing Risk", []),
            company.risk_summary,
        ),
        references=_merge_references(company_live.evidence) or company.references,
    )


def make_evaluation(
    *,
    category: str,
    signal: int,
    weight: float,
    summary: str,
    evidence: List[str],
    follow_up_questions: List[str],
) -> EvaluationResult:
    kb = get_knowledge_base()
    context = format_docs(kb.search(f"{category} evaluation score methodology")) if kb else ""
    if context and llm_client.available:
        prompt = (
            f"{EVALUATION_PROMPT}\n\n"
            f"Category: {category}\n"
            f"Signal score: {signal}/5\n"
            f"Weight: {weight}\n"
            f"Initial summary: {summary}\n"
            f"Evidence candidates: {', '.join(evidence)}\n"
            f"Reference context:\n{context}\n"
            "Return structured Korean output."
        )
        enriched = llm_client.invoke_structured(prompt, EvaluationLLMOutput)
        if enriched:
            summary = enriched.summary
            evidence = enriched.evidence or evidence
            follow_up_questions = enriched.follow_up_questions or follow_up_questions

    return EvaluationResult(
        category=category,
        score=signal,
        weighted_score=round(weighted_score(signal, weight), 1),
        summary=summary,
        evidence=evidence,
        follow_up_questions=follow_up_questions,
    )


def build_follow_up(signal: int, category: str) -> List[str]:
    if signal >= 4:
        return [f"{category} 관련 강점을 검증할 수 있는 실제 고객 또는 기술 증빙을 추가 확인한다."]
    if signal == 3:
        return [f"{category} 관련 불확실성을 해소할 추가 데이터와 인터뷰가 필요하다."]
    return [f"{category}는 핵심 리스크 영역이므로 정밀 실사 이전에 보강 증거 확보가 필요하다."]


def collect_references(company: CompanyProfile, market: MarketResearch) -> List[str]:
    live_company_refs = _merge_references(_search_company(company).evidence)
    merged = live_company_refs + company.references + market.references
    deduped: List[str] = []
    for item in merged:
        if item not in deduped:
            deduped.append(item)
    return deduped


def enrich_company_profile(company: CompanyProfile) -> CompanyProfile:
    web_research = _search_company(company)
    by_category: Dict[str, List[ResearchEvidence]] = {}
    for item in web_research.evidence:
        by_category.setdefault(item.category, []).append(item)

    return company.model_copy(
        update={
            "references": _merge_references(web_research.evidence) or company.references,
            "business_model": _pick_summary(
                by_category.get("Traction & Commercialization", []),
                company.business_model,
            ),
            "product_summary": _pick_summary(
                by_category.get("Technology & Product", []),
                company.product_summary or f"{company.name} AI semiconductor product",
            ),
            "customer_focus": _pick_summary(
                by_category.get("Market Attractiveness", []),
                company.customer_focus,
            ),
            "moat": _pick_summary(
                by_category.get("Competitive Advantage", []),
                company.moat,
            ),
            "team_signal": _score_from_evidence(
                by_category.get("Team & Founders", []),
                company.team_signal,
            ),
            "market_signal": _score_from_evidence(
                by_category.get("Market Attractiveness", []),
                company.market_signal,
            ),
            "technology_signal": _score_from_evidence(
                by_category.get("Technology & Product", []),
                company.technology_signal,
            ),
            "traction_signal": _score_from_evidence(
                by_category.get("Traction & Commercialization", []),
                company.traction_signal,
            ),
            "competition_signal": _score_from_evidence(
                by_category.get("Competitive Advantage", []),
                company.competition_signal,
            ),
            "risk_signal": max(
                1,
                min(
                    5,
                    _score_from_evidence(
                        by_category.get("Execution & Financing Risk", []),
                        company.risk_signal,
                    ),
                ),
            ),
            "team_summary": _pick_summary(
                by_category.get("Team & Founders", []),
                company.team_summary,
            ),
            "market_summary": _pick_summary(
                by_category.get("Market Attractiveness", []),
                company.market_summary,
            ),
            "technology_summary": _pick_summary(
                by_category.get("Technology & Product", []),
                company.technology_summary,
            ),
            "traction_summary": _pick_summary(
                by_category.get("Traction & Commercialization", []),
                company.traction_summary,
            ),
            "competition_summary": _pick_summary(
                by_category.get("Competitive Advantage", []),
                company.competition_summary,
            ),
            "risk_summary": _pick_summary(
                by_category.get("Execution & Financing Risk", []),
                company.risk_summary,
            ),
        }
    )


def comparison_row(decision_map: Dict[str, str], key: str) -> str:
    return decision_map.get(key, "-")
