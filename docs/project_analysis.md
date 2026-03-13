# 프로젝트 분석 보고서

## 1. 프로젝트 개요

이 프로젝트는 현재 작업 디렉터리의 Markdown 문서를 입력 데이터로 읽고, LangGraph 기반 멀티 에이전트 파이프라인을 통해 투자 분석 보고서를 생성하는 Python 프로젝트다. 산출물은 한국어 Markdown/JSON 형식으로 `outputs/` 디렉터리에 저장된다.

현재 구현 기준 핵심 목적은 다음과 같다.

- 특정 도메인에 대한 시장 분석 수행
- 입력 문서에서 회사명 후보 추출
- 회사별로 기술, 시장, 비즈니스, 팀, 리스크, 경쟁 구도를 평가
- 종합 점수 기반으로 추천 또는 보류 정책 결정
- 최종 투자 추천 보고서 또는 보류 보고서 생성

기본 도메인은 `AI Semiconductor`로 설정되어 있다.

## 2. 디렉터리 구조와 역할

프로젝트의 실제 역할 기준 구조는 다음과 같다.

```text
.
├── agents/
│   ├── __init__.py
│   ├── models.py
│   ├── service.py
│   └── README.md
├── data/
├── docs/
│   ├── architecture_mermaid.md
│   └── project_analysis.md
├── notebooks/
│   └── investment_report_service.ipynb
├── outputs/
├── prompts/
│   ├── business_evaluation_prompt.md
│   ├── competition_evaluation_prompt.md
│   ├── final_report_prompt.md
│   ├── hold_report_prompt.md
│   ├── market_evaluation_prompt.md
│   ├── ranking_prompt.md
│   ├── risk_evaluation_prompt.md
│   ├── team_evaluation_prompt.md
│   └── technology_evaluation_prompt.md
├── app.py
├── prompt_project_summary_ai_ready.md
├── README.md
└── requirements.txt
```

### 핵심 파일 설명

- `app.py`
  - CLI 성격의 얇은 진입점이다.
  - `InvestmentAnalysisService`를 생성하고 `run()`을 호출한 뒤 정책 결정과 출력 파일 경로를 출력한다.
- `agents/service.py`
  - 프로젝트의 실질적 핵심 구현이다.
  - 문서 탐색, 벡터스토어 구성, 프롬프트 조립, LangGraph 노드 구성, 정책 분기, 산출물 저장까지 모두 담당한다.
- `agents/models.py`
  - 설정값, 에이전트 응답 스키마, 그래프 상태를 Pydantic 모델로 정의한다.
- `notebooks/investment_report_service.ipynb`
  - 서비스 실행과 점검을 위한 노트북이다.
  - 실제 핵심 로직은 이미 `agents/` 패키지로 분리되어 있어, 노트북은 확인용 인터페이스에 가깝다.
- `prompts/*.md`
  - 각 에이전트 역할과 반환 형식을 정의하는 시스템 프롬프트 모음이다.
- `prompt_project_summary_ai_ready.md`
  - 현재 프로젝트에서 가장 중요한 입력 문서다.
  - 투자 평가 설계 초안, 상태(state) 정의, 그래프 설계 방향, 임베딩 모델 선택 이유가 들어 있다.
- `outputs/`
  - 이전 실행 결과가 누적되어 있으며, 실제 출력 포맷을 확인할 수 있는 디렉터리다.

## 3. 기술 스택

구현에 사용된 핵심 기술은 다음과 같다.

- Python 3.11 기준 개발
- LangChain
- LangGraph
- OpenAI Chat 모델 (`gpt-4.1-mini`)
- Hugging Face 임베딩 (`BAAI/bge-m3`)
- FAISS 벡터스토어
- Pydantic
- python-dotenv
- Jupyter Notebook

`requirements.txt`는 비교적 큰 환경 전체를 고정하고 있으며, 실제 런타임 핵심 의존성보다 노트북/실험용 패키지가 더 많이 포함되어 있다.

## 4. 실행 방식

### 4.1 진입점

실행 경로는 두 가지다.

