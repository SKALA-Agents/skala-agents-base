from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, StateGraph

from .models import (
    AgentEvaluation,
    CompanyEvaluation,
    CompanyResearch,
    GraphState,
    ResearchSource,
    ServiceConfig,
)


class InvestmentAnalysisService:
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    )
    SEARCH_ENDPOINTS = (
        "https://html.duckduckgo.com/html/?q={query}",
        "https://lite.duckduckgo.com/lite/?q={query}",
    )

    def __init__(self, base_dir: Path, config: ServiceConfig | None = None):
        self.base_dir = base_dir.resolve()
        self.config = config or ServiceConfig()
        self.output_dir = self.base_dir / "outputs"
        self.prompt_dir = self.base_dir / "prompts"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        load_dotenv(self.base_dir / ".env")
        if not os.getenv("OPENAI_API_KEY"):
            aliased_key = os.getenv("OPEN_AI_API_KEY") or os.getenv("OPEN_AI_API")
            if aliased_key:
                os.environ["OPENAI_API_KEY"] = aliased_key

        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.config.embedding_model,
            encode_kwargs={"normalize_embeddings": True},
            query_encode_kwargs={"normalize_embeddings": True},
        )
        self.llm = ChatOpenAI(
            model=self.config.llm_model,
            temperature=self.config.temperature,
        )
        self.http = requests.Session()
        self.http.headers.update({"User-Agent": self.USER_AGENT})
        self._build_prompts()

    @staticmethod
    def resolve_base_dir(cwd: Path | None = None) -> Path:
        return (cwd or Path.cwd()).resolve()

    def load_prompt(self, name: str) -> str:
        return (self.prompt_dir / name).read_text(encoding="utf-8")

    @staticmethod
    def format_docs(docs: list[Document]) -> str:
        return "\n\n".join(
            f"Source: {doc.metadata.get('source', 'unknown')}\n{doc.page_content}"
            for doc in docs
        )

    @staticmethod
    def _clean_text(text: str) -> str:
        return " ".join(text.split())

    def _build_prompts(self) -> None:
        self.research_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "당신은 AI 반도체 투자 리서치 애널리스트입니다. 제공된 웹 조사 문맥만 사용해 "
                        "회사의 핵심 정보를 구조화하세요. 근거가 부족한 항목은 '정보 부족'이라고 쓰고, "
                        "모든 답변은 한국어로 작성하세요."
                    ),
                ),
                (
                    "human",
                    "도메인: {domain}\n회사명: {company}\n웹 조사 문맥:\n{context}",
                ),
            ]
        )
        self.technology_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("technology_evaluation_prompt.md")),
                (
                    "human",
                    "도메인: {domain}\n회사명: {company}\n회사 조사 결과:\n{research_json}\n문맥:\n{context}",
                ),
            ]
        )
        self.market_eval_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("market_evaluation_prompt.md")),
                (
                    "human",
                    "도메인: {domain}\n회사명: {company}\n회사 조사 결과:\n{research_json}\n문맥:\n{context}",
                ),
            ]
        )
        self.business_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("business_evaluation_prompt.md")),
                (
                    "human",
                    "도메인: {domain}\n회사명: {company}\n회사 조사 결과:\n{research_json}\n문맥:\n{context}",
                ),
            ]
        )
        self.team_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("team_evaluation_prompt.md")),
                (
                    "human",
                    "도메인: {domain}\n회사명: {company}\n회사 조사 결과:\n{research_json}\n문맥:\n{context}",
                ),
            ]
        )
        self.risk_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("risk_evaluation_prompt.md")),
                (
                    "human",
                    "도메인: {domain}\n회사명: {company}\n회사 조사 결과:\n{research_json}\n문맥:\n{context}",
                ),
            ]
        )
        self.competition_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("competition_evaluation_prompt.md")),
                (
                    "human",
                    "도메인: {domain}\n회사명: {company}\n회사 조사 결과:\n{research_json}\n문맥:\n{context}",
                ),
            ]
        )
        self.ranking_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("ranking_prompt.md")),
                (
                    "human",
                    "도메인: {domain}\n회사명: {company}\n회사 조사 결과:\n{research_json}\n기술 평가:\n{technology_json}\n시장성 평가:\n{market_json}\n비즈니스 평가:\n{business_json}\n팀 평가:\n{team_json}\n리스크 평가:\n{risk_json}\n경쟁사 비교 평가:\n{competition_json}",
                ),
            ]
        )
        self.report_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("final_report_prompt.md")),
                (
                    "human",
                    "도메인: {domain}\n시장 분석:\n{market_analysis}\n정책 결정: {policy_decision}\n정책 사유: {policy_reason}\n평가 결과 JSON:\n{evaluations_json}\n선정 기업 JSON:\n{selected_json}\n보류 기업 JSON:\n{hold_json}",
                ),
            ]
        )
        self.hold_report_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("hold_report_prompt.md")),
                (
                    "human",
                    "도메인: {domain}\n시장 분석:\n{market_analysis}\n정책 사유: {policy_reason}\n보류 기업 JSON:\n{hold_json}",
                ),
            ]
        )
        self.market_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "당신은 시장 조사 에이전트입니다. 제공된 웹 조사 문맥만 사용해 시장 규모, 성장성, 수요 신호, 정책 환경, 핵심 리스크를 한국어로 요약하세요.",
                ),
                ("human", "도메인: {domain}\n문맥:\n{context}"),
            ]
        )

    def _search_web(self, query: str, max_results: int) -> list[ResearchSource]:
        encoded_query = quote_plus(query)
        last_error: Exception | None = None
        for template in self.SEARCH_ENDPOINTS:
            search_url = template.format(query=encoded_query)
            try:
                response = self.http.get(
                    search_url,
                    timeout=self.config.web_request_timeout,
                )
                response.raise_for_status()
                results = self._parse_search_results(response.text, max_results)
                if results:
                    return results
            except requests.RequestException as exc:
                last_error = exc
                continue
        if last_error:
            print(f"[warn] web search failed for query '{query}': {last_error}")
        return []

    def _parse_search_results(
        self, html: str, max_results: int
    ) -> list[ResearchSource]:
        soup = BeautifulSoup(html, "html.parser")

        results: list[ResearchSource] = []
        for result in soup.select(".result"):
            title_node = result.select_one(".result__title")
            snippet_node = result.select_one(".result__snippet")
            link_node = result.select_one(".result__url") or result.select_one("a.result__a")
            anchor = result.select_one("a.result__a")
            if not title_node or not anchor:
                continue
            href = anchor.get("href", "").strip()
            if not href:
                continue
            title = self._clean_text(title_node.get_text(" ", strip=True))
            snippet = ""
            if snippet_node:
                snippet = self._clean_text(snippet_node.get_text(" ", strip=True))
            source_url = href
            if link_node and link_node.get_text(" ", strip=True).startswith("http"):
                source_url = link_node.get_text(" ", strip=True)
            results.append(
                ResearchSource(title=title, url=source_url, snippet=snippet)
            )
            if len(results) >= max_results:
                return results

        # DuckDuckGo lite has a simpler table-based layout.
        for anchor in soup.select("a"):
            href = anchor.get("href", "").strip()
            title = self._clean_text(anchor.get_text(" ", strip=True))
            if not href or not title:
                continue
            if "http" not in href:
                continue
            results.append(ResearchSource(title=title, url=href, snippet=""))
            if len(results) >= max_results:
                break
        return results

    def _fetch_page_text(self, url: str) -> str:
        response = self.http.get(url, timeout=self.config.web_request_timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = self._clean_text(soup.get_text(" ", strip=True))
        return text[: self.config.max_page_chars]

    def _build_research_documents(
        self, company: str, sources: list[ResearchSource]
    ) -> list[Document]:
        documents: list[Document] = []
        for source in sources[: self.config.max_research_urls_per_company]:
            try:
                page_text = self._fetch_page_text(source.url)
            except Exception:
                page_text = source.snippet or ""
            if not page_text:
                continue
            documents.append(
                Document(
                    page_content=page_text,
                    metadata={
                        "source": source.url,
                        "title": source.title,
                        "company": company,
                    },
                )
            )
        return documents

    def _company_vector_context(
        self, company: str, documents: list[Document], query: str
    ) -> str:
        if not documents:
            return ""
        split_documents = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        ).split_documents(documents)
        vectorstore = FAISS.from_documents(split_documents, self.embeddings)
        docs = vectorstore.as_retriever(
            search_kwargs={"k": self.config.retrieval_k}
        ).invoke(query)
        return self.format_docs(docs)

    def load_input_companies(self, state: GraphState) -> GraphState:
        companies = [company.strip() for company in self.config.companies if company.strip()]
        if not companies:
            raise ValueError("No input companies were provided.")
        state.input_companies = companies
        state.companies = companies
        return state

    def analyze_market(self, state: GraphState) -> GraphState:
        market_sources = self._search_web(
            f"{state.domain} market size growth demand regulation",
            self.config.web_search_results,
        )
        market_documents = self._build_research_documents(state.domain, market_sources)
        state.source_files = [source.url for source in market_sources]
        state.market_context = self._company_vector_context(
            state.domain,
            market_documents,
            f"{state.domain} market size growth demand regulation trends",
        )
        if not state.market_context:
            state.market_context = (
                "시장 분석을 위한 웹 검색 결과를 확보하지 못했습니다. "
                "현재 환경에서는 외부 검색 연결이 불안정하거나 차단되었을 수 있습니다."
            )
            state.market_analysis = (
                "시장 분석 정보 부족: 외부 웹 검색 결과를 확보하지 못해 시장 규모, 성장성, "
                "규제 동향에 대한 신뢰 가능한 요약을 생성하지 못했습니다."
            )
            return state

        response = self.llm.invoke(
            self.market_prompt.format_messages(
                domain=state.domain,
                context=state.market_context,
            )
        )
        state.market_analysis = response.content
        return state

    def research_companies(self, state: GraphState) -> GraphState:
        structured_llm = self.llm.with_structured_output(CompanyResearch)
        company_research: dict[str, dict[str, Any]] = {}
        company_contexts: dict[str, str] = {}

        for company in state.companies:
            sources = self._search_web(
                f"{company} AI semiconductor company product technology traction team funding",
                self.config.web_search_results,
            )
            documents = self._build_research_documents(company, sources)
            context = self._company_vector_context(
                company,
                documents,
                f"{company} product technology customers traction team competition risks",
            )
            if not context:
                fallback_lines = [
                    f"Source: {source.url}\n{source.title}\n{source.snippet}"
                    for source in sources
                ]
                context = "\n\n".join(fallback_lines)
            if not context:
                context = (
                    f"회사명: {company}\n"
                    "웹 검색 결과를 확보하지 못했습니다.\n"
                    "확인 가능한 외부 근거가 부족하므로 정보 부족 상태로 조사 결과를 작성해야 합니다."
                )

            result = structured_llm.invoke(
                self.research_prompt.format_messages(
                    domain=state.domain,
                    company=company,
                    context=context,
                )
            )
            normalized = result.model_dump()
            normalized["references"] = [source.model_dump() for source in result.references]
            if not normalized["references"]:
                normalized["references"] = [source.model_dump() for source in sources]
            company_research[company] = normalized
            company_contexts[company] = context

        state.company_research = company_research
        state.company_contexts = company_contexts
        return state

    def run_dimension_agent(
        self, state: GraphState, prompt: ChatPromptTemplate, field_name: str
    ) -> GraphState:
        structured_llm = self.llm.with_structured_output(AgentEvaluation)
        results: dict[str, dict[str, Any]] = {}
        for company in state.companies:
            context = state.company_contexts[company]
            research_json = json.dumps(
                state.company_research[company],
                ensure_ascii=False,
                indent=2,
            )
            result = structured_llm.invoke(
                prompt.format_messages(
                    domain=state.domain,
                    company=company,
                    research_json=research_json,
                    context=context,
                )
            )
            results[company] = result.model_dump()
        setattr(state, field_name, results)
        return state

    def evaluate_technology(self, state: GraphState) -> GraphState:
        return self.run_dimension_agent(
            state, self.technology_prompt, "technology_evaluations"
        )

    def evaluate_market(self, state: GraphState) -> GraphState:
        return self.run_dimension_agent(
            state, self.market_eval_prompt, "market_evaluations"
        )

    def evaluate_business(self, state: GraphState) -> GraphState:
        return self.run_dimension_agent(
            state, self.business_prompt, "business_evaluations"
        )

    def evaluate_team(self, state: GraphState) -> GraphState:
        return self.run_dimension_agent(state, self.team_prompt, "team_evaluations")

    def evaluate_risk(self, state: GraphState) -> GraphState:
        return self.run_dimension_agent(state, self.risk_prompt, "risk_evaluations")

    def evaluate_competition(self, state: GraphState) -> GraphState:
        return self.run_dimension_agent(
            state, self.competition_prompt, "competition_evaluations"
        )

    def investment_supervisor(self, state: GraphState) -> GraphState:
        # Future hook: insert a technology additional-research loop here when evidence is weak.
        state = self.evaluate_technology(state)
        # Future hook: insert a market additional-research loop here when evidence is weak.
        state = self.evaluate_market(state)
        state = self.evaluate_business(state)
        state = self.evaluate_team(state)
        state = self.evaluate_risk(state)
        state = self.evaluate_competition(state)
        return state

    def rank_companies(self, state: GraphState) -> GraphState:
        structured_llm = self.llm.with_structured_output(CompanyEvaluation)
        evaluations: list[dict[str, Any]] = []
        for company in state.companies:
            result = structured_llm.invoke(
                self.ranking_prompt.format_messages(
                    domain=state.domain,
                    company=company,
                    research_json=json.dumps(
                        state.company_research[company],
                        ensure_ascii=False,
                        indent=2,
                    ),
                    technology_json=json.dumps(
                        state.technology_evaluations[company],
                        ensure_ascii=False,
                        indent=2,
                    ),
                    market_json=json.dumps(
                        state.market_evaluations[company],
                        ensure_ascii=False,
                        indent=2,
                    ),
                    business_json=json.dumps(
                        state.business_evaluations[company],
                        ensure_ascii=False,
                        indent=2,
                    ),
                    team_json=json.dumps(
                        state.team_evaluations[company],
                        ensure_ascii=False,
                        indent=2,
                    ),
                    risk_json=json.dumps(
                        state.risk_evaluations[company],
                        ensure_ascii=False,
                        indent=2,
                    ),
                    competition_json=json.dumps(
                        state.competition_evaluations[company],
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
            )
            item = result.model_dump()
            item["total_score"] = result.total_score
            item["normalized_score"] = result.normalized_score
            item["company_research"] = state.company_research[company]
            evaluations.append(item)
        state.evaluations = sorted(
            evaluations,
            key=lambda item: item["normalized_score"],
            reverse=True,
        )
        return state

    def apply_investment_policy(self, state: GraphState) -> GraphState:
        selected = [
            item
            for item in state.evaluations
            if item["normalized_score"] >= self.config.recommendation_threshold
        ][: self.config.top_k_companies]
        hold = [item for item in state.evaluations if item not in selected]

        state.selected_companies = selected
        state.hold_companies = hold
        if selected:
            state.policy_decision = "top3"
            state.policy_reason = (
                f"100점 환산 점수 {self.config.recommendation_threshold}점 이상 기업이 "
                f"존재하여 상위 {self.config.top_k_companies}개를 추천 대상으로 선정했습니다."
            )
        else:
            state.policy_decision = "hold"
            state.policy_reason = (
                f"100점 환산 점수 {self.config.recommendation_threshold}점 이상 기업이 없어 "
                "전체 보류로 판단했습니다."
            )
        return state

    def route_after_policy(self, state: GraphState) -> str:
        return state.policy_decision or "hold"

    def _write_common_outputs(self, state: GraphState, timestamp: str) -> None:
        market_output_path = self.output_dir / f"market_analysis_{timestamp}.md"
        research_output_path = self.output_dir / f"company_research_{timestamp}.json"
        evaluations_output_path = self.output_dir / f"evaluations_{timestamp}.json"
        agent_output_path = self.output_dir / f"agent_evaluations_{timestamp}.json"
        policy_output_path = self.output_dir / f"policy_decision_{timestamp}.json"

        market_output_path.write_text(state.market_analysis, encoding="utf-8")
        research_output_path.write_text(
            json.dumps(state.company_research, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        evaluations_output_path.write_text(
            json.dumps(state.evaluations, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        agent_output_path.write_text(
            json.dumps(
                {
                    "technology": state.technology_evaluations,
                    "market": state.market_evaluations,
                    "business": state.business_evaluations,
                    "team": state.team_evaluations,
                    "risk": state.risk_evaluations,
                    "competition": state.competition_evaluations,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        policy_output_path.write_text(
            json.dumps(
                {
                    "decision": state.policy_decision,
                    "reason": state.policy_reason,
                    "selected_companies": state.selected_companies,
                    "hold_companies": state.hold_companies,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def generate_investment_report(self, state: GraphState) -> GraphState:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._write_common_outputs(state, timestamp)
        report = self.llm.invoke(
            self.report_prompt.format_messages(
                domain=state.domain,
                market_analysis=state.market_analysis,
                policy_decision=state.policy_decision,
                policy_reason=state.policy_reason,
                evaluations_json=json.dumps(
                    state.evaluations, ensure_ascii=False, indent=2
                ),
                selected_json=json.dumps(
                    state.selected_companies, ensure_ascii=False, indent=2
                ),
                hold_json=json.dumps(state.hold_companies, ensure_ascii=False, indent=2),
            )
        )
        output_path = self.output_dir / f"investment_report_{timestamp}.md"
        output_path.write_text(report.content, encoding="utf-8")
        state.final_report = report.content
        state.output_path = str(output_path)
        return state

    def generate_hold_report(self, state: GraphState) -> GraphState:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._write_common_outputs(state, timestamp)
        report = self.llm.invoke(
            self.hold_report_prompt.format_messages(
                domain=state.domain,
                market_analysis=state.market_analysis,
                policy_reason=state.policy_reason,
                hold_json=json.dumps(state.hold_companies, ensure_ascii=False, indent=2),
            )
        )
        output_path = self.output_dir / f"hold_report_{timestamp}.md"
        output_path.write_text(report.content, encoding="utf-8")
        state.final_report = report.content
        state.output_path = str(output_path)
        return state

    def build_graph(self):
        workflow = StateGraph(GraphState)
        workflow.add_node("load_input_companies", self.load_input_companies)
        workflow.add_node("analyze_market", self.analyze_market)
        workflow.add_node("research_companies", self.research_companies)
        workflow.add_node("investment_supervisor", self.investment_supervisor)
        workflow.add_node("rank_companies", self.rank_companies)
        workflow.add_node("apply_investment_policy", self.apply_investment_policy)
        workflow.add_node("generate_investment_report", self.generate_investment_report)
        workflow.add_node("generate_hold_report", self.generate_hold_report)

        workflow.set_entry_point("load_input_companies")
        workflow.add_edge("load_input_companies", "analyze_market")
        workflow.add_edge("analyze_market", "research_companies")
        workflow.add_edge("research_companies", "investment_supervisor")
        workflow.add_edge("investment_supervisor", "rank_companies")
        workflow.add_edge("rank_companies", "apply_investment_policy")
        workflow.add_conditional_edges(
            "apply_investment_policy",
            self.route_after_policy,
            {
                "top3": "generate_investment_report",
                "hold": "generate_hold_report",
            },
        )
        workflow.add_edge("generate_investment_report", END)
        workflow.add_edge("generate_hold_report", END)
        return workflow.compile()

    def run(
        self, companies: list[str] | None = None, domain: str | None = None
    ) -> GraphState:
        graph = self.build_graph()
        if companies is not None:
            self.config.companies = companies
        initial_state = GraphState(domain=domain or self.config.domain)
        result = graph.invoke(initial_state)
        if isinstance(result, GraphState):
            return result
        return GraphState.model_validate(result)
