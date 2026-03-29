# Agent Pattern Architecture

## 1. Overview

이 시스템은 하나의 단일 에이전트 패턴만으로 구성되어 있지 않다.  
상위 제어 계층에는 `Supervisor pattern`이 적용되어 있고, 그 아래에는 `Multi-Agent 분업 구조`, `Agentic RAG`, `추가 조사 루프(Feedback Loop)`가 함께 결합된 형태로 구현되어 있다.

즉, 이 프로젝트는 **"Supervisor가 전체 평가 흐름을 통제하고, 각 전문 에이전트가 분업하며, 필요한 경우 RAG와 재조사 루프를 통해 근거를 보강하는 혼합형 에이전트 아키텍처"**로 이해하는 것이 가장 정확하다.

---

## 2. Pattern Summary

| 계층 | 적용 패턴 | 역할 |
| --- | --- | --- |
| 전체 파이프라인 | Workflow Orchestration | 기업 목록 조사, 시장 조사, 기업 분석, 랭킹, 보고서 생성 순서를 제어 |
| 투자 판단 서브그래프 | Supervisor Pattern | 어떤 평가 에이전트를 먼저/다음에 실행할지 상태 기반으로 라우팅 |
| 평가 단계 | Multi-Agent Pattern | 기술, 시장, 팀, 리스크, 경쟁 분석을 개별 에이전트가 분업 수행 |
| 검색 및 근거 수집 | Agentic RAG | 설계 문서 + 웹 리서치 결과를 검색해 평가에 필요한 근거를 공급 |
| 보강 조사 | Feedback Loop / Iterative Research | 기술/시장 정보가 부족하면 추가 조사 후 재평가 |
| 최종 리포트 | Synthesis Agent | 여러 평가 결과를 종합해 Markdown/PDF 보고서 생성 |

---

## 3. Where Each Pattern Is Used

### 3-1. Supervisor Pattern

적용 위치:
- [investment_pipeline/graph.py](/Users/angj/AngJ/SKALA_Project/new_mcp_project/investment_pipeline/graph.py)

핵심 노드:
- `investment_supervisor`

역할:
- 현재 state를 읽고 다음 실행 노드를 선택한다.
- 기술 평가, 시장 평가, 팀 평가, 리스크 분석, 경쟁 분석 중 아직 수행되지 않은 단계를 라우팅한다.
- 기술 점수나 시장 점수가 부족하면 추가 조사 노드로 보내고, 이후 다시 해당 평가 노드로 복귀시킨다.
- 모든 평가가 완료되면 `decision` 노드로 이동시킨다.

해석:
- 이 패턴은 "누가 다음에 일할지 결정하는 중앙 관리자" 역할에 해당한다.
- 따라서 이 시스템의 핵심 제어 패턴은 Supervisor Pattern이다.

---

### 3-2. Multi-Agent Pattern

적용 위치:
- [investment_pipeline/graph.py](/Users/angj/AngJ/SKALA_Project/new_mcp_project/investment_pipeline/graph.py)

전문 에이전트 역할에 해당하는 노드:
- `technical_eval`
- `market_eval`
- `team_eval`
- `risk_eval`
- `competition_eval`

역할:
- 기술력 평가 에이전트: 제품/기술 차별성 평가
- 시장성 평가 에이전트: 시장성과 트랙션 평가
- 팀 역량 평가 에이전트: 창업자 및 조직 실행력 평가
- 리스크 분석 에이전트: 실행/자금 조달 리스크 평가
- 경쟁 분석 에이전트: 경쟁 우위 및 방어력 평가

해석:
- 이 다섯 개 노드는 각각 독립적인 전문 평가자처럼 동작한다.
- 따라서 이 구조는 분업형 Multi-Agent Pattern을 포함하고 있다.

---

### 3-3. Agentic RAG Architecture

적용 위치:
- [investment_pipeline/retrieval.py](/Users/angj/AngJ/SKALA_Project/new_mcp_project/investment_pipeline/retrieval.py)
- [investment_pipeline/services.py](/Users/angj/AngJ/SKALA_Project/new_mcp_project/investment_pipeline/services.py)
- [investment_pipeline/serpapi.py](/Users/angj/AngJ/SKALA_Project/langchain_project_develop/investment_pipeline/serpapi.py)

구성 요소:
- `QdrantHybridKnowledgeBase`
- `DesignDocumentKnowledgeBase`
- `build_evidence_knowledge_base`
- SerpApi 웹 검색