1. `python app.py`
2. `notebooks/investment_report_service.ipynb` 실행

노트북과 Python 엔트리포인트 모두 최종적으로 `InvestmentAnalysisService`를 사용한다.

### 4.2 환경 변수

OpenAI API 키는 아래 이름 중 하나로 주입 가능하게 처리되어 있다.

- `OPENAI_API_KEY`
- `OPEN_AI_API_KEY`
- `OPEN_AI_API`

서비스 초기화 시 `.env`를 로드한 뒤 alias 이름이 있으면 `OPENAI_API_KEY`로 매핑한다.

## 5. 실제 데이터 입력 방식

이 프로젝트는 겉보기와 달리 `data/` 디렉터리를 기본 입력으로 사용하지 않는다. 실제 코드를 기준으로 입력 문서는 다음 조건으로 선택된다.

- `base_dir` 바로 아래에 있는 `*.md`
- 단, `README.md`는 제외

즉 현재 구조에서는 루트 디렉터리의 Markdown 파일이 핵심 입력이며, 실질적으로는 `prompt_project_summary_ai_ready.md`가 주요 분석 소스 역할을 한다.

이 점은 중요하다. README에 있는 설명만 보면 "현재 워크스페이스의 Markdown 파일"을 넓게 읽는 것처럼 보이지만, 실제 구현은 재귀 탐색이 아니며 `base_dir/*.md`만 읽는다.

## 6. 서비스 내부 동작 흐름

`agents/service.py` 기준으로 초기화와 실행 흐름은 아래와 같다.

### 6.1 초기화 단계

1. `.env` 로드
2. Markdown 소스 파일 탐색
3. Markdown 파일을 LangChain `Document`로 변환
4. `RecursiveCharacterTextSplitter`로 청크 분할
5. `BAAI/bge-m3` 임베딩 생성
6. FAISS 벡터스토어 생성
7. Retriever 생성
8. `gpt-4.1-mini` 기반 `ChatOpenAI` 생성
9. 프롬프트 템플릿 로드

### 6.2 실행 그래프

LangGraph 노드는 아래 순서로 연결된다.

1. `discover_sources`
2. `analyze_market`
3. `extract_companies`
4. `collect_company_contexts`
5. `investment_supervisor`
6. `rank_companies`
7. `apply_investment_policy`
8. `generate_investment_report` 또는 `generate_hold_report`

### 6.3 정책 분기

종합 점수가 `recommendation_threshold` 이상인 회사를 추천 후보로 간주한다.

- 기본 기준점: `20`
- 최대 추천 개수: `3`

추천 대상이 하나라도 있으면 `top3` 경로로 가고, 없으면 `hold` 경로로 간다.

## 7. 에이전트 설계 분석

### 7.1 현재 구현된 평가 축

현재 구현된 세부 평가 에이전트는 6개다.

- 기술 평가
- 시장성 평가
- 비즈니스 평가
- 팀 평가
- 리스크 평가
- 경쟁사 비교 평가

각 에이전트는 동일한 구조를 사용한다.

- 입력: `domain`, `company`, `context`
- 출력: `AgentEvaluation`
  - `company_name`
  - `score` (1~5)
  - `rationale`
  - `strengths`
  - `risks`
  - `diligence_questions`

즉 이 프로젝트는 "여러 종류의 프롬프트를 같은 실행 골격 위에 얹는 구조"로 설계되어 있다.

### 7.2 Supervisor의 성격

코드에 `investment_supervisor`라는 이름이 있지만, 실제로는 동적 오케스트레이션을 하는 Supervisor 에이전트라기보다는 6개의 평가 함수를 순차 호출하는 컨트롤러 함수에 가깝다.

즉 현재 구조는 다음에 가깝다.

- 진짜 멀티 에이전트 협업
- 보다는
- 순차 실행형 멀티 프롬프트 파이프라인

이 차이는 설계 문서와 실제 구현의 간극을 이해할 때 중요하다.

## 8. 상태 모델 구조

`GraphState`는 LangGraph 전체 파이프라인 상태를 한 객체에 모은 구조다. 주요 필드는 다음과 같다.

