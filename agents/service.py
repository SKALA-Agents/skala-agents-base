from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, StateGraph

from investment_pipeline.serpapi import serpapi_client
from investment_pipeline.tracing import (
    apply_langsmith_env,
    make_run_config,
    parse_tags,
)

from .models import (
    AgentEvaluation,
    CompanyEvaluation,
    CompanyList,
    EvaluationDimension,
    GraphState,
    ProductMarketEvaluation,
    ServiceConfig,
    TeamRiskCompetitionEvaluation,
)

HARDCODED_AI_SEMICONDUCTOR_COMPANIES = [
    "Groq",
    "Cerebras",
    "SambaNova Systems",
    "Tenstorrent",
    "SiMa.ai",
    "Hailo",
    "d-Matrix",
    "Axelera AI",
    "EnCharge AI",
    "Etched",
]


class InvestmentAnalysisService:
    def __init__(self, base_dir: Path, config: ServiceConfig | None = None):
        self.base_dir = base_dir.resolve()
        self.config = config or ServiceConfig()
        self.output_dir = self.base_dir / "outputs"
        self.prompt_dir = self.base_dir / "prompts"
        self._company_web_context_cache: dict[str, str] = {}
        self.output_dir.mkdir(parents=True, exist_ok=True)

        load_dotenv(self.base_dir / ".env")
        if not os.getenv("OPENAI_API_KEY"):
            aliased_key = os.getenv("OPEN_AI_API_KEY") or os.getenv("OPEN_AI_API")
            if aliased_key:
                os.environ["OPENAI_API_KEY"] = aliased_key
        apply_langsmith_env(
            enabled=self.config.langsmith_tracing,
            api_key=self.config.langsmith_api_key,
            project=self.config.langsmith_project,
            endpoint=self.config.langsmith_endpoint,
        )

        self.source_files = self.discover_markdown_files()
        self.documents = self.load_markdown_documents(self.source_files)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.config.embedding_model,
            encode_kwargs={"normalize_embeddings": True},
            query_encode_kwargs={"normalize_embeddings": True},
        )
        self.split_documents = []
        self.vectorstore = None
        self.retriever = None
        if self.documents:
            self.split_documents = RecursiveCharacterTextSplitter(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
            ).split_documents(self.documents)
        if self.split_documents:
            self.vectorstore = FAISS.from_documents(self.split_documents, self.embeddings)
            self.retriever = self.vectorstore.as_retriever(
                search_kwargs={"k": self.config.retrieval_k}
            ).with_config(
                make_run_config(
                    run_name="agents.retriever",
                    tags=parse_tags(self.config.langsmith_tags, "agents", "retriever"),
                )
            )
        self.llm = ChatOpenAI(
            model=self.config.llm_model,
            temperature=self.config.temperature,
        ).with_config(
            make_run_config(
                run_name="agents.chat_openai",
                tags=parse_tags(self.config.langsmith_tags, "agents", "llm"),
            )
        )
        self._build_prompts()

    @staticmethod
    def resolve_base_dir(cwd: Path | None = None) -> Path:
        cwd = (cwd or Path.cwd()).resolve()
        candidates = [cwd, cwd.parent]
        for candidate in candidates:
            docs_dir = candidate / "docs"
            if docs_dir.is_dir() and any(path.is_file() for path in docs_dir.rglob("*.md")):
                return candidate
        return cwd

    def load_prompt(self, name: str) -> str:
        return (self.prompt_dir / name).read_text(encoding="utf-8")

    def discover_markdown_files(self) -> list[Path]:
        return sorted(
            path
            for path in self.base_dir.glob(self.config.md_glob)
            if path.is_file() and path.name != "README.md"
        )

    @staticmethod
    def load_markdown_documents(paths: list[Path]) -> list[Document]:
        return [
            Document(
                page_content=path.read_text(encoding="utf-8"),
                metadata={"source": str(path), "file_name": path.name},
            )
            for path in paths
        ]

    @staticmethod
    def format_docs(docs: list[Document]) -> str:
        return "\n\n".join(
            f"Source: {doc.metadata['file_name']}\n{doc.page_content}" for doc in docs
        )

    @staticmethod
    def _format_web_evidence(company: str, evidence: list[object]) -> str:
        sections: list[str] = []
        seen_urls: set[str] = set()
        for item in evidence:
            title = getattr(item, "title", "") or company
            url = getattr(item, "url", "")
            source = getattr(item, "source", "web")
            content = re.sub(r"\s+", " ", getattr(item, "content", "") or "").strip()
            if not url or url in seen_urls or not content:
                continue
            seen_urls.add(url)
            sections.append(
                "\n".join(
                    [
                        f"Web Source: {source}",
                        f"Title: {title}",
                        f"URL: {url}",
                        f"Summary: {content[:500]}",
                    ]
                )
            )
            if len(sections) >= 6:
                break
        return "\n\n".join(sections)

    def _search_company_web_context(self, company: str) -> str:
        if company in self._company_web_context_cache:
            return self._company_web_context_cache[company]
        if not serpapi_client.available:
            self._company_web_context_cache[company] = ""
            return ""

        query_map = {
            "company": [f"{company} AI semiconductor startup overview funding"],
            "technology": [f"{company} AI accelerator architecture benchmark patent"],
            "market": [f"{company} customers design partner market traction"],
            "team": [f"{company} founders executives semiconductor AI startup"],
            "risk": [f"{company} foundry manufacturing supply chain risk funding"],
        }

        evidence: list[object] = []
        for category, queries in query_map.items():
            for query in queries:
                evidence.extend(serpapi_client.search(query, category=category, days=1825))

        formatted = self._format_web_evidence(company, evidence)
        self._company_web_context_cache[company] = formatted
        return formatted

    @staticmethod
    def fallback_company_candidates(text: str) -> list[str]:
        slash_candidates = re.findall(r"\b([A-Z]{3,})/[A-Za-z0-9.-]+\b", text)
        upper_candidates = re.findall(r"\b[A-Z]{3,}\b", text)
        camel_candidates = re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", text)
        candidates = slash_candidates + upper_candidates + camel_candidates
        blocked = {
            "AID",
            "PDF",
            "MIT",
            "TOP",
            "GPT",
            "RAG",
            "API",
            "LCEL",
            "SUMMARY",
            "REFERENCE",
        }
        cleaned: list[str] = []
        for candidate in candidates:
            if candidate in blocked:
                continue
            if candidate not in cleaned:
                cleaned.append(candidate)
        return cleaned[:10]

    def _build_prompts(self) -> None:
        self.product_market_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("product_market_evaluation_prompt.md")),
                ("human", "도메인: {domain}\n회사명: {company}\n문맥:\n{context}"),
            ]
        )
        self.team_risk_competition_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("team_risk_competition_evaluation_prompt.md")),
                ("human", "도메인: {domain}\n회사명: {company}\n문맥:\n{context}"),
            ]
        )
        self.ranking_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("ranking_prompt.md")),
                (
                    "human",
                    "도메인: {domain}\n회사명: {company}\n제품/시장 통합 평가:\n{product_market_json}\n팀/리스크/경쟁 통합 평가:\n{team_risk_competition_json}",
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
                    "You are a market research agent. Use only the provided context and summarize market size, growth, demand signals, policy context, and key risks in English.",
                ),
                ("human", "Domain: {domain}\nContext:\n{context}"),
            ]
        )
        self.company_extraction_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Extract startup or company names mentioned in the source context. Respond in JSON only and place a list of strings under the key 'companies'.",
                ),
                ("human", "Context:\n{context}"),
            ]
        )

    def discover_sources(self, state: GraphState) -> GraphState:
        state.source_files = [str(path) for path in self.source_files]
        return state

    def analyze_market(self, state: GraphState) -> GraphState:
        docs = []
        if self.retriever is not None:
            docs = self.retriever.invoke(
                f"{state.domain} market size growth demand regulation trends"
            )
        state.market_context = self.format_docs(docs)
        response = self.llm.invoke(
            self.market_prompt.format_messages(
                domain=state.domain,
                context=state.market_context,
            ),
            config=make_run_config(
                run_name="agents.market_analysis",
                tags=parse_tags(
                    self.config.langsmith_tags,
                    "agents",
                    "analysis",
                    "market",
                ),
                metadata={"domain": state.domain},
            ),
        )
        state.market_analysis = response.content
        return state

    def extract_companies(self, state: GraphState) -> GraphState:
        state.companies = HARDCODED_AI_SEMICONDUCTOR_COMPANIES.copy()
        return state

    def collect_company_contexts(self, state: GraphState) -> GraphState:
        company_contexts: dict[str, str] = {}
        for company in state.companies:
            docs = []
            if self.retriever is not None:
                docs = self.retriever.invoke(
                    f"{company} technology product traction patents market team competition risk"
                )
            local_context = self.format_docs(docs)
            web_context = self._search_company_web_context(company)
            company_contexts[company] = "\n\n".join(
                part for part in [local_context, web_context] if part
            )
        state.company_contexts = company_contexts
        return state

    @staticmethod
    def _dimension_to_agent_eval(company: str, dimension: EvaluationDimension) -> dict[str, Any]:
        return AgentEvaluation(
            company_name=company,
            score=dimension.score,
            rationale=dimension.rationale,
            strengths=dimension.strengths,
            risks=dimension.risks,
            diligence_questions=dimension.diligence_questions,
        ).model_dump()

    def _sync_legacy_dimension_fields(self, state: GraphState) -> None:
        technology: dict[str, dict[str, Any]] = {}
        market: dict[str, dict[str, Any]] = {}
        business: dict[str, dict[str, Any]] = {}
        team: dict[str, dict[str, Any]] = {}
        risk: dict[str, dict[str, Any]] = {}
        competition: dict[str, dict[str, Any]] = {}

        for company, result in state.product_market_evaluations.items():
            technology[company] = self._dimension_to_agent_eval(
                company,
                EvaluationDimension.model_validate(result["technology"]),
            )
            market[company] = self._dimension_to_agent_eval(
                company,
                EvaluationDimension.model_validate(result["market"]),
            )
            business[company] = self._dimension_to_agent_eval(
                company,
                EvaluationDimension.model_validate(result["business"]),
            )

        for company, result in state.team_risk_competition_evaluations.items():
            team[company] = self._dimension_to_agent_eval(
                company,
                EvaluationDimension.model_validate(result["team"]),
            )
            risk[company] = self._dimension_to_agent_eval(
                company,
                EvaluationDimension.model_validate(result["risk"]),
            )
            competition[company] = self._dimension_to_agent_eval(
                company,
                EvaluationDimension.model_validate(result["competition"]),
            )

        state.technology_evaluations = technology
        state.market_evaluations = market
        state.business_evaluations = business
        state.team_evaluations = team
        state.risk_evaluations = risk
        state.competition_evaluations = competition

    def run_combined_agent_for_company(
        self,
        *,
        domain: str,
        company: str,
        context: str,
        prompt: ChatPromptTemplate,
        schema: type[ProductMarketEvaluation] | type[TeamRiskCompetitionEvaluation],
        run_name: str,
        tag: str,
    ) -> dict[str, Any]:
        structured_llm = self.llm.with_structured_output(schema)
        result = structured_llm.invoke(
            prompt.format_messages(
                domain=domain,
                company=company,
                context=context,
            ),
            config=make_run_config(
                run_name=run_name,
                tags=parse_tags(
                    self.config.langsmith_tags,
                    "agents",
                    "evaluation",
                    tag,
                ),
                metadata={"domain": domain, "company": company},
            ),
        )
        return result.model_dump()

    def _combined_specs(
        self,
    ) -> list[tuple[str, ChatPromptTemplate, type[ProductMarketEvaluation] | type[TeamRiskCompetitionEvaluation], str, str]]:
        return [
            (
                "product_market_evaluations",
                self.product_market_prompt,
                ProductMarketEvaluation,
                "agents.product_market_evaluation",
                "product-market",
            ),
            (
                "team_risk_competition_evaluations",
                self.team_risk_competition_prompt,
                TeamRiskCompetitionEvaluation,
                "agents.team_risk_competition_evaluation",
                "team-risk-competition",
            ),
        ]

    def evaluate_company(self, state: GraphState, company: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
        context = state.company_contexts[company]
        product_market = self.run_combined_agent_for_company(
            domain=state.domain,
            company=company,
            context=context,
            prompt=self.product_market_prompt,
            schema=ProductMarketEvaluation,
            run_name="agents.product_market_evaluation",
            tag="product-market",
        )
        team_risk_competition = self.run_combined_agent_for_company(
            domain=state.domain,
            company=company,
            context=context,
            prompt=self.team_risk_competition_prompt,
            schema=TeamRiskCompetitionEvaluation,
            run_name="agents.team_risk_competition_evaluation",
            tag="team-risk-competition",
        )
        return company, product_market, team_risk_competition

    def investment_supervisor(self, state: GraphState) -> GraphState:
        product_market_results: dict[str, dict[str, Any]] = {}
        team_risk_competition_results: dict[str, dict[str, Any]] = {}
        max_workers = min(len(state.companies), 4) or 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self.evaluate_company, state, company)
                for company in state.companies
            ]
            for future in futures:
                company, product_market, team_risk_competition = future.result()
                product_market_results[company] = product_market
                team_risk_competition_results[company] = team_risk_competition
        state.product_market_evaluations = product_market_results
        state.team_risk_competition_evaluations = team_risk_competition_results
        self._sync_legacy_dimension_fields(state)
        return state

    def rank_companies(self, state: GraphState) -> GraphState:
        structured_llm = self.llm.with_structured_output(CompanyEvaluation)
        evaluations: list[dict[str, Any]] = []
        for company in state.companies:
            result = structured_llm.invoke(
                self.ranking_prompt.format_messages(
                    domain=state.domain,
                    company=company,
                    product_market_json=json.dumps(
                        state.product_market_evaluations[company],
                        ensure_ascii=False,
                        indent=2,
                    ),
                    team_risk_competition_json=json.dumps(
                        state.team_risk_competition_evaluations[company],
                        ensure_ascii=False,
                        indent=2,
                    ),
                ),
                config=make_run_config(
                    run_name="agents.rank_company",
                    tags=parse_tags(
                        self.config.langsmith_tags,
                        "agents",
                        "ranking",
                    ),
                    metadata={"domain": state.domain, "company": company},
                ),
            )
            item = result.model_dump()
            item["total_score"] = result.total_score
            evaluations.append(item)
        state.evaluations = sorted(
            evaluations,
            key=lambda item: item["total_score"],
            reverse=True,
        )
        return state

    def apply_investment_policy(self, state: GraphState) -> GraphState:
        selected = [
            item
            for item in state.evaluations
            if item["total_score"] >= self.config.recommendation_threshold
        ][: self.config.top_k_companies]
        hold = [item for item in state.evaluations if item not in selected]

        state.selected_companies = selected
        state.hold_companies = hold
        if selected:
            state.policy_decision = "top3"
            state.policy_reason = (
                f"총점 {self.config.recommendation_threshold}점 이상 기업을 최대 "
                f"{self.config.top_k_companies}개까지 추천 대상으로 선정했습니다."
            )
        else:
            state.policy_decision = "hold"
            state.policy_reason = (
                f"총점 {self.config.recommendation_threshold}점 이상 기업이 없어 "
                "전체 보류로 판단했습니다."
            )
        return state

    def route_after_policy(self, state: GraphState) -> str:
        return state.policy_decision or "hold"

    def _write_common_outputs(self, state: GraphState, timestamp: str) -> None:
        market_output_path = self.output_dir / f"market_analysis_{timestamp}.md"
        evaluations_output_path = self.output_dir / f"evaluations_{timestamp}.json"
        agent_output_path = self.output_dir / f"agent_evaluations_{timestamp}.json"
        policy_output_path = self.output_dir / f"policy_decision_{timestamp}.json"

        market_output_path.write_text(state.market_analysis, encoding="utf-8")
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
            ),
            config=make_run_config(
                run_name="agents.generate_investment_report",
                tags=parse_tags(
                    self.config.langsmith_tags,
                    "agents",
                    "report",
                    "top3",
                ),
                metadata={"selected_company_count": len(state.selected_companies)},
            ),
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
            ),
            config=make_run_config(
                run_name="agents.generate_hold_report",
                tags=parse_tags(
                    self.config.langsmith_tags,
                    "agents",
                    "report",
                    "hold",
                ),
                metadata={"hold_company_count": len(state.hold_companies)},
            ),
        )
        output_path = self.output_dir / f"hold_report_{timestamp}.md"
        output_path.write_text(report.content, encoding="utf-8")
        state.final_report = report.content
        state.output_path = str(output_path)
        return state

    def build_graph(self):
        workflow = StateGraph(GraphState)
        workflow.add_node("discover_sources", self.discover_sources)
        workflow.add_node("analyze_market", self.analyze_market)
        workflow.add_node("extract_companies", self.extract_companies)
        workflow.add_node("collect_company_contexts", self.collect_company_contexts)
        workflow.add_node("investment_supervisor", self.investment_supervisor)
        workflow.add_node("rank_companies", self.rank_companies)
        workflow.add_node("apply_investment_policy", self.apply_investment_policy)
        workflow.add_node("generate_investment_report", self.generate_investment_report)
        workflow.add_node("generate_hold_report", self.generate_hold_report)

        workflow.set_entry_point("discover_sources")
        workflow.add_edge("discover_sources", "analyze_market")
        workflow.add_edge("analyze_market", "extract_companies")
        workflow.add_edge("extract_companies", "collect_company_contexts")
        workflow.add_edge("collect_company_contexts", "investment_supervisor")
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

    def run(self, domain: str | None = None) -> GraphState:
        graph = self.build_graph()
        initial_state = GraphState(domain=domain or self.config.domain)
        result = graph.invoke(
            initial_state,
            config=make_run_config(
                run_name="agents.investment_analysis",
                tags=parse_tags(self.config.langsmith_tags, "agents", "graph"),
                metadata={"domain": initial_state.domain},
            ),
        )
        if isinstance(result, GraphState):
            return result
        return GraphState.model_validate(result)
