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
from investment_pipeline.models import CompanyProfile
from investment_pipeline.scoring import STAGE_WEIGHTS, to_recommendation, weighted_score
from investment_pipeline.tracing import (
    apply_langsmith_env,
    make_run_config,
    parse_tags,
)

from .models import (
    CandidateCompanyFiltered,
    CandidateCompanyRaw,
    CompanyDecisionSummary,
    CompanyEvaluation,
    CompanyList,
    QueryDomain,
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

COMPANY_NAME_BLOCKLIST = {
    "ai",
    "startup",
    "startups",
    "semiconductor",
    "semiconductors",
    "chip",
    "chips",
    "accelerator",
    "accelerators",
    "hardware",
    "inference",
    "training",
    "funding",
    "companies",
    "company",
    "venture",
    "backed",
}

COMPANY_SNIPPET_BLOCKLIST = {
    "market report",
    "industry report",
    "wikipedia",
    "top startups",
    "list of",
    "ranking",
    "comparison",
    "news",
}


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
        self.company_profile_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("company_profile_enrichment_prompt.md")),
                (
                    "human",
                    "Domain: {domain}\nCompany: {company}\nExisting candidate evidence:\n{candidate_evidence}\nWeb evidence:\n{web_evidence}",
                ),
            ]
        )
        self.product_market_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("product_market_evaluation_prompt.md")),
                ("human", "Domain: {domain}\nCompany: {company}\nContext:\n{context}"),
            ]
        )
        self.team_risk_competition_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("team_risk_competition_evaluation_prompt.md")),
                ("human", "Domain: {domain}\nCompany: {company}\nContext:\n{context}"),
            ]
        )
        self.ranking_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("ranking_prompt.md")),
                (
                    "human",
                    "Domain: {domain}\nCompany: {company}\nStage: {stage}\nWeighted total score: {weighted_total_score}\nRecommendation: {recommendation}\nProduct/market evaluation:\n{product_market_json}\nTeam/risk/competition evaluation:\n{team_risk_competition_json}",
                ),
            ]
        )
        self.report_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("final_report_prompt.md")),
                (
                    "human",
                    "Domain: {domain}\nMarket analysis:\n{market_analysis}\nPolicy decision: {policy_decision}\nPolicy reason: {policy_reason}\nEvaluation JSON:\n{evaluations_json}\nSelected companies JSON:\n{selected_json}\nHold companies JSON:\n{hold_json}",
                ),
            ]
        )
        self.hold_report_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.load_prompt("hold_report_prompt.md")),
                (
                    "human",
                    "Domain: {domain}\nMarket analysis:\n{market_analysis}\nPolicy reason: {policy_reason}\nHold companies JSON:\n{hold_json}",
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
        self.domain_extraction_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Extract the investment domain from the user query. Return structured output only. Keep the domain concise, specific, and useful for startup discovery search.",
                ),
                ("human", "User query:\n{query}"),
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

    def extract_domain_from_query(self, query: str) -> str:
        normalized_query = re.sub(r"\s+", " ", query).strip()
        if not normalized_query:
            return self.config.domain
        structured_llm = self.llm.with_structured_output(QueryDomain)
        try:
            result = structured_llm.invoke(
                self.domain_extraction_prompt.format_messages(query=normalized_query),
                config=make_run_config(
                    run_name="agents.extract_domain_from_query",
                    tags=parse_tags(
                        self.config.langsmith_tags,
                        "agents",
                        "query-understanding",
                    ),
                    metadata={"query_length": len(normalized_query)},
                ),
            )
            extracted_domain = re.sub(r"\s+", " ", result.domain).strip()
            return extracted_domain or self.config.domain
        except Exception:
            return self.config.domain

    def analyze_market(self, state: GraphState) -> GraphState:
        docs = []
        if self.retriever is not None:
            docs = self.retriever.invoke(
                f"{state.domain} market size growth demand regulation trends"
            )
        market_context = self.format_docs(docs)
        response = self.llm.invoke(
            self.market_prompt.format_messages(
                domain=state.domain,
                context=market_context,
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

    def discover_candidate_companies(self, state: GraphState) -> GraphState:
        if not serpapi_client.available:
            state.candidate_companies_raw = []
            return state

        discovery_hint = state.user_query.strip() or state.domain
        queries = [
            f"{discovery_hint} startups AI chip accelerator companies",
            f"{discovery_hint} venture backed startups inference chip companies",
            f"{discovery_hint} startup funding AI hardware accelerator",
        ]
        evidence: list[object] = []
        for query in queries:
            try:
                evidence.extend(
                    serpapi_client.search(
                        query,
                        category="candidate-discovery",
                        days=1825,
                    )
                )
            except Exception:
                continue

        if not evidence:
            state.candidate_companies_raw = []
            return state

        discovery_context = "\n\n".join(
            "\n".join(
                [
                    f"Title: {getattr(item, 'title', '')}",
                    f"URL: {getattr(item, 'url', '')}",
                    f"Snippet: {getattr(item, 'content', '')}",
                ]
            )
            for item in evidence[:20]
        )
        structured_llm = self.llm.with_structured_output(CompanyList)
        try:
            result = structured_llm.invoke(
                self.company_extraction_prompt.format_messages(context=discovery_context),
                config=make_run_config(
                    run_name="agents.discover_candidate_companies",
                    tags=parse_tags(
                        self.config.langsmith_tags,
                        "agents",
                        "candidate-discovery",
                    ),
                    metadata={"domain": state.domain, "query_count": len(queries)},
                ),
            )
            discovered_names = result.companies
        except Exception:
            discovered_names = []

        raw_candidates: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for name in discovered_names:
            normalized = re.sub(r"\s+", " ", name).strip()
            if not normalized or normalized.lower() in seen_names:
                continue
            supporting_item = next(
                (
                    item
                    for item in evidence
                    if normalized.lower() in (getattr(item, "title", "") or "").lower()
                    or normalized.lower() in (getattr(item, "content", "") or "").lower()
                ),
                None,
            )
            raw_candidates.append(
                CandidateCompanyRaw(
                    name=normalized,
                    source_url=getattr(supporting_item, "url", "") if supporting_item else "",
                    source_title=getattr(supporting_item, "title", "") if supporting_item else "",
                    snippet=getattr(supporting_item, "content", "") if supporting_item else "",
                    discovery_query=queries[0],
                ).model_dump()
            )
            seen_names.add(normalized.lower())
        state.candidate_companies_raw = raw_candidates
        return state

    def extract_companies(self, state: GraphState) -> GraphState:
        if state.candidate_companies_filtered:
            state.companies = [
                item["name"]
                for item in state.candidate_companies_filtered[:10]
                if item.get("name")
            ]
        else:
            state.companies = HARDCODED_AI_SEMICONDUCTOR_COMPANIES.copy()
        return state

    def normalize_and_filter_candidates(self, state: GraphState) -> GraphState:
        filtered: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        for item in state.candidate_companies_raw:
            name = re.sub(r"\s+", " ", item.get("name", "")).strip(" -|:,;")
            snippet = (item.get("snippet", "") or "").strip()
            title = (item.get("source_title", "") or "").strip()
            normalized_key = name.lower()

            if not name or normalized_key in seen_names:
                continue
            if normalized_key in COMPANY_NAME_BLOCKLIST:
                continue
            if len(name) < 2 or len(name.split()) > 4:
                continue
            if any(token.isdigit() for token in name.split()):
                continue
            lowered_text = f"{title} {snippet}".lower()
            if any(blocked in lowered_text for blocked in COMPANY_SNIPPET_BLOCKLIST):
                continue
            if not re.search(r"[A-Za-z]", name):
                continue

            filtered.append(
                CandidateCompanyFiltered(
                    name=name,
                    source_url=item.get("source_url", ""),
                    source_title=title,
                    snippet=snippet,
                    discovery_query=item.get("discovery_query", ""),
                    filter_reason="matched startup-style candidate name from search evidence",
                ).model_dump()
            )
            seen_names.add(normalized_key)

        state.candidate_companies_filtered = filtered[:10]
        return state

    @staticmethod
    def _infer_stage_from_text(text: str) -> str:
        lowered = text.lower()
        if "series c" in lowered or "series d" in lowered or "growth stage" in lowered:
            return "Series C+"
        if "series b" in lowered:
            return "Series B"
        if "series a" in lowered:
            return "Series A"
        if "seed" in lowered or "pre-seed" in lowered:
            return "Seed"
        return "Series A"

    @staticmethod
    def _format_candidate_evidence(item: dict[str, Any] | None) -> str:
        if not item:
            return ""
        parts = [
            f"Title: {item.get('source_title', '')}",
            f"URL: {item.get('source_url', '')}",
            f"Snippet: {item.get('snippet', '')}",
            f"Filter reason: {item.get('filter_reason', '')}",
        ]
        return "\n".join(part for part in parts if part.strip())

    @staticmethod
    def _format_company_profile(profile: dict[str, Any]) -> str:
        references = "\n".join(f"- {url}" for url in profile.get("references", []))
        risks = "\n".join(f"- {risk}" for risk in profile.get("risks", []))
        tags = ", ".join(profile.get("tags", []))
        return "\n".join(
            [
                f"Company: {profile.get('name', '')}",
                f"Stage: {profile.get('stage', '')}",
                f"Industry: {profile.get('industry', '')}",
                f"Business model: {profile.get('business_model', '')}",
                f"Product summary: {profile.get('product_summary', '')}",
                f"Customer focus: {profile.get('customer_focus', '')}",
                f"Moat: {profile.get('moat', '')}",
                f"Tags: {tags}",
                f"Team signal: {profile.get('team_signal', '')}",
                f"Market signal: {profile.get('market_signal', '')}",
                f"Technology signal: {profile.get('technology_signal', '')}",
                f"Traction signal: {profile.get('traction_signal', '')}",
                f"Competition signal: {profile.get('competition_signal', '')}",
                f"Risk signal: {profile.get('risk_signal', '')}",
                "Risks:",
                risks,
                "References:",
                references,
            ]
        ).strip()

    def _fallback_company_profile(
        self,
        *,
        domain: str,
        company: str,
        candidate_item: dict[str, Any] | None,
        web_evidence: str,
    ) -> dict[str, Any]:
        combined_text = " ".join(
            [
                company,
                candidate_item.get("snippet", "") if candidate_item else "",
                candidate_item.get("source_title", "") if candidate_item else "",
                web_evidence,
            ]
        )
        references: list[str] = []
        if candidate_item and candidate_item.get("source_url"):
            references.append(candidate_item["source_url"])
        references.extend(re.findall(r"https?://\S+", web_evidence))
        unique_references: list[str] = []
        for reference in references:
            cleaned = reference.rstrip("),.]")
            if cleaned and cleaned not in unique_references:
                unique_references.append(cleaned)

        return CompanyProfile(
            name=company,
            industry=domain,
            stage=self._infer_stage_from_text(combined_text),
            business_model=(candidate_item or {}).get("snippet", "")[:240],
            product_summary=(candidate_item or {}).get("snippet", "")[:240],
            customer_focus="Insufficient evidence from current search results.",
            moat="Insufficient evidence from current search results.",
            risks=["Limited verified evidence available from current search results."],
            references=unique_references[:5],
            tags=["ai-semiconductor", "startup"],
        ).model_dump()

    def enrich_company_profiles(self, state: GraphState) -> GraphState:
        candidate_index = {
            item["name"]: item
            for item in state.candidate_companies_filtered
            if item.get("name")
        }
        profiles: dict[str, dict[str, Any]] = {}
        target_companies = state.companies[:10]

        def enrich_company_profile(company: str) -> tuple[str, dict[str, Any]]:
            candidate_item = candidate_index.get(company)
            candidate_evidence = self._format_candidate_evidence(candidate_item)
            web_evidence = self._search_company_web_context(company)
            structured_llm = self.llm.with_structured_output(CompanyProfile)
            try:
                profile = structured_llm.invoke(
                    self.company_profile_prompt.format_messages(
                        domain=state.domain,
                        company=company,
                        candidate_evidence=candidate_evidence,
                        web_evidence=web_evidence,
                    ),
                    config=make_run_config(
                        run_name="agents.enrich_company_profile",
                        tags=parse_tags(
                            self.config.langsmith_tags,
                            "agents",
                            "company-profile",
                        ),
                        metadata={"domain": state.domain, "company": company},
                    ),
                )
                return company, profile.model_dump()
            except Exception:
                return company, self._fallback_company_profile(
                    domain=state.domain,
                    company=company,
                    candidate_item=candidate_item,
                    web_evidence=web_evidence,
                )

        max_workers = min(len(target_companies), 4) or 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(enrich_company_profile, company)
                for company in target_companies
            ]
            for future in futures:
                company, profile = future.result()
                profiles[company] = profile

        state.company_profiles = profiles
        return state

    def collect_company_contexts(self, state: GraphState) -> GraphState:
        company_contexts: dict[str, str] = {}
        target_companies = [
            company for company in state.companies if company in state.company_profiles
        ] or state.companies
        for company in target_companies:
            docs = []
            if self.retriever is not None:
                docs = self.retriever.invoke(
                    f"{company} technology product traction patents market team competition risk"
                )
            local_context = self.format_docs(docs)
            web_context = self._search_company_web_context(company)
            profile_context = ""
            if company in state.company_profiles:
                profile_context = self._format_company_profile(state.company_profiles[company])
            company_contexts[company] = "\n\n".join(
                part
                for part in [profile_context, local_context, web_context]
                if part
            )
        state.company_contexts = company_contexts
        return state

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
        target_companies = [
            company for company in state.companies if company in state.company_profiles
        ] or state.companies
        max_workers = min(len(target_companies), 4) or 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self.evaluate_company, state, company)
                for company in target_companies
            ]
            for future in futures:
                company, product_market, team_risk_competition = future.result()
                product_market_results[company] = product_market
                team_risk_competition_results[company] = team_risk_competition
        state.product_market_evaluations = product_market_results
        state.team_risk_competition_evaluations = team_risk_competition_results
        return state

    @staticmethod
    def _normalize_stage(stage: str | None) -> str:
        if stage in STAGE_WEIGHTS:
            return stage
        return "Series A"

    def _build_company_scorecard(self, state: GraphState, company: str) -> dict[str, Any]:
        product_market = ProductMarketEvaluation.model_validate(
            state.product_market_evaluations[company]
        )
        team_risk_competition = TeamRiskCompetitionEvaluation.model_validate(
            state.team_risk_competition_evaluations[company]
        )
        profile = CompanyProfile.model_validate(state.company_profiles[company])
        stage = self._normalize_stage(profile.stage)
        weights = STAGE_WEIGHTS[stage]

        raw_scores = {
            "technology_score": product_market.technology.score,
            "market_score": product_market.market.score,
            "business_score": product_market.business.score,
            "team_score": team_risk_competition.team.score,
            "risk_score": team_risk_competition.risk.score,
            "competition_score": team_risk_competition.competition.score,
        }
        raw_total_score = sum(raw_scores.values())
        weighted_total_score = round(
            weighted_score(raw_scores["technology_score"], weights["technology"])
            + weighted_score(raw_scores["market_score"], weights["market"])
            + weighted_score(raw_scores["business_score"], weights["traction"])
            + weighted_score(raw_scores["team_score"], weights["team"])
            + weighted_score(raw_scores["risk_score"], weights["risk"])
            + weighted_score(raw_scores["competition_score"], weights["competition"])
        )

        return {
            "profile": profile,
            "stage": stage,
            "weights": weights,
            "raw_scores": raw_scores,
            "raw_total_score": raw_total_score,
            "weighted_total_score": weighted_total_score,
            "recommendation": to_recommendation(weighted_total_score),
        }

    def synthesize_company_decision(
        self, state: GraphState, company: str
    ) -> dict[str, Any]:
        scorecard = self._build_company_scorecard(state, company)
        structured_llm = self.llm.with_structured_output(CompanyDecisionSummary)
        summary = structured_llm.invoke(
            self.ranking_prompt.format_messages(
                domain=state.domain,
                company=company,
                stage=scorecard["stage"],
                weighted_total_score=scorecard["weighted_total_score"],
                recommendation=scorecard["recommendation"],
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
                run_name="agents.summarize_company_decision",
                tags=parse_tags(
                    self.config.langsmith_tags,
                    "agents",
                    "decision-summary",
                ),
                metadata={
                    "domain": state.domain,
                    "company": company,
                    "stage": scorecard["stage"],
                    "weighted_total_score": scorecard["weighted_total_score"],
                },
            ),
        )
        evaluation = CompanyEvaluation(
            company_name=company,
            stage=scorecard["stage"],
            recommendation=scorecard["recommendation"],
            thesis=summary.thesis,
            technology_score=scorecard["raw_scores"]["technology_score"],
            market_score=scorecard["raw_scores"]["market_score"],
            business_score=scorecard["raw_scores"]["business_score"],
            team_score=scorecard["raw_scores"]["team_score"],
            risk_score=scorecard["raw_scores"]["risk_score"],
            competition_score=scorecard["raw_scores"]["competition_score"],
            raw_total_score=scorecard["raw_total_score"],
            weighted_total_score=scorecard["weighted_total_score"],
            strengths=summary.strengths,
            risks=summary.risks,
            diligence_questions=summary.diligence_questions,
        )
        item = evaluation.model_dump()
        item["total_score"] = evaluation.total_score
        return item

    def synthesize_company_decisions(self, state: GraphState) -> GraphState:
        target_companies = [
            company for company in state.companies if company in state.company_profiles
        ] or state.companies
        max_workers = min(len(target_companies), 4) or 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self.synthesize_company_decision, state, company)
                for company in target_companies
            ]
            evaluations = [future.result() for future in futures]
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
                    "product_market": state.product_market_evaluations,
                    "team_risk_competition": state.team_risk_competition_evaluations,
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
        workflow.add_node("analyze_market", self.analyze_market)
        workflow.add_node("discover_candidate_companies", self.discover_candidate_companies)
        workflow.add_node("normalize_and_filter_candidates", self.normalize_and_filter_candidates)
        workflow.add_node("extract_companies", self.extract_companies)
        workflow.add_node("enrich_company_profiles", self.enrich_company_profiles)
        workflow.add_node("collect_company_contexts", self.collect_company_contexts)
        workflow.add_node("investment_supervisor", self.investment_supervisor)
        workflow.add_node("synthesize_company_decisions", self.synthesize_company_decisions)
        workflow.add_node("apply_investment_policy", self.apply_investment_policy)
        workflow.add_node("generate_investment_report", self.generate_investment_report)
        workflow.add_node("generate_hold_report", self.generate_hold_report)

        workflow.set_entry_point("analyze_market")
        workflow.add_edge("analyze_market", "discover_candidate_companies")
        workflow.add_edge("discover_candidate_companies", "normalize_and_filter_candidates")
        workflow.add_edge("normalize_and_filter_candidates", "extract_companies")
        workflow.add_edge("extract_companies", "enrich_company_profiles")
        workflow.add_edge("enrich_company_profiles", "collect_company_contexts")
        workflow.add_edge("collect_company_contexts", "investment_supervisor")
        workflow.add_edge("investment_supervisor", "synthesize_company_decisions")
        workflow.add_edge("synthesize_company_decisions", "apply_investment_policy")
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

    def run(self, query: str | None = None, domain: str | None = None) -> GraphState:
        graph = self.build_graph()
        normalized_query = re.sub(r"\s+", " ", (query or "")).strip()
        resolved_domain = domain or self.extract_domain_from_query(normalized_query)
        initial_state = {
            "domain": resolved_domain,
            "user_query": normalized_query,
        }
        result = graph.invoke(
            initial_state,
            config=make_run_config(
                run_name="agents.investment_analysis",
                tags=parse_tags(self.config.langsmith_tags, "agents", "graph"),
                metadata={
                    "domain": resolved_domain,
                    "user_query": normalized_query,
                },
            ),
        )
        if isinstance(result, GraphState):
            return result
        return GraphState.model_validate(result)