- `domain`
- `source_files`
- `market_context`
- `market_analysis`
- `companies`
- `company_contexts`
- `technology_evaluations`
- `market_evaluations`
- `business_evaluations`
- `team_evaluations`
- `risk_evaluations`
- `competition_evaluations`
- `evaluations`
- `selected_companies`
- `hold_companies`
- `policy_decision`
- `policy_reason`
- `final_report`
- `output_path`

설계 초안 문서에는 훨씬 더 세분화된 state 체계가 제시되어 있지만, 현재 구현은 하나의 `GraphState`에 필요한 정보를 누적하는 단순한 방식이다.

## 9. 프롬프트 설계 특징

`prompts/` 아래 프롬프트들은 공통적으로 다음 특성을 가진다.

- 한국어 출력 강제
- 제공된 문맥만 사용하도록 제한
- 구조화 출력 스키마 유도
- 투자 실사 관점의 항목별 체크리스트 제공

특히 랭킹 프롬프트는 6개 평가 결과 JSON을 다시 입력받아 최종 투자 논지와 종합 점수를 만들도록 설계돼 있다. 이 구조는 "세부 평가와 종합 판단의 분리"라는 장점이 있다.

최종 보고서 프롬프트는 투자 보고서와 보류 보고서를 분리해 각각 다른 문서 구조를 요구한다.

## 10. 산출물 구조

실행 결과는 `outputs/`에 여러 파일로 저장된다.

### 공통 저장 파일

- `market_analysis_<timestamp>.md`
- `evaluations_<timestamp>.json`
- `agent_evaluations_<timestamp>.json`
- `policy_decision_<timestamp>.json`

### 분기 저장 파일

- 추천 경로: `investment_report_<timestamp>.md`
- 보류 경로: `hold_report_<timestamp>.md`

즉 이 프로젝트는 최종 문서만 남기는 방식이 아니라, 중간 의사결정 산출물까지 파일로 남겨 디버깅 가능성을 높인다.

## 11. 실제 출력 결과에서 확인되는 특징

기존 `outputs/`를 보면 아래 특징이 드러난다.

- 추천 보고서와 보류 보고서가 모두 생성된 이력이 있다.
- 결과 JSON과 최종 Markdown 보고서가 함께 저장된다.
- 실제 소스 문서가 제한적이기 때문에 특정 기업명 하나에 분석이 집중되는 결과가 자주 나온다.
- 현재 출력 예시에서는 `BAAI`가 사실상 핵심 분석 대상으로 사용되었다.

이는 루트 Markdown 소스가 매우 제한적이기 때문이다. 즉 파이프라인 구조는 멀티 기업 평가를 지향하지만, 현재 데이터셋은 그 설계를 충분히 뒷받침하지 못한다.

## 12. 설계 문서와 실제 코드의 차이

이 프로젝트는 "아이디어 문서 -> 프로토타입 구현" 단계의 전형적인 형태다. 가장 큰 차이는 다음과 같다.

### 설계 문서가 지향하는 것

- 더 세분화된 state 체계
- 추가 조사(기술/시장) 루프
- 기업 조사 단계 분리
- 명시적 Top3 선정 정책
- 더 풍부한 보고서 구조

### 현재 코드가 구현한 것

- 단일 `GraphState`
- 루트 Markdown 기반 간단 RAG
- 구조화 출력 기반 6개 평가 에이전트
- 합산 점수 기반 단순 정책 분기
- 최종 보고서 자동 생성

즉 현재 구현은 "완성형 제품"보다는 "동작 가능한 1차 프로토타입"으로 보는 것이 정확하다.

## 13. 장점

### 13.1 구조가 단순하고 읽기 쉽다

핵심 로직이 `agents/service.py` 하나에 모여 있어 전체 흐름을 따라가기 쉽다.

### 13.2 프롬프트와 코드가 분리돼 있다

평가 기준 조정이 필요할 때 Python 코드를 크게 건드리지 않고 `prompts/`만 수정해도 된다.

### 13.3 구조화 출력 사용이 적절하다

