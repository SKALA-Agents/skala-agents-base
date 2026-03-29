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
    GraphState,
    ServiceConfig,
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
        self.split_documents = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        ).split_documents(self.documents)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.config.embedding_model,
            encode_kwargs={"normalize_embeddings": True},
            query_encode_kwargs={"normalize_embeddings": True},
        )
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
            if any(
                path.is_file() and path.name != "README.md"
                for path in candidate.glob("*.md")
            ):
                return candidate
        return cwd

    def load_prompt(self, name: str) -> str:
        return (self.prompt_dir / name).read_text(encoding="utf-8")

    def discover_markdown_files(self) -> list[Path]:
        files = sorted(
            path
            for path in self.base_dir.glob(self.config.md_glob)
            if path.is_file() and path.name != "README.md"
        )
        if not files:
            raise FileNotFoundError(
                "No Markdown source files were found in the current directory."
            )
        return files

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
        self.technology_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("technology_evaluation_prompt.md")),
                ("human", "도메인: {domain}\n회사명: {company}\n문맥:\n{context}"),
            ]
        )
        self.market_eval_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("market_evaluation_prompt.md")),
                ("human", "도메인: {domain}\n회사명: {company}\n문맥:\n{context}"),
            ]
        )
        self.business_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("business_evaluation_prompt.md")),
                ("human", "도메인: {domain}\n회사명: {company}\n문맥:\n{context}"),
            ]
        )
        self.team_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("team_evaluation_prompt.md")),
                ("human", "도메인: {domain}\n회사명: {company}\n문맥:\n{context}"),
            ]
        )
        self.risk_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("risk_evaluation_prompt.md")),
                ("human", "도메인: {domain}\n회사명: {company}\n문맥:\n{context}"),
            ]
        )
        self.competition_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("competition_evaluation_prompt.md")),
                ("human", "도메인: {domain}\n회사명: {company}\n문맥:\n{context}"),
            ]
        )
        self.ranking_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("ranking_prompt.md")),
                (
                    "human",
                    "도메인: {domain}\n회사명: {company}\n기술 평가:\n{technology_json}\n시장성 평가:\n{market_json}\n비즈니스 평가:\n{business_json}\n팀 평가:\n{team_json}\n리스크 평가:\n{risk_json}\n경쟁사 비교 평가:\n{competition_json}",
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
                    "당신은 시장 조사 에이전트입니다. 제공된 문맥만 사용해 시장 규모, 성장성, 수요 신호, 정책 환경, 핵심 리스크를 한국어로 요약하세요.",
                ),
                ("human", "도메인: {domain}\n문맥:\n{context}"),
            ]
        )
        self.company_extraction_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "소스 문맥에 등장하는 스타트업 또는 회사명을 추출하세요. JSON으로만 응답하고, companies 키에 문자열 리스트를 넣으세요.",
                ),
                ("human", "문맥:\n{context}"),
            ]
        )

    def discover_sources(self, state: GraphState) -> GraphState:
        state.source_files = [str(path) for path in self.source_files]
        return state

    def analyze_market(self, state: GraphState) -> GraphState:
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

    def run_dimension_agent(
        self, state: GraphState, prompt: ChatPromptTemplate, field_name: str
    ) -> dict[str, dict[str, Any]]:
        structured_llm = self.llm.with_structured_output(AgentEvaluation)
        results: dict[str, dict[str, Any]] = {}
        dimension_name = field_name.removesuffix("_evaluations")
        for company in state.companies:
            context = state.company_contexts[company]
            result = structured_llm.invoke(
                prompt.format_messages(
                    domain=state.domain,
                    company=company,
                    context=context,
                ),
                config=make_run_config(
                    run_name=f"agents.{dimension_name}_evaluation",
                    tags=parse_tags(
                        self.config.langsmith_tags,
                        "agents",
                        "evaluation",
                        dimension_name,
                    ),
                    metadata={"domain": state.domain, "company": company},
                ),
            )
            results[company] = result.model_dump()
        return results

    def _dimension_specs(self) -> list[tuple[str, ChatPromptTemplate]]:
        return [
            ("technology_evaluations", self.technology_prompt),
            ("market_evaluations", self.market_eval_prompt),
            ("business_evaluations", self.business_prompt),
            ("team_evaluations", self.team_prompt),
            ("risk_evaluations", self.risk_prompt),
            ("competition_evaluations", self.competition_prompt),
        ]

    def evaluate_technology(self, state: GraphState) -> GraphState:
        state.technology_evaluations = self.run_dimension_agent(
            state, self.technology_prompt, "technology_evaluations"
        )
        return state

    def evaluate_market(self, state: GraphState) -> GraphState:
        state.market_evaluations = self.run_dimension_agent(
            state, self.market_eval_prompt, "market_evaluations"
        )
        return state

    def evaluate_business(self, state: GraphState) -> GraphState:
        state.business_evaluations = self.run_dimension_agent(
            state, self.business_prompt, "business_evaluations"
        )
        return state

    def evaluate_team(self, state: GraphState) -> GraphState:
        state.team_evaluations = self.run_dimension_agent(
            state, self.team_prompt, "team_evaluations"
        )
        return state

    def evaluate_risk(self, state: GraphState) -> GraphState:
        state.risk_evaluations = self.run_dimension_agent(
            state, self.risk_prompt, "risk_evaluations"
        )
        return state

    def evaluate_competition(self, state: GraphState) -> GraphState:
        state.competition_evaluations = self.run_dimension_agent(
            state, self.competition_prompt, "competition_evaluations"
        )
        return state

    def investment_supervisor(self, state: GraphState) -> GraphState:
        # 각 차원 평가는 동일한 회사 문맥을 읽기만 하므로 병렬 실행 후 결과만 합칩니다.
        dimension_specs = self._dimension_specs()
        with ThreadPoolExecutor(max_workers=len(dimension_specs)) as executor:
            future_map = {
                field_name: executor.submit(
                    self.run_dimension_agent,
                    state,
                    prompt,
                    field_name,
                )
                for field_name, prompt in dimension_specs
            }
            for field_name in [field for field, _ in dimension_specs]:
                setattr(state, field_name, future_map[field_name].result())
        return state

    def rank_companies(self, state: GraphState) -> GraphState:
        structured_llm = self.llm.with_structured_output(CompanyEvaluation)
        evaluations: list[dict[str, Any]] = []
        for company in state.companies:
            result = structured_llm.invoke(
                self.ranking_prompt.format_messages(
                    domain=state.domain,
                    company=company,
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
