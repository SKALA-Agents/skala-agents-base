# 프로젝트 개요 (Project Overview)

## 서비스 명칭
`SKALA 학습 도움 Chatbot` (**MCP Chatbot / SKALA 학습 도움 Chatbot**)

## 한 줄 요약
Spring AI 문서 기반으로 질의응답을 수행하고, OpenAI LLM + RAG(검색 증강)를 결합해 구조화된 챗 응답(요약, 핵심 포인트, 후속 질문, 출처)을 제공하는 MCP 기반 챗봇 서비스입니다.

## 개발 배경 및 목적
기본 응답 품질을 높이기 위해 단순한 LLM 질의에서 벗어나, Spring AI 공식 문서를 근거로 하는 RAG 기반 챗봇을 만들었습니다.  
목표는 다음과 같습니다.
- Spring AI 주제의 답변을 **문서 기반 근거**와 함께 제공
- 사용자 대화 맥락을 유지하면서 질의 품질을 지속적으로 개선
- 운영 관점에서 재색인/상태 점검이 가능한 구조로 구축

# 주요 기능 (Key Features)

## 핵심 기능 리스트
1. 대화형 질의응답
   - `/api/chat/messages`를 통해 질문 요청/응답 처리
   - 응답은 구조화 데이터(`title`, `summary`, `keyPoints`, `followUpQuestions`, `sources`)로 내려옴
2. RAG 기반 근거 제시
   - PDF 문서를 페이지/청크로 분할해 벡터 검색
   - 검색 결과를 LLM prompt에 결합해 출처 기반 답변 생성
3. 대화 이력 및 상태 관리
   - `conversationId` 기반 히스토리 저장/조회
   - In-memory chat memory를 함께 사용해 문맥 반영
4. 운영 API와 MCP 연동
   - RAG 상태 조회/재색인 API 제공
   - MCP Tool(`spring-ai-chat`) 및 Resource(`rag-status`, `rag-metadata`) 노출

## 사용자 흐름 (User Flow)
1. 사용자는 `/`에서 웹 UI 접속
2. 클라이언트는 `conversationId`를 생성/복원하고 `/api/chat/messages`로 기존 대화 이력을 조회
3. 사용자 질문 입력 후 `/api/chat/messages`(POST) 호출
4. 서버는 최근 대화 히스토리 + RAG 검색 결과를 결합해 LLM 호출
5. 결과를 구조화 객체로 반환
6. 화면에서 답변, 키포인트, 후속질문, 출처를 확인한 뒤 재질의 반복

## 서비스 화면
![service_ui.png](readme_image/service_ui.png)
# 기술 스택 (Tech Stack)

## Frontend
- HTML/CSS/JavaScript (정적 페이지)
- Vue 3 (CDN 기반)
- Thymeleaf 템플릿

## Backend
- Java 21
- Spring Boot 3.5.11
- Spring Web, Spring Data JPA, Validation
- Spring AI (`spring-ai-starter-mcp-server`, `spring-ai-starter-model-openai`)
- MCP 어노테이션 기반 기능 제공

## Database & Cache
- **Database**: H2 (메시지 저장)
  - 테이블: `chat_messages`
- **Cache/Session**: 별도 Redis/캐시 미사용
- **Vector Store**: Spring AI `SimpleVectorStore`(로컬 JSON 파일 기반 영속화)

## Infrastructure
- Gradle Wrapper 기반 빌드/실행
- OpenAI Chat API 연동
- MCP SSE 엔드포인트(`/mcp/sse`, `/mcp/message`) 사용

# 시스템 아키텍처 (System Architecture)

## 서비스 구조도
![service_architecture.png](readme_image/service_architecture.png)

## 데이터베이스 설계 (ERD)
![erdiagram.png](readme_image/erdiagram.png)

# 핵심 기술 구현 및 트러블슈팅 (Technical Challenges)

## 성능 최적화
- 벡터 검색은 `topK=4`, `similarity-threshold=0.30`로 상한을 두어 질의 비용 관리
- RAG 시작 모드는 `LOAD_OR_INDEX`로 기본 운영, 벡터 인덱스가 유효하지 않으면 자동 재색인
- 문서 변경 감지 시 `document SHA-256`, 임베딩 설정값(`chunk-size`, `min-chunk-size-chars`, `max-num-chunks` 등) 비교 후 갱신

## 동시성 제어
- 채팅 요청은 이벤트 + `@Async` 처리로 처리 스레드를 분리
- `ThreadPoolTaskExecutor`로 동시 요청량 제어
  - core 2 / max 8 / queue 100
- LLM 호출은 타임아웃과 재시도 정책(지수 백오프 + jitter) 적용

## 보안
- 입력 값 검증(`@NotBlank`) 및 전역 예외 응답 포맷 적용
- 타임아웃/외부 API 실패를 일관된 HTTP 상태로 변환
- 현재 인증/인가(예: JWT/Session)는 기본적으로 적용되지 않음
- H2 콘솔(`/h2-console`)은 개발 편의를 위해 노출되어 있어 운영 환경에서 접근 제어 필요

# 시작 가이드 (Getting Started)

## 사전 요구 사항
- Java 21
- Gradle Wrapper (프로젝트 내 포함)
- OpenAI API Key

## 설치 및 실행 방법
```bash
git clone <repo-url>
cd /Users/angj/AngJ/SKALA_Project/mcp_project/mini_project/mcpserver
./gradlew bootRun
```
- 브라우저: `http://localhost:8080`

## 환경 변수 설정
```env
OPEN_AI_KEY=your-openai-api-key
```

# API 명세서 (API Documentation)

## 주요 API 엔드포인트
- `GET /`  
  - Thymeleaf 기반 채팅 페이지 렌더링
- `GET /api/chat/health`  
  - 상태 조회 (`UP`)
- `GET /api/chat/messages?conversationId={id}`  
  - 대화 이력 조회 (최신 최대 20건)
- `POST /api/chat/messages`  
  - 질문 전송 및 구조화된 응답 반환
- `GET /api/rag/status`  
  - 벡터 인덱스 상태 조회
- `POST /api/rag/reindex`  
  - 벡터 인덱스 재생성(비동기 응답)
- `GET /h2-console`  
  - H2 관리 콘솔(개발용)
- `GET /mcp/sse`, `POST /mcp/message`  
  - MCP 통신 엔드포인트

### POST `/api/chat/messages` 예시
요청:
```json
{
  "question": "Spring AI가 뭐야?",
  "conversationId": "conv-123"
}
```

응답(요약):
```json
{
  "userMessageId": 1,
  "assistantMessageId": 2,
  "conversationId": "conv-123",
  "question": "Spring AI가 뭐야?",
  "answer": "Spring AI는 스프링 기반 AI 애플리케이션 통합 프레임워크입니다.",
  "structuredAnswer": {
    "title": "Spring AI 소개",
    "summary": "...",
    "keyPoints": ["..."],
    "followUpQuestions": ["..."],
    "sources": [
      { "source": "docs/spring_AI_v1.0.pdf", "pageNumber": 12, "snippet": "..." }
    ],
    "usedRag": true,
    "groundingNote": "Answer grounded with 1 retrieved chunk(s) from spring_AI_v1.0.pdf."
  },
  "answeredAt": "2026-03-13T..."
}
```
