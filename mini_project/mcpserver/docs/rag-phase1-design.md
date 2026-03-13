# RAG 1차 설계 메모

## 1. 문서 리더 선택
- 선택: `PagePdfDocumentReader`
- 이유:
  - PDF를 페이지 단위로 먼저 보존하면 추후 출처 표시에 유리하다.
  - Spring AI 공식 문서상 `PagePdfDocumentReader`는 페이지 단위 `Document`를 생성하는 기본 PDF 리더다.

## 2. 청킹 방식 선택
- 선택: `TokenTextSplitter`
- 설정:
  - `chunk-size=800`
  - `min-chunk-size-chars=350`
  - `min-chunk-length-to-embed=10`
  - `max-num-chunks=10000`
  - `keep-separator=true`
- 선택 이유:
  - Spring AI 공식 문서에서 토큰 기반 분할은 모델 컨텍스트 윈도우 관리에 직접 대응한다.
  - PDF 기술 문서는 문단 길이가 들쭉날쭉하므로, 글자 수 기반보다 토큰 기반이 더 일관적이다.
  - 800 토큰은 너무 작아 문맥이 끊기지 않으면서도, 검색 정밀도를 유지할 수 있는 보수적 초기값이다.
  - 먼저 페이지 단위로 읽고 이후 토큰 단위로 분할해 페이지 메타데이터를 유지한다.

## 3. 임베딩 모델 선택
- 선택: `TransformersEmbeddingModel`
- 모델: `sentence-transformers/all-MiniLM-L6-v2`
- 선택 이유:
  - Spring AI 공식 문서 기준 기본 ONNX 모델로 바로 사용할 수 있다.
  - 오픈소스 모델이라 1차 구현에서 임베딩 API 비용과 외부 종속성을 줄일 수 있다.
  - 문서 원문이 영어 중심인 Spring AI 문서이므로, 1차 구축에서 빠르게 검증하기 적합하다.
- 한계:
  - 한국어 질의 대응은 다국어 임베딩 모델보다 약할 수 있다.
  - 2차 개선에서는 `multilingual-e5` 계열이나 외부 벡터 DB 조합으로 교체를 검토할 수 있다.

## 4. 벡터 저장소 선택
- 선택: `SimpleVectorStore`
- 이유:
  - 별도 인프라 없이 로컬 파일 저장/복원이 가능하다.
  - H2는 애플리케이션 데이터 저장용으로 유지하고, 벡터 검색 책임은 별도 컴포넌트로 분리한다.
  - 1차 목표는 검색 품질 검증이지, 분산 운영이 아니다.
- 저장 경로:
  - `data/vector-store/spring-ai-vector-store.json`

## 5. 질의 처리 방식
- 흐름:
  1. 사용자 질문 수신
  2. 벡터 저장소에서 `topK=4`, `similarity-threshold=0.30`으로 관련 청크 검색
  3. 검색 결과를 컨텍스트로 조합
  4. 컨텍스트와 질문을 함께 OpenAI Chat 모델에 전달
  5. Structured Output으로 응답 생성

## 6. 왜 이 구성이 1차에 적합한가
- 로컬에서 바로 실행 가능하다.
- PDF 적재, 청킹, 임베딩, 검색, 응답 생성까지 RAG의 핵심 흐름을 모두 포함한다.
- 이후 벡터 저장소를 `PgVector`, `Qdrant`, `OpenSearch` 등으로 교체해도 서비스 레이어 변경을 최소화할 수 있다.
