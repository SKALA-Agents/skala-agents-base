from __future__ import annotations

import re
from typing import List
from urllib.parse import urlparse

from .config import settings
from .llm import llm_client
from .models import InvestmentDecision, MarketResearch, RankingSelection
from .prompts import HOLD_REPORT_DYNAMIC_PROMPT, TOP_REPORT_DYNAMIC_PROMPT


def _score_table(decisions: List[InvestmentDecision]) -> str:
    lines = [
        "| Company | Stage | Final Score | Recommendation |",
        "|---|---|---:|---|",
    ]
    for decision in decisions:
        lines.append(
            f"| {decision.company_name} | {decision.stage} | {decision.final_score} | {decision.recommendation} |"
        )
    return "\n".join(lines)


def _reference_section(decisions: List[InvestmentDecision], market: MarketResearch) -> str:
    refs: List[str] = []
    for ref in market.references:
        if ref not in refs:
            refs.append(ref)
    for decision in decisions:
        for ref in decision.references:
            if ref not in refs:
                refs.append(ref)
    return _format_references(refs)


def _split_reference(raw: str) -> tuple[str, str]:
    if " - http" in raw:
        title, url = raw.rsplit(" - ", 1)
        return title.strip(), url.strip()
    if "http" in raw:
        parts = raw.split("http", 1)
        return parts[0].strip(" -"), "http" + parts[1].strip()
    return raw.strip(), ""


def _extract_year(text: str) -> str:
    full_date = re.search(r"(20\d{2}[-./]\d{2}[-./]\d{2})", text)
    if full_date:
        return full_date.group(1).replace(".", "-").replace("/", "-")
    match = re.search(r"(20\d{2})", text)
    return match.group(1) if match else "n.d."


def _domain_org(url: str) -> str:
    if not url:
        return "출처 미상"
    hostname = urlparse(url).netloc.lower().replace("www.", "")
    mapping = {
        "iea.org": "IEA",
        "deloitte.com": "Deloitte",
        "mckinsey.com": "McKinsey",
        "sec.gov": "SEC",
        "techcrunch.com": "TechCrunch",
        "cnbc.com": "CNBC",
        "prnewswire.com": "PR Newswire",
        "marketsandmarkets.com": "MarketsandMarkets",
        "precedenceresearch.com": "Precedence Research",
        "a16z.com": "Andreessen Horowitz",
        "groq.com": "Groq",
        "enchargeai.com": "EnCharge AI",
    }
    for key, value in mapping.items():
        if hostname.endswith(key):
            return value
    return hostname.split(".")[0].replace("-", " ").title()


def _reference_category(title: str, url: str) -> str:
    lower_title = title.lower()
    lower_url = url.lower()
    if any(
        keyword in lower_title
        for keyword in ["journal", "vol.", "doi", "학회", "연구", "논문"]
    ):
        return "학술 논문"
    if any(
        keyword in lower_title
        for keyword in ["outlook", "report", "보고서", "white paper", "whitepaper"]
    ) or any(
        domain in lower_url
        for domain in ["iea.org", "deloitte.com", "mckinsey.com", "sec.gov"]
    ):
        return "기관 보고서"
    return "웹페이지"


def _format_reference_item(raw: str) -> tuple[str, str]:
    title, url = _split_reference(raw)
    year = _extract_year(title + " " + url)
    org = _domain_org(url)
    category = _reference_category(title, url)

    if category == "학술 논문":
        formatted = f"- {org}({year}). {title}. {org}. {url}".strip()
    else:
        formatted = f"- {org}({year}). {title}. {org}. {url}".strip()
    return category, formatted


def _format_references(refs: List[str]) -> str:
    formatted_refs: List[str] = []
    for ref in refs:
        _, formatted = _format_reference_item(ref)
        if formatted not in formatted_refs:
            formatted_refs.append(formatted)
    return "\n".join(formatted_refs)


