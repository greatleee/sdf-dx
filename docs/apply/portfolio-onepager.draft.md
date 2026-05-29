# 모의 설비 기반 제조 라인 실시간 모니터링

**공장 설비의 신호를 수집하여 라인 상태와 OEE를 실시간으로 모니터링하는 E2E 데이터 파이프라인입니다.** 데이터 수집(MQTT·Sparkplug B)부터 대시보드 표출까지 전 구간을 직접 구축했으며, 제조 도메인 표준(ISA-95, ISO 22400)을 기반으로 설비 모델과 지표를 설계했습니다.

본 프로젝트는 SDF(Software Defined Factory)의 전체 범위 중 **데이터 흐름(Control → Data Platform → Application)과 미들웨어 통합**에 집중했습니다. 실제 하드웨어 제어 및 디지털 트윈 영역은 제외하고, 대규모 데이터 처리 아키텍처의 완성도를 높이는 데 주력했습니다.

> 지원: 현대자동차그룹 SDF Manufacturing DX · Senior Full-Stack Engineer
> 이창대 · cd.lee.dev@gmail.com · GitHub: github.com/greatleee/sdf-dx
>
> **사용 Tech Stack**
> · 엣지·OT: Kotlin · MQTT(Eclipse Paho v5) · Sparkplug B(Eclipse Tahu)
> · 메시징·브로커: HiveMQ(MQTT) · Redpanda(Kafka 호환)
> · 백엔드·저장: Python · FastAPI · TimescaleDB(PostgreSQL)
> · 프런트엔드: React · TypeScript
> · 계약·코드젠: OpenAPI 3.1 · Protobuf · JSON Schema
> · 인프라·품질: Docker Compose · import-linter · Konsist · ESLint(boundaries) · GitHub Actions

---

### Goal & Non-Goal

- **목표**: 설비 신호를 모아 라인 상태와 OEE를 실시간으로 보여주는 End-to-End 데이터 파이프라인을 점진적으로 구축합니다. SDF로 치면 데이터가 현장에서 화면까지 흐르는 경로(Control → Data Platform → Application)에 해당합니다.
  - **Phase 1** 단일 공장·단일 라인·5개 설비 기준의 End-to-End 파이프라인: `Kotlin 엣지(Sparkplug B·MQTT) → Kafka → Python 수집 → TimescaleDB → FastAPI → React`
  - **Phase 2** 여러 공장으로 확장하는 멀티테넌트(schema-per-tenant): 라인 구성·설비 타입·타임존·언어가 다른 공장들, 공장 온보딩과 인증.
  - **Phase 3** 24/7 운영을 가정한 관측가능성 · 성능 · CI/CD (목표치: 1,000 msg/sec 수집, API p99 200ms).
  - **Phase 4** 품질 · Predictive Maintenance 같은 다른 유즈케이스로 넓히는 포트-어댑터 구조. 이 단계에서 OPC UA(Machinery) 서버를 더해 설비 데이터의 *의미*까지 다룹니다.
- **비목표**: 소프트웨어로 설비를 제어하는 부분(가상 PLC), 디지털 트윈, 공장을 소프트웨어로 재구성하는 부분, 자동차 업계 데이터 표준(Catena-X 등). 실제 공장과 조직 없이는 흉내만 내게 되는 영역이라 처음부터 범위에서 뺐습니다.

### WHY

이 포트폴리오는 단순한 모니터링 시스템이 아니라, 시니어 개발자의 현대적인 문제 해결 방식을 증명하는 결과물입니다. ISA-95, ISO 22400 등 글로벌 표준을 분석해 낯선 제조 도메인을 아키텍처로 정확히 번역해 냈습니다. 동시에 Claude Code 등 AI 에이전트로 생산성을 극대화하되, 스키마 계약(Contract)과 순수 함수 기반의 테스트 코드를 선제적으로 작성해 AI의 궤도 이탈(LLM Drift)을 구조적으로 통제했습니다.

### HOW

- **도메인 표준 기반 아키텍처 설계**: 도메인 표준을 직접 조사하며 시스템의 경계를 명확히 정의했습니다. ISA-95를 기준으로 프로젝트를 L0~L2에 한정해 MES(L3)와의 결합도를 낮췄고, ISO 22400 OEE 계산 시 Performance 값이 이론상 1(100%)을 초과할 수 있는 엣지 케이스를 파악해 데이터 모델의 경계 조건에 안전하게 반영했습니다.

- **Contract-first 및 환각 방지**: API와 메시지 스키마를 코드보다 먼저 확정하고, 코드를 그 스키마에서 자동 생성합니다. 이는 시스템 간 결합도를 낮출 뿐만 아니라, AI가 존재하지 않는 API를 임의로 지어내는 Hallucination을 구조적으로 막습니다.

- **순수 함수 도메인과 테스트 앵커링(Functional Core)**: 핵심 비즈니스 로직은 외부 의존성이 없는 순수 함수로 구성해 mock 없는 단위 테스트를 구축했습니다. AI가 코드를 작성하거나 리팩토링할 때 본래의 의도에서 벗어나는 LLM Drift를 방지하는 튼튼한 앵커 역할을 합니다.

- **아키텍처 규칙 강제 (Architecture Linting)**: 백엔드뿐 아니라 프론트엔드까지 동일한 FC/IS 레이어 구조로 설계하고, 도메인이 인프라를 침범하지 못하도록 import-linter(Python)·Konsist(Kotlin)·ESLint(eslint-plugin-boundaries, TypeScript)를 도입해 세 언어 모두에서 아키텍처 경계 규칙을 CI에서 검사합니다. 사람이 리뷰에서 매번 확인하지 않아도 시스템의 구조적 무결성이 유지됩니다.

### Current & Next
Phase 1의 아키텍처 결정, 스키마 계약, 인프라 구축 및 E2E 데이터 흐름 구현을 완료했습니다.
멀티테넌트 및 확장을 고려한 Phase 2~4는 아키텍처 설계를 마친 상태이며 점진적으로 구현해 나갈 계획입니다.

다가오는 면접에서 Phase 1의 실시간 파이프라인 동작 화면과, LLM(Claude Code)을 활용해 안전하게 코드를 생성하고 테스트로 검증하는 개발 워크플로우를 직접 시연해 보여드리고 싶습니다.
