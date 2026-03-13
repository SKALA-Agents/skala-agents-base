# RAG 인프라 구조화 메모

## 점검 결과
- 기존 상태에서 `config`, `service`는 존재했다.
- 하지만 PDF 읽기와 청킹이 서비스 내부에 섞여 있었고, 벡터 저장소 접근도 서비스에 직접 결합되어 있었다.
- 따라서 요구한 `config / service / loader / vectorstore` 계층 분리는 완전히 충족되지 않았다.

## 적용한 구조
- `config`
  - RAG 설정값과 빈 구성
- `loader`
  - PDF 문서 읽기 및 청킹 책임
- `vectorstore`
  - 벡터 저장소 load/save/search 책임
- `service`
  - 인덱싱 오케스트레이션, 검색 컨텍스트 생성, 챗봇 통합 책임

## 인덱싱 방식 결정
- 선택: 하이브리드
  - 기본 운영 모드: `LOAD_OR_INDEX`
  - 수동 재색인 API: `/api/rag/reindex`
  - 상태 확인 API: `/api/rag/status`
- 이유:
  - 개발 단계에서는 앱 시작 시 자동 준비가 편하다.
  - 운영 단계에서는 수동 재색인 제어가 필요하다.
  - 따라서 "자동 초기화만" 또는 "수동 배치만"보다 혼합 전략이 더 실용적이다.

## startup-mode 정의
- `LOAD_OR_INDEX`
  - 저장된 벡터 스토어와 메타데이터가 유효하면 load
  - 없거나 stale이면 reindex
- `REINDEX`
  - 앱 시작 때마다 강제 재색인
- `MANUAL`
  - 시작 시 인덱싱하지 않고 API로만 재색인

## 재색인 전략
- 선택: 메타데이터 비교 기반 재색인
- 비교 항목:
  - PDF SHA-256
  - 임베딩 모델 ID
  - 청킹 설정
    - `chunk-size`
    - `min-chunk-size-chars`
    - `min-chunk-length-to-embed`
    - `max-num-chunks`
    - `keep-separator`
- 이유:
  - 단순히 "파일 존재 여부"만 보면 문서 내용 변경을 감지할 수 없다.
  - 청킹 설정과 임베딩 모델이 바뀌어도 기존 인덱스는 의미가 달라진다.
  - 따라서 문서 + 청킹 + 임베딩 조합을 하나의 인덱스 버전으로 취급하는 것이 맞다.

## 현재 운영 권장값
- 개발: `LOAD_OR_INDEX`
- 실험/튜닝: `REINDEX`
- 운영: `MANUAL` + 배치/관리 API 연동
