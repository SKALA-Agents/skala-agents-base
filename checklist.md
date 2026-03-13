# Agent Implementation Checklist

현재 코드베이스를 기준으로, 이미지에 정의된 에이전트 설계와 실제 구현 여부를 대조한 체크리스트입니다.

체크 기준:
- `[x]` 현재 코드에 해당 단계가 실제로 존재하고 실행 흐름에 연결되어 있음
- `[ ]` 현재 코드에 해당 단계가 없거나, placeholder 수준이라 설계 의도를 충족하지 못함

| 구현 | 순서 | Agents | 역할 | 현재 구현 방식 | INPUT | OUTPUT | 비고 |
|---|---|---|---|---|---|---|---|
| [x] | 1 | 도메인 관련 시장성 조사 에이전트 | 반도체/AI 반도체 시장 조사 | `build_market_research()` + Tavily Web Search + 설계 문서 retrieval + 선택적 LLM | `domain` | `domain_market_research_state` | 현재는 `investment_pipeline/services.py`에서 구현 |
| [x] | 2 | 기업 조사 에이전트 (기술+시장성 등 모든 항목 조사) | 스타트업 기술력/시장성/경쟁/팀/리스크 조사 | `enrich_company_profile()` + `build_company_research()` + Tavily Web Search | 회사명, stage, 도메인 | 평가 단계에 들어갈 회사별 요약/참조/점수용 입력 | 현재는 회사별 웹 검색 결과를 profile과 research state로 반영 |
| [x] | 3 | 투자 판단 에이전트 | 종합 판단(리스트, ROI 등) | LangGraph `investment_supervisor` + `decision_node` | 평가 state들 | `investment_decision_state` | Supervisor 패턴으로 하위 평가 에이전트를 라우팅 |
| [x] | 3-a | 기술 평가 에이전트 | 기술력 평가 | LangGraph `technical_eval_node` + retrieval 기반 요약 + 점수화 | 회사 조사 결과, stage weight | `technical_evaluation_state` | 설계의 RAG를 단순 retrieval/증거기반 평가 형태로 구현 |
| [x] | 3-a-i | 추가 조사 → 다시 2-a | 기술 추가 조사 후 재평가 루프 | `technical_additional_research_node` 후 `investment_supervisor`가 다시 `technical_eval_node`로 라우팅 | 기술 평가 결과 | 추가 조사 메모 후 재평가 | 추가 조사 자체는 note 기반이며, 독립 Web Search 재호출까지는 아직 미구현 |
| [x] | 3-b | 시장성 평가 에이전트 | 시장성 평가 | LangGraph `market_eval_node` + 기업/시장 evidence 기반 점수화 | 회사 조사 결과, 시장 조사 결과 | `market_evaluation_state` | traction을 함께 반영 |
| [x] | 3-b-i | 추가 조사 → 다시 2-b | 시장성 추가 조사 후 재평가 루프 | `market_additional_research_node` 후 `investment_supervisor`가 다시 `market_eval_node`로 라우팅 | 시장성 평가 결과 | 추가 조사 메모 후 재평가 | 추가 조사 자체는 note 기반이며, 독립 Web Search 재호출까지는 아직 미구현 |
| [x] | 3-c | 팀 역량 평가 에이전트 | 팀 평가 | LangGraph `team_eval_node` | 회사 조사 결과 | `team_evaluation_state` | 팀 관련 evidence를 점수화 |
| [x] | 3-d | 리스크 분석 에이전트 | 리스크 평가 | LangGraph `risk_eval_node` | 회사 조사 결과 | `risk_analysis_state` | 실행/자금 리스크를 역점수 형태로 환산 |
| [x] | 3-e | 경쟁사 비교 및 평가 에이전트 | 경쟁 구도/차별성 분석 | LangGraph `competition_eval_node` | 회사 조사 결과, 시장 조사 결과 일부 | `competition_evaluation_state` | 별도 경쟁사 서브리서치 없이 evidence 요약 기반 |
| [ ] | 4 | 기업별 보고서 생성 에이전트 | 결과 요약 보고서 생성 | 별도 agent 없음 | - | - | 기업별 중간 보고서 agent/state는 없고 최종 보고서 렌더링 내부에 통합되어 있음 |
| [x] | 5 | 최종 보고서 생성 에이전트 | 최종 보고서 생성 | `render_top_report()` / `render_hold_report()` + CLI 출력 | 투자 판단 결과 목록 | 최종 Markdown 보고서 | 새 템플릿 기준 목차 반영 완료 |

## 코드 기준 근거

- 시장 조사: [investment_pipeline/services.py](/Users/angj/AngJ/SKALA_Project/new_mcp_project/investment_pipeline/services.py)
- 기업 조사/프로필 보강: [investment_pipeline/services.py](/Users/angj/AngJ/SKALA_Project/new_mcp_project/investment_pipeline/services.py)
- LangGraph 평가 플로우: [investment_pipeline/graph.py](/Users/angj/AngJ/SKALA_Project/new_mcp_project/investment_pipeline/graph.py)
- 최종 보고서 렌더링: [investment_pipeline/reporting.py](/Users/angj/AngJ/SKALA_Project/new_mcp_project/investment_pipeline/reporting.py)
- Tavily 검색 연동: [investment_pipeline/tavily.py](/Users/angj/AngJ/SKALA_Project/new_mcp_project/investment_pipeline/tavily.py)

## 요약

- 실질적으로 구현된 단계: `1, 2, 3, 3-a, 3-a-i, 3-b, 3-b-i, 3-c, 3-d, 3-e, 5`
- 부분 구현 또는 미구현 단계: `4`

다음 우선 보강 대상은 `4`이며, `3-a-i`, `3-b-i`는 현재 Supervisor 기반 재평가 루프까지는 구현되었지만 추가 Web Search 자동 재호출은 보강 여지가 있습니다.