역할:
- 설계 문서를 chunk 단위로 분할하고 Qdrant에 적재한다.
- 기업/시장 웹 리서치 결과를 별도 evidence knowledge base로 구축한다.
- `bge-m3` 기반 dense retrieval과 sparse lexical retrieval을 결합해 하이브리드 검색을 수행한다.
- 검색된 문서를 기반으로 시장 조사, 기업 조사, 평가 프롬프트에 근거를 공급한다.

해석:
- 이 구조는 단순 문서 조회를 넘어, "에이전트가 필요한 근거를 능동적으로 검색해 사용하는 RAG"라는 점에서 Agentic RAG에 해당한다.

---

### 3-4. Feedback Loop / Iterative Research Pattern

적용 위치:
- [investment_pipeline/graph.py](/Users/angj/AngJ/SKALA_Project/new_mcp_project/investment_pipeline/graph.py)

관련 노드:
- `technical_additional_research`
- `market_additional_research`

역할:
- 기술 평가 점수가 충분하지 않으면 기술 추가 조사 노드로 이동한다.
- 시장 평가 점수가 충분하지 않으면 시장 추가 조사 노드로 이동한다.
- 보강 조사 후 다시 기존 평가 노드로 돌아가 재평가를 수행한다.

해석:
- 이는 한 번 평가하고 끝나는 직렬 파이프라인이 아니라,
- 부족한 정보를 보완한 뒤 다시 판단하는 iterative loop 구조다.
- 설계 문서의 `추가 조사 -> 다시 평가` 흐름이 여기에 반영되어 있다.

---

### 3-5. Workflow Orchestration Pattern

적용 위치:
- [investment_pipeline/graph.py](/Users/angj/AngJ/SKALA_Project/new_mcp_project/investment_pipeline/graph.py)

상위 파이프라인 노드:
- `list_candidates`
- `market_research`
- `analyze_companies`
- `ranking`
- `top_report`
- `hold_report`

역할:
- 전체 투자심사 프로세스를 단계별 워크플로우로 연결한다.
- 기업별 분석 서브그래프를 호출하고 결과를 모은다.
- 점수 기준으로 Top3 또는 Hold branch를 선택한다.
- 최종 보고서를 Markdown/PDF로 생성한다.

해석:
- 이것은 개별 에이전트보다 상위 레벨에서 전체 업무 흐름을 제어하는 Workflow Orchestration에 해당한다.

---

### 3-6. Synthesis / Report Generation Pattern

적용 위치:
- [investment_pipeline/reporting.py](/Users/angj/AngJ/SKALA_Project/new_mcp_project/investment_pipeline/reporting.py)
- [investment_pipeline/report_polish.py](/Users/angj/AngJ/SKALA_Project/new_mcp_project/investment_pipeline/pdf_export.py)

역할:
- 평가 결과를 투자 추천 보고서 또는 투자 보류 보고서 형식으로 종합한다.
- 영어 목차를 유지하면서 본문은 한국어로 정리한다.
- Markdown과 PDF 결과물을 함께 생성한다.

해석:
- 이 계층은 여러 하위 에이전트의 결과를 하나의 최종 산출물로 통합하는 Synthesis Agent 역할에 가깝다.

---

## 4. Practical Interpretation

이 시스템을 한 문장으로 설명하면 아래와 같다.

> **상위에는 Supervisor가 있고, 내부에는 다섯 개의 전문 평가 에이전트가 분업하며, 필요한 경우 Agentic RAG와 추가 조사 루프를 통해 근거를 보강한 뒤, 최종적으로 보고서 생성 에이전트가 결과를 종합하는 혼합형 구조**

즉, 이 프로젝트는 다음 중 하나만 택한 구조가 아니다.

- Supervisor Pattern만 있는 시스템
- Multi-Agent Pattern만 있는 시스템
- RAG 시스템만 있는 구조

위 셋이 각각 다른 계층에서 함께 쓰이는 구조다.

---

## 5. Conclusion

현재 코드베이스의 에이전트 패턴은 다음처럼 정리할 수 있다.

1. 상위 제어는 `Supervisor Pattern`
2. 평가 수행은 `Multi-Agent Pattern`
3. 검색 근거 보강은 `Agentic RAG`
4. 부족 정보 보완은 `Feedback Loop`
5. 최종 산출물 작성은 `Synthesis Agent`

따라서 이 시스템은 **단일 패턴 구조가 아니라, 여러 에이전트 패턴이 계층적으로 결합된 하이브리드 아키텍처**다.