def _candidate_comparison(decisions: List[InvestmentDecision]) -> str:
    lines = [
        "| Company | Technology | Market | Team | Risk | Overall Assessment |",
        "|---|---|---|---|---|---|",
    ]
    for decision in decisions:
        lines.append(
            "| "
            + " | ".join(
                [
                    decision.company_name,
                    f"{decision.technical_evaluation.score}/5",
                    f"{decision.market_evaluation.score}/5",
                    f"{decision.team_evaluation.score}/5",
                    f"{decision.risk_analysis.score}/5",
                    decision.recommendation,
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _scorecard_table(decisions: List[InvestmentDecision]) -> str:
    lines = [
        "| Company | Technology | Market | Team | Competition | Risk | Final Score |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for decision in decisions:
        lines.append(
            f"| {decision.company_name} | "
            f"{decision.technical_evaluation.score} | "
            f"{decision.market_evaluation.score} | "
            f"{decision.team_evaluation.score} | "
            f"{decision.competition_evaluation.score} | "
            f"{decision.risk_analysis.score} | "
            f"{decision.final_score} |"
        )
    return "\n".join(lines)


def _executive_overview(decision: InvestmentDecision) -> str:
    return (
        f"{decision.company_name}는 {decision.stage} 단계의 AI 반도체 기업으로, "
        f"최종 DD-Worthiness Score {decision.final_score}점을 기록하며 {decision.recommendation} 의견을 받았다. "
        f"기술({decision.technical_evaluation.score}/5), 시장성({decision.market_evaluation.score}/5), "
        f"팀 역량({decision.team_evaluation.score}/5) 측면에서는 상대적으로 우수했지만, "
        f"실행 및 자금조달 리스크는 추가 검증이 필요한 상태다."
    )


def _technology_assessment(decision: InvestmentDecision) -> str:
    if decision.technical_evaluation.score >= 4:
        return (
            f"{decision.company_name}의 기술 평가는 긍정적이다. 제품 차별성과 아키텍처 경쟁력은 일정 수준 확인되며, "
            "향후에는 벤치마크, 고객 적용 사례, 양산 준비도 검증이 핵심 확인 포인트다."
        )
    return (
        f"{decision.company_name}의 기술 평가는 보수적으로 접근할 필요가 있다. "
        "기술 완성도와 제품 차별화를 뒷받침할 추가 검증 자료 확보가 요구된다."
    )


def _market_position(decision: InvestmentDecision) -> str:
    if decision.market_evaluation.score >= 4:
        return (
            f"{decision.company_name}는 AI 반도체 수요 확대 국면에서 시장 진입 가능성을 보유하고 있다. "
            "다만 실제 고객 전환, 매출 가시성, 파트너십 지속성은 후속 실사에서 점검해야 한다."
        )
    return (
        f"{decision.company_name}는 시장 기회는 존재하지만, 초기 고객 확보와 사업화 속도 측면에서 추가 확인이 필요하다."
    )


def _risk_assessment(decision: InvestmentDecision) -> str:
    if decision.risk_analysis.score <= 2:
        return (
            f"{decision.company_name}는 실행 리스크와 자금조달 리스크를 상대적으로 보수적으로 봐야 한다. "
            "양산 일정, 공급망 대응, 추가 자금 확보 계획을 구체적으로 검토할 필요가 있다."
        )
    return (
        f"{decision.company_name}의 리스크 수준은 관리 가능한 범위로 보이지만, "
        "시장 경쟁 심화와 고객 전환 속도는 지속적으로 모니터링해야 한다."
    )


def _serialize_report_context(decisions: List[InvestmentDecision], market: MarketResearch) -> str:
    blocks = [
        f"Domain: {market.domain}",
        f"Market Summary: {market.market_size_summary}",
        "Market Drivers:",
    ]
    blocks.extend(f"- {item}" for item in market.growth_drivers)
    blocks.append("Company Decision Summary:")
    for decision in decisions:
        blocks.extend(
            [
                f"- Company: {decision.company_name}",
                f"  Stage: {decision.stage}",
                f"  Final Score: {decision.final_score}",
                f"  Recommendation: {decision.recommendation}",
                f"  Technology Score: {decision.technical_evaluation.score}/5",
                f"  Market Score: {decision.market_evaluation.score}/5",
                f"  Team Score: {decision.team_evaluation.score}/5",
                f"  Competition Score: {decision.competition_evaluation.score}/5",
                f"  Risk Score: {decision.risk_analysis.score}/5",
                f"  Summary: {decision.summary}",
                f"  Technology Notes: {decision.technical_evaluation.summary}",
                f"  Market Notes: {decision.market_evaluation.summary}",
                f"  Team Notes: {decision.team_evaluation.summary}",
                f"  Competition Notes: {decision.competition_evaluation.summary}",
                f"  Risk Notes: {decision.risk_analysis.summary}",
            ]
        )
    return "\n".join(blocks)


def _invoke_dynamic_report(prompt: str, fallback_report: str, context: str) -> str:
    if not llm_client.available:
        return fallback_report
    response = llm_client.invoke_text(
        f"{prompt}\n\n[Required Markdown Structure]\n{fallback_report}\n\n[Context]\n{context}"
    )
    if not response:
        return fallback_report
    expected_headings = [
        "## 1. Executive Summary",
        "## 2. Market Overview",
        "## 3. Candidate Comparison",
        "## 4. Individual Company Analysis",
    ]
    if not all(heading in response for heading in expected_headings):
        return fallback_report
    return response.strip() + "\n"


def _render_top_report_fallback(
    ranking: RankingSelection,
    decisions: List[InvestmentDecision],
    market: MarketResearch,
) -> str:
    selected = [d for d in decisions if d.company_name in ranking.top_companies]
    selected.sort(key=lambda item: item.final_score, reverse=True)

    lines = [
        "# DD-Worthiness Investment Screening Report",
        "Startup Investment Evaluation Memo",
        "",
        "## 1. Executive Summary",
        (
            f"본 보고서는 {market.domain} 도메인 후보 기업을 DD-Worthiness Score 기준으로 평가하고, "
            f"`{settings.selective_dd_threshold}`점 이상을 기록한 기업 중 상위 {len(selected)}개사를 "
            "투자 추천 후보로 정리한 결과다."
        ),
        "",
        "| Rank | Company | Stage | DD Score | Recommendation |",
        "|---|---|---|---:|---|",
    ]
    for index, company in enumerate(selected, start=1):
        lines.append(
            f"| {index} | {company.company_name} | {company.stage} | {company.final_score} | {company.recommendation} |"
        )

    lines.extend(
        [
            "",
            "## 2. Market Overview",
            market.market_size_summary,
            "",
            "### Market Drivers",
        ]
    )
    lines.extend(f"- {driver}" for driver in market.growth_drivers)

    lines.extend(
        [
            "",
            "## 3. Candidate Comparison",
            _candidate_comparison(selected),
            "",
            "## 4. Individual Company Analysis",
        ]
    )

    for decision in selected:
        lines.extend(
            [
                "",
                f"### {decision.company_name}",
                "",
                "#### Executive Overview",
                _executive_overview(decision),
                "",
                "#### Technology Assessment",
                _technology_assessment(decision),
                "",
                "#### Market Position",
                _market_position(decision),
                "",
                "#### Risk Assessment",
                _risk_assessment(decision),
            ]
        )

    lines.extend(
        [
            "",
            "## 5. Scorecard Evaluation",
            _scorecard_table(selected),
            "",
            "## 6. DD-Worthiness Decision",
            _score_table(selected),
            "",
            (
                f"선정된 기업들은 모두 `{settings.selective_dd_threshold}`점 이상을 기록했으며, "
                "현 단계에서 Selective DD 진행 가치가 있는 후보로 판단된다."
            ),
            "",
            "## 7. Investment Recommendation",
        ]
    )

    if selected:
        best = selected[0]
        lines.extend(
            [
                (
                    f"현 시점 최우선 검토 대상은 **{best.company_name}**이다. "
                    f"{best.stage} 단계에서 {best.final_score}점을 기록했고, 기술 경쟁력과 시장 진입 가능성이 "
                    "상대적으로 우수한 편이다. 후속 실사에서는 고객 검증, 양산 실행력, 자금 집행 계획을 중점적으로 확인할 필요가 있다."
                ),
                "",
                "### REFERENCE",
                _reference_section(selected, market),
            ]
        )

    return "\n".join(lines) + "\n"


def render_top_report(
    ranking: RankingSelection,
    decisions: List[InvestmentDecision],
    market: MarketResearch,
) -> str:
    fallback_report = _render_top_report_fallback(ranking, decisions, market)
    selected = [d for d in decisions if d.company_name in ranking.top_companies]
    selected.sort(key=lambda item: item.final_score, reverse=True)
    context = _serialize_report_context(selected, market)
    return _invoke_dynamic_report(TOP_REPORT_DYNAMIC_PROMPT, fallback_report, context)


def _render_hold_report_fallback(
    ranking: RankingSelection,
    decisions: List[InvestmentDecision],
    market: MarketResearch,
) -> str:
    ordered = sorted(decisions, key=lambda item: item.final_score, reverse=True)
    lines = [
        "# DD-Worthiness Investment Screening Report",
        "Startup Investment Evaluation Memo",
        "",
        "## 1. Executive Summary",
        (
            f"본 보고서는 {market.domain} 도메인 후보 기업의 투자 적합성을 평가한 결과다. "
            f"이번 분석에서는 `{settings.selective_dd_threshold}`점 이상 기준을 충족한 기업이 없어 "
            "현 단계 판단은 투자 보류다."
        ),
        "",
        "## 2. Market Overview",
        market.market_size_summary,
        "",
        "### Market Drivers",
    ]
    lines.extend(f"- {driver}" for driver in market.growth_drivers)
    lines.extend(
        [
            "",
            "## 3. Candidate Comparison",
            _candidate_comparison(ordered),
            "",
            "## 4. Individual Company Analysis",
        ]
    )

    for decision in ordered:
        lines.extend(
            [
                "",
                f"### {decision.company_name}",
                "",
                "#### Executive Overview",
                _executive_overview(decision),
                "",
                "#### Technology Assessment",
                _technology_assessment(decision),
                "",
                "#### Market Position",
                _market_position(decision),
                "",
                "#### Risk Assessment",
                _risk_assessment(decision),
            ]
        )

    lines.extend(
        [
            "",
            "## 5. Scorecard Evaluation",
            _scorecard_table(ordered),
            "",
            "## 6. DD-Worthiness Decision",
            _score_table(ordered),
            "",
            "현재 DD 진행 대상에 해당하는 기업은 없으며, 전반적으로 기술 검증과 고객 traction 확인이 추가로 필요하다.",
            "",
            "## 7. Future Monitoring Candidates",
        ]
    )

    for decision in ordered[:3]:
        lines.append(
            f"- {decision.company_name}: {decision.weaknesses[0] if decision.weaknesses else decision.risk_analysis.summary}"
        )

    lines.extend(
        [
            "",
            "### REFERENCE",
            _reference_section(ordered, market),
        ]
    )
    return "\n".join(lines) + "\n"


def render_hold_report(
    ranking: RankingSelection,
    decisions: List[InvestmentDecision],
    market: MarketResearch,
) -> str:
    fallback_report = _render_hold_report_fallback(ranking, decisions, market)
    ordered = sorted(decisions, key=lambda item: item.final_score, reverse=True)
    context = _serialize_report_context(ordered, market)
    return _invoke_dynamic_report(HOLD_REPORT_DYNAMIC_PROMPT, fallback_report, context)
