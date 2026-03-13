from __future__ import annotations

import re
from typing import List
from urllib.parse import urlparse

from .config import settings
from .models import InvestmentDecision, MarketResearch, RankingSelection


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


def render_top_report(
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
            f"본 보고서는 {market.domain} 도메인 후보 기업을 대상으로 DD-Worthiness Score를 산정하고, "
            f"`{settings.selective_dd_threshold}점 이상` 기업 중 상위 {len(selected)}개 회사를 투자 추천 후보로 정리한 결과이다."
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
                decision.summary,
                "",
                "#### Technology Assessment",
                decision.technical_evaluation.summary,
                "",
                "#### Market Position",
                decision.market_evaluation.summary,
                "",
                "#### Risk Assessment",
                decision.risk_analysis.summary,
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
                f"상위 선정 기업은 모두 `{settings.selective_dd_threshold}점 이상`을 기록했으며, "
                "정밀 실사 진행 가치가 있는 Selective DD 이상 후보로 판단된다."
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
                    f"현 시점 최우선 검토 대상은 **{best.company_name}**이며, "
                    f"{best.technical_evaluation.summary} 또한 {best.market_evaluation.summary}"
                ),
                "",
                "### REFERENCE",
                _reference_section(selected, market),
            ]
        )

    return "\n".join(lines) + "\n"


def render_hold_report(
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
            f"본 보고서는 {market.domain} 도메인 후보 기업을 대상으로 투자 가능성을 평가한 결과를 정리한 것이다. "
            f"분석 결과 `{settings.selective_dd_threshold}점 이상` 기준을 충족한 기업이 없어 현재 단계에서는 투자 보류로 판단된다."
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
                decision.summary,
                "",
                "#### Technology Assessment",
                decision.technical_evaluation.summary,
                "",
                "#### Market Position",
                decision.market_evaluation.summary,
                "",
                "#### Risk Assessment",
                decision.risk_analysis.summary,
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
            "현재 기준에서는 DD 진행 대상 기업이 없으며, 전반적으로 추가적인 기술 검증과 고객 traction 확보가 더 필요하다.",
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