`with_structured_output()`과 Pydantic 모델을 사용해 에이전트 응답 품질을 어느 정도 강제하고 있다.

### 13.4 중간 산출물 저장이 실용적이다

시장 분석, 세부 평가, 정책 결정 JSON을 남겨서 결과 검증과 디버깅이 쉽다.

### 13.5 노트북과 모듈 코드가 분리돼 있다

실험용 인터페이스와 재사용 가능한 서비스 로직이 어느 정도 분리되어 있다.

## 14. 한계와 리스크

### 14.1 입력 문서 탐색 범위가 매우 좁다

현재는 루트의 `*.md`만 읽는다. `data/`, `docs/`, 하위 폴더 문서는 기본적으로 분석에 쓰이지 않는다.

### 14.2 실제 입력 데이터와 프로젝트 문서가 섞여 있다

현재 주요 입력 소스는 투자 대상 기업 데이터셋이 아니라 설계 요약 문서에 가깝다. 따라서 모델은 "기업 팩트"보다 "프로젝트 설명 텍스트"를 근거로 평가를 만들 가능성이 높다.

### 14.3 점수 정책이 단순하다

6개 항목 단순 합산 구조이며 가중치가 없다. 도메인 특성이나 스타트업 stage별 차등 평가가 반영되지 않는다.

### 14.4 회사 추출 품질이 입력 문서에 크게 의존한다

회사명 추출 실패 시 정규식 fallback을 쓰는데, 이 방식은 약어나 기술 용어를 회사명으로 오인할 수 있다.

### 14.5 병렬화가 없다

회사 수가 늘어나면 6개 평가를 순차로 돌기 때문에 응답 속도와 비용 측면에서 비효율이 커질 수 있다.

### 14.6 테스트 코드가 없다

현재 저장소에는 자동화 테스트가 없고, 동작 검증은 노트북 실행 결과에 의존한다.

### 14.7 README 일부 설명이 구현과 완전히 일치하지 않는다

- `data/`가 입력 소스처럼 보이지만 실제 기본 입력이 아님
- "현재 워크스페이스의 Markdown"이라는 설명이 구현보다 넓다
- 아키텍처 문서 링크 경로가 현재 저장소 기준이 아니라 외부 절대경로를 가리킨다

## 15. 개선 우선순위 제안

실용성 기준으로 보면 다음 순서의 개선이 효과적이다.

1. 입력 문서 로딩 범위를 명확히 재설계
   - 예: `data/**/*.md` 또는 사용자가 지정한 소스 디렉터리만 읽기
2. 기업 조사용 원시 데이터와 프로젝트 설명 문서를 분리
3. 회사 추출 단계의 품질 개선
4. 점수 계산에 가중치 또는 stage별 rubric 도입
5. 평가 에이전트 호출 병렬화
6. 테스트 추가
   - 최소한 문서 발견, 정책 분기, 출력 파일 생성 검증
7. README와 실제 구현 동기화

## 16. 종합 판단

이 프로젝트는 "Markdown 기반 투자 분석 자동화"를 빠르게 검증하기 위한 LangGraph 프로토타입으로 평가할 수 있다. 구조는 비교적 깔끔하고, 프롬프트 분리와 구조화 출력, 중간 산출물 저장 방식은 실용적이다.

반면 현재 단계에서는 입력 데이터 설계가 가장 큰 제약이다. 실제 스타트업별 사실 데이터가 충분히 공급되지 않으면, 파이프라인이 아무리 그럴듯해도 결과 신뢰도는 낮아질 수밖에 없다. 따라서 이 프로젝트의 다음 핵심 과제는 에이전트 구조 고도화보다도 "신뢰 가능한 입력 코퍼스 구성"과 "입력 범위 제어"에 있다.

## 17. 결론 한 줄 요약

현재 저장소는 "멀티 에이전트 투자 분석 시스템의 1차 동작 프로토타입"이며, 핵심 강점은 구조 단순성과 실행 가능성이고, 핵심 약점은 실제 입력 데이터 설계와 평가 신뢰도다.
