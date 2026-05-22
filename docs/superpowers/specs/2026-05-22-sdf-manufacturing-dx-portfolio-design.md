# SDF Manufacturing DX Portfolio — Design Spec

| | |
|---|---|
| **Date** | 2026-05-22 |
| **Target Position** | 현대자동차그룹 SDF Manufacturing DX Senior Full-Stack Engineer |
| **Status** | Draft — pending user review |
| **Time Budget** | 3주+ 풀타임 또는 1달+ |
| **Author** | cd.lee.dev@gmail.com (+ Claude as pair) |

---

## 1. Headline & Strategy

### 1.1 Headline Message

> **"AI-네이티브 senior가 낯선 도메인(제조)을 탐독하는 방식 — 표준 기반의 정직한 모델링과 LLM drift 방지의 정형 워크플로우"**

이 포트폴리오는 단일 데모가 아니라 *engineering judgment의 증거 누적물*이다. 면접관에게 제시할 것:

1. AI 도구로 빠르게 도메인을 흡수하는 *workflow* — *with guardrails*.
2. AI 출력을 신뢰할 시점과 직접 작성할 시점을 *판단*한 흔적 (ADR / 코드 / 케이스 스터디).
3. 표준(ISA-95, ISO 22400, OPC UA Companion Spec, Sparkplug B)에 기반한 *정직한* 모델링 — 흉내내지 않음.
4. Senior 풀스택의 운영 성숙도 (관측가능성, CI/CD, 마이그레이션 전략).

### 1.2 Why this angle (JD 정조준 매핑)

| JD 우대사항 | 본 포트폴리오 증거물 |
|---|---|
| "AI 출력 결과를 신뢰해야 할 시점과 처음부터 코드를 작성해야 할 시점 파악" | Phase별 AI 워크플로우 케이스 스터디 + ADR 인용 |
| "LLM 지원 코딩을 가상 애플리케이션에 실시간 시연" | Phase 5 라이브 데모 (Main C / B-plan A / Wildcard E) |
| "단순 Vibe Coding을 넘어" | Functional Core + Contract-first + 정형 toolchain drift gate |
| "기술 트레이드오프 분석" | 15+ ADR (특히 #2 TimescaleDB vs InfluxDB, #3 schema-per-tenant) |
| "업그레이드 경로, 하위 호환성 및 마이그레이션 전략" | 각 결정의 *evolution policy* + ADR-3, 8 |
| "표준화/모듈화된 아키텍처 / 멀티테넌트" | Phase 2 (schema-per-tenant) + Phase 4 (BC 확장 포인트) |
| "MQTT/Kafka 미들웨어 통합" | Kotlin OT Gateway + Sparkplug B + Kafka |

### 1.3 도메인 신뢰성 정책

- **목표: B 수준 (표준 정합성)** — ISA-95, ISO 22400, OPC UA Companion Spec, Sparkplug B 인용.
- **명시적 한계: C 수준 (운영 사실주의)** — `docs/KNOWN-UNKNOWNS.md`에 기록. *흉내내지 않음 = 정직함이 무기*.

### 1.4 Usage Scenarios (3중 사용)

1. **서류용 정적 GitHub repo** — README + 다이어그램 + 코드 품질로 평가.
2. **면접 라이브 데모** — 동작하는 시스템, 시나리오 walkthrough.
3. **LLM 코딩 실시간 시연** — JD 우대사항 정조준. 사전 staged + B-plan + wildcard.

---

## 2. Engineering Principles

이 6개 원칙은 design doc의 *근원*이다. 모든 구조 결정은 이 원칙에서 파생된다.

### 2.1 Functional Core / Imperative Shell (Bernhardt)

- 도메인 로직 = pure functions, 외부 의존성 zero.
- 도메인 단위 테스트 = **mock/stub/fake 0개**, container 0개.
- Shell(adapters)만이 IO. IO 직전에 pure 호출.
- 결과: 도메인 정확성을 *수학적으로* 증명 가능 (property-based test 가능).

### 2.2 Bounded Contexts — 점진 도입

- Phase 1: 직관적 분리 (`monitoring/`, `topology/`).
- Phase 2: BC 경계 명시 (`tenancy/`, `identity/` 분리).
- Phase 4: 완전 BC 분리 (`quality/` 또는 `maintenance/`).
- BC 간 통신: **shared_kernel value object + 도메인 이벤트(Kafka) + ports 인터페이스만**.
- 트리거: ① ubiquitous language 충돌 ② 독립적 lifecycle ③ 다른 팀 소유 가능성.

### 2.3 Contract-First Inter-Service Communication

- 모든 inter-service 통신은 *schema가 single source of truth*.
- **OpenAPI 3.1** (FE↔BE), **Sparkplug B Protobuf** (Edge↔Bus), **JSON Schema** (Kafka payload), Phase 3에서 Avro 검토.
- 변경 순서: **spec 먼저 → codegen → 구현**. 거꾸로 가지 않음.
- CI gate: codegen drift 감지 시 fail.
- 결과: LLM이 endpoint 시그니처를 hallucinate 못 함.

### 2.4 Test Speed Tiering — 로컬 = 빠름, CI = 진짜

| 레이어 | 로컬 기본 | CI |
|---|---|---|
| `tests/domain/` | always-on, 1초 미만 | 동일 |
| `tests/application/` | in-memory fakes (FakeKafka, InMemoryStore, FrozenClock) | 동일 |
| `tests/integration/` | **opt-in** (`--integration`) | always-on, testcontainers |
| `tests/e2e/` (BE+FE) | **fake stack** (MSW or BE fake-mode) | real Postgres + Kafka + Kotlin gateway |

구현 메커니즘:
- FastAPI app factory가 `SDF_MODE=fake|real` 환경변수로 adapter swap.
- React Vite dev server는 `dev:fake` 모드에서 MSW(Mock Service Worker) 자동 inject.
- Playwright `--project=fake` (로컬), `--project=real` (CI).

### 2.5 E2E = QA Layer

- 모든 use case → 정확히 1개의 E2E spec.
- AC를 코드로 (BDD 식).
- `docs/USE-CASES.md` ID ↔ E2E spec ID **1:1 매핑**.
- CI gate: use case 수 ≠ spec 수면 fail (use case 누락 자동 감지).

### 2.6 LLM Drift Containment via Toolchain

- 모든 LLM drift 가능 경계는 *자동화된 lint/type/architecture 검증* 으로 막는다.
- 사람의 리뷰는 *판단력* 에 집중, 보일러플레이트 위반은 도구가 잡는다.
- 상세: §6 참조.

---

## 3. Architecture & Components

### 3.1 Polyglot 분할

| 레이어 | 책임 | 스택 |
|---|---|---|
| Edge / OT Gateway | OPC UA polling, MQTT publish, Sparkplug B birth/death/data — *현장 설비와의 통신 프로토콜* | **Kotlin** + Spring Boot + Eclipse Tahu/Paho |
| Device Simulator | 라인·설비 시뮬레이션 (Sparkplug B publisher) | Kotlin |
| (Phase 4 옵션) OPC UA Server | Eclipse Milo + Companion Spec for Machinery | Kotlin |
| MQTT Broker | Sparkplug B 토픽 hub | HiveMQ CE |
| Sparkplug→Kafka Bridge | per-tenant topic 라우팅 | Kotlin |
| Stream Bus | 메시지 브로커 | Kafka (Redpanda) |
| Ingest & Stream Processor | Kafka 소비 → 정규화 → tenant 라우팅 → 시계열 적재 | **Python** + aiokafka |
| Domain Service | OEE/A/P/Q (ISO 22400) · 라인 상태머신 · 알람 룰 | Python + FastAPI |
| Tenant & Config Service | 공장 프로필 · 라인 토폴로지 · 사용자 · 권한 | Python + FastAPI |
| API / BFF | REST + WebSocket · JWT 인증 | Python + FastAPI |
| Frontend Dashboard | 실시간 라인 상태 · OEE · 알람 · tenant switcher · 다국어 | **React** + Vite + TanStack Query + Tailwind + Recharts + react-i18next |
| Storage (관계형 + 시계열) | 멀티테넌트 격리 + hypertable | **PostgreSQL + TimescaleDB** |
| Cache (Phase 2+) | 최근 라인 상태 · 세션 | Redis |
| Object Storage (Phase 3+) | 리포트 / 데이터 덤프 | MinIO |
| Observability (Phase 3+) | metrics · traces · logs | Prometheus + Grafana + OpenTelemetry |
| CI/CD (Phase 3+) | 빌드 · 테스트 · 컨테이너 푸시 | GitHub Actions |

### 3.2 Polyglot 정당화 (ADR-1)

- **JVM의 단독 우위**: Eclipse Milo (OPC UA), Paho (MQTT), Tahu (Sparkplug B) — 산업 통신 라이브러리는 JVM이 *유일한 어른의 선택*. Python으로 가면 파편화·미성숙 라이브러리 고통.
- **Python의 자연 영역**: 도메인 로직 (OEE 산식, ISA-95 데이터 모델 — Pydantic이 표현력 강함), 빠른 production polish, 사용자 강점.
- **헤드라인과 정렬**: "AI 판단력 시연" 은 *익숙한 스택에서* 가능. 본인이 강한 Python에서 도메인 흡수 + 검증 시연, JVM은 *프로토콜 어댑터*로 한정.
- **실제 industrial system 구조 미러링**: OT 어댑터(JVM/네이티브) vs 애플리케이션(Python/Node)이 현장 패턴.

### 3.3 Repo: Monorepo

- 1개 Git repo. 폴리글랏 경계가 한눈에, 한 PR로 OT↔앱↔FE 변경 추적.
- 면접 walkthrough에 압도적으로 유리.

---

## 4. Data Flow (Phase 1 기준)

```
[Device Simulator (Kotlin)]
     ↓ Sparkplug B over MQTT (Eclipse Tahu)
[HiveMQ CE]
     ↓ Sparkplug → Kafka Bridge (Kotlin)
[Kafka topic: sdf.{tenant}.machine.{type}]   ← per-tenant topic
     ↓ aiokafka consumer (Python)
[Ingest & Stream Processor]
     ↓ 정규화 + tenant resolution + search_path 라우팅
[tenant_{X}.machine_telemetry]   (TimescaleDB hypertable)
     ↓ Continuous Aggregate
[tenant_{X}.line_oee_5m, _1h, _shift]
     ↑ 쿼리 (search_path = tenant_{X})
[Domain Service · API/BFF (FastAPI)]
     ↓ REST (조회) + WebSocket (실시간 push)
[React Dashboard]
```

**핵심 규칙:**
- Tenant 라우팅: Kafka topic의 `{tenant}` 추출 → consumer가 `SET search_path` → 해당 schema의 hypertable에 INSERT.
- 실시간 push: domain service가 라인 상태 변화 감지 → WebSocket pub.
- 시뮬레이터는 ISA-95 L0~L2 추상 (Equipment / Work Unit / Work Center) 따름.
- 모든 메시지는 Sparkplug B sequence number 보유 → 갭 감지 가능.

---

## 5. Storage & Multi-Tenancy

### 5.1 시계열 저장소: PostgreSQL + TimescaleDB (ADR-2)

- 시장 1위는 **InfluxDB** (DB-Engines 20.86 vs Timescale 5.62, PTC ThingWorx / Siemens WinCC OA 공식 채택). 이 *사실을 알고도* TimescaleDB 선택.
- 선택 근거:
  - 표준 SQL → 면접관 누구나 코드 읽힘.
  - Postgres 통합 운영 (관계형 + 시계열 단일 DB).
  - 채용 시장 인지도 ("Postgres + 시계열" 겸용 경험).
  - InfluxDB v1→v2→v3 (FluxQL 폐기, IOx 전환) 마이그 혼란 회피.
  - 데모 신뢰성: 움직이는 부분이 적을수록 라이브 데모에 안전.

### 5.2 멀티테넌시: Schema-per-tenant + hypertable per schema (ADR-3)

- 격리 모델: `tenant_korea`, `tenant_india`, ... 스키마 분리.
- 각 schema에 hypertable + Continuous Aggregate.
- Onboarding: `POST /tenants` → schema + 마이그 + hypertable + CA 자동 생성 (라이브 데모 시나리오 D에 활용 가능).
- 마이그레이션 도구: Alembic + multi-schema 패턴 (env.py에서 search_path 동적 주입 + `alembic-multischema` 데코레이터).
- Connection routing: tenant resolution middleware → asyncpg `search_path`.
- Cross-tenant 분석: 별도 aggregator (Phase 3+에서 UNION ALL).

### 5.3 격리 모델 선택 근거

- RLS도 검토했으나 다음 이유로 schema-per-tenant 선택:
  - 산업 정서(Ignition per-site, AVEVA per-plant historian)와 자연스럽게 정렬.
  - 2~수십 공장 규모에서 운영 부담 ≈ RLS (Citus/Crunchy 경고는 500+ tenant 컨텍스트).
  - 온보딩 자동화 라이브 데모(시나리오 D) 매력 압도적.
  - TimescaleDB Continuous Aggregate × RLS 미호환(GitHub issue #5787) 우회 불필요.
- **마이그레이션 경로 (ADR에 명시)**: 100+ tenant 또는 schema 마이그가 30초+ 걸리면 RLS 또는 Citus로 전환.

### 5.4 도메인 데이터 모델 (Phase 1 초안)

- `factory` (id, name, region, timezone, locale)
- `production_line` (id, factory_id, name, isa95_role)
- `machine` (id, line_id, type, sparkplug_node_id)
- `machine_telemetry` (hypertable: time, machine_id, metric, value)
- `line_state` (hypertable: time, line_id, state[RUNNING/IDLE/DOWN/CHANGEOVER])
- `production_cycle` (cycle_id, line_id, planned_qty, actual_qty, good_qty, started_at, ended_at)
- `alarm` (id, line_id, rule_id, severity, fired_at, acked_at, ack_by)
- `kpi_oee_*` (continuous aggregates: 5m / 1h / shift)

---

## 6. LLM Drift Containment Toolchain (ADR-10)

### 6.1 스택별 매트릭스

| Drift 카테고리 | Python | TypeScript | Kotlin |
|---|---|---|---|
| 레이어 경계 (domain ↛ adapters) | **import-linter** or **tach** | **eslint-plugin-boundaries** | **Konsist** |
| BC 경계 (contexts 간 직접 import) | import-linter / tach | eslint-plugin-boundaries | Konsist |
| Private/internal API leak | **ruff PLC2701, PLE0604** | `@internal` JSDoc + **import/no-internal-modules** | **`internal` keyword + `-Xexplicit-api=strict`** |
| 타입 안전 | **mypy strict** (disallow-any-*) | **tsc --strict --noUncheckedIndexedAccess + no-explicit-any** | Kotlin 자체 + detekt |
| 복잡도 | ruff C901, PLR | eslint complexity | detekt CyclomaticComplexity |
| 미사용 코드 | ruff F401/F841 | ts-prune + eslint no-unused-vars | detekt UnusedImports |
| Async drift | ruff B (bugbear) | no-floating-promises | detekt CoroutineRules |
| Codegen drift | CI diff gate | CI diff gate | CI diff gate |
| 포맷 | **ruff format** | **prettier** | **ktlint** |
| 잠재 버그 | ruff B, S (bandit) | typescript-eslint | detekt |

### 6.2 Kotlin 도구 정당화

- **detekt** — Kotlin 정적 분석 사실상 표준 (ESLint/ruff 등가물).
- **ktlint** — 포맷 (Prettier 등가물).
- **Konsist** — Kotlin-native 아키텍처 테스트 (import-linter / boundaries 등가물). JUnit으로 룰 작성 → 가독성 ↑.
- **`-Xexplicit-api=strict`** — *모든 public API에 명시적 `public` 선언 강제*. **Python underscore leak의 Kotlin 등가물**. 우발적 public API 노출 차단.
- ArchUnit은 backup으로 고려, Konsist를 1순위.

### 6.3 import-linter 룰 예시 (Python)

```toml
[[tool.importlinter.contracts]]
name = "domain은 외부 인프라를 알면 안 됨"
type = "forbidden"
source_modules = ["api.contexts.*.domain"]
forbidden_modules = ["api.contexts.*.adapters", "sqlalchemy", "aiokafka", "httpx", "redis"]

[[tool.importlinter.contracts]]
name = "BC는 서로 직접 import 금지 (shared_kernel만 허용)"
type = "independence"
modules = ["api.contexts.monitoring", "api.contexts.topology", "api.contexts.tenancy"]
```

### 6.4 Konsist 룰 예시 (Kotlin)

```kotlin
@Test
fun `domain layer should not depend on adapters or application`() {
    Konsist.scopeFromModule("ot-gateway-kotlin")
        .classes()
        .filter { it.resideInPackage("..domain..") }
        .assertFalse { it.hasImports("..adapters..", "..application..") }
}
```

### 6.5 실행 레이어

- **로컬 (속도 생명)**: pre-commit hook → ruff/eslint/ktlint/detekt만 실행 (밀리초). mypy/tsc/Konsist는 IDE LSP에서 실시간.
- **CI (정확성)**: full mypy/tsc strict + import-linter + Konsist + dependency-cruiser + codegen drift + 모든 테스트.
- **AI 생성 코드 PR**: PR 라벨 `ai-generated` 시 추가 게이트 (예: ADR 인용 누락 시 fail, 도메인 모듈에 외부 의존성 import 시 명시적 차단).

---

## 7. Testing Strategy

| 레이어 | 도구 | 의존성 | AI 워크플로우 결합 |
|---|---|---|---|
| Domain 단위 (pure) | pytest + Hypothesis (property-based) | **0개** — mock/stub/fake 금지 | AI 생성 → 표준 대조 검증 (Phase 1 케이스 #1) |
| Schema/Contract | JSON Schema 검증 + Sparkplug B 페이로드 fixture | contracts/ 직접 | LLM이 표준 문서 보고 fixture 자동 생성 |
| Application use case (fakes) | pytest + in-memory FakeKafka/FakeStore/FrozenClock | adapter 인터페이스만 | use case 행위 단위 |
| Integration | testcontainers (Postgres + Kafka) | real Postgres/Kafka | CI default-on, 로컬은 `--integration` |
| Kotlin gateway | JUnit 5 + Testcontainers | real HiveMQ | Sparkplug birth/death 시나리오 |
| E2E (BE+FE) | **Playwright (Python)** | local=fake stack, CI=real | use case = 1 spec, AC 검증 |
| Load (Phase 3) | k6 | real | 시나리오 자동 생성 |
| **AI 출력 검증 메타** | CI gate | — | AI 코드 변경 시 ADR/표준 인용 누락 자동 검사 |

### 7.1 로컬 실행 명령

```bash
pytest                       # domain + application(fakes) — 항상 빠름
pytest --integration         # testcontainers 추가 (opt-in)
pnpm test                    # FE 단위
pnpm test:fake               # FE + MSW
pnpm e2e:fake                # E2E with fake BE
make ci                      # CI와 동일한 풀 매트릭스 (느림, 가끔만)
```

---

## 8. Error Handling

### 8.1 Phase 1 (baseline)

- **Kafka**: at-least-once + idempotent consumer (cycle_id 기반 dedup).
- **Sparkplug B**: birth/death/rebirth 처리. sequence number gap 감지 → 메트릭 alert + rebirth request.
- **Schema 검증**: contracts/ JSON Schema. 실패 시 `dlq.{tenant}` 토픽 + 메트릭.
- **Unknown tenant**: `dlq.unknown_tenant` + alert.
- **DB**: batch insert (100~1000 rows), `INSERT ... ON CONFLICT DO NOTHING` (멱등).
- **Health**: `/healthz` (liveness), `/readyz` (DB + Kafka 연결 검사).
- **Frontend**: WS 끊김 시 polling fallback + 마지막 known state 표시. *라이브 데모 시연 시 중요*.

### 8.2 Phase 3 (강화)

- Circuit breaker (resilience4j-kotlin, tenacity-python).
- Bulkhead pattern (tenant 단위 isolation).
- Backpressure: Kafka consumer lag 모니터링 → 자동 throttle.
- Chaos test: pumba 컨테이너 kill 시뮬레이션.

---

## 9. Repo Structure

```
sdf-dx/
├── README.md                       ← root
├── apps/
│   ├── ot-gateway-kotlin/
│   ├── device-simulator-kotlin/
│   ├── ingest-python/
│   ├── api-python/
│   └── dashboard-react/
├── packages/
│   └── contracts/
│       ├── sparkplug/              # Sparkplug B Protobuf
│       ├── openapi/                # OpenAPI 3.1 (FE↔BE)
│       ├── kafka-payloads/         # JSON Schema (Phase 1) → Avro (Phase 3)
│       └── codegen/                # 생성 산출물 (Pydantic, TS, Kotlin DTO)
├── infra/
│   ├── docker-compose.yml          # Phase 1
│   ├── docker-compose.prod.yml     # Phase 3
│   └── k8s/                        # Phase 3 매니페스트 예시
├── docs/
│   ├── adr/                        # 0001-polyglot, 0002-timescaledb, ...
│   ├── KNOWN-UNKNOWNS.md
│   ├── DOMAIN-NOTES.md             # ISA-95/ISO 22400/Sparkplug B 흡수 노트
│   ├── USE-CASES.md                # E2E spec과 1:1 매핑
│   ├── AI-WORKFLOW/                # phase별 LLM 워크플로우 케이스 스터디
│   └── superpowers/specs/          # 이 design doc 위치
├── scripts/
│   └── live-demo/                  # Main C / B-plan A / Wildcard E 시나리오
└── .github/workflows/              # CI
```

### 9.1 Python BC 구조 (apps/api-python)

```
src/
├── contexts/
│   ├── monitoring/
│   │   ├── domain/         # pure: aggregates, value objects, domain services, events
│   │   ├── application/    # use case orchestration (shell)
│   │   ├── adapters/       # Kafka, DB, HTTP, WS
│   │   └── ports.py        # inbound/outbound 인터페이스
│   └── topology/
│       ├── domain/
│       ├── application/
│       └── adapters/
├── shared_kernel/          # TenantId, FactoryId, LineId, Timestamp
└── composition.py          # DI composition root

tests/
├── contexts/
│   ├── monitoring/
│   │   ├── domain/         # pure, 0개 mock/stub/fake
│   │   ├── application/    # fakes
│   │   └── integration/    # testcontainers (CI default)
│   └── topology/
└── e2e/                    # cross-context use case 시나리오
```

### 9.2 Kotlin BC 구조 (apps/ot-gateway-kotlin)

```
src/main/kotlin/
├── contexts/
│   └── sparkplug_edge/
│       ├── domain/         # pure: Sparkplug payload model, edge state
│       ├── application/
│       └── adapters/       # Paho/Tahu, Kafka producer
└── composition/

src/test/kotlin/
├── contexts/
│   └── sparkplug_edge/
│       ├── domain/         # pure
│       ├── application/    # fakes
│       └── integration/    # Testcontainers HiveMQ
└── architecture/           # Konsist 룰 테스트
```

---

## 10. Phase Plan

각 phase는 git tag + README 업데이트 + 2~3분 walkthrough 녹화로 마감. **매 phase 종료 시점이 그 자체로 portfolio 제출 가능 상태.**

### Phase 1 — Single-Factory Vertical Slice (Week 1–2)

| | |
|---|---|
| Deliverable | 1 가상 공장 + 1 라인 + 5 설비, end-to-end 동작 |
| Components | Kotlin OT gateway (1 line publisher) + HiveMQ + Kafka + Python ingest + Python domain (OEE) + React dashboard |
| Docs | README · C4 다이어그램 · ADR 1–4, 11, 12 · KNOWN-UNKNOWNS · DOMAIN-NOTES · USE-CASES |
| AI 워크플로우 | 케이스 #1 — "ISO 22400 OEE 산식을 LLM으로 흡수 → property-based 테스트 자동 생성 → 표준 대조 검증" |
| Live demo 시나리오 | 1개 5분 시나리오 (Scenario A 기반) — *cross-cutting 원칙 충족* |
| Portfolio 상태 | "AI-네이티브 senior가 단일 라인 실시간 공정 모니터링을 도메인 학습 과정과 함께 공개" |

### Phase 2 — Multi-Tenancy (Week 3)

| | |
|---|---|
| Deliverable | 가상 공장 +2개 (서로 다른 라인 구성, 설비 타입, 타임존, 언어) |
| Components | Tenant 라이프사이클 (`POST /tenants` 자동 schema/마이그/CA) · 다국어 · JWT · BC `tenancy/`, `identity/` 분리 |
| Docs | ADR 8, 9 (BC 도입, inter-context 통신) |
| AI 워크플로우 | 케이스 #2 — "schema-per-tenant 격리 패턴 트레이드오프 — AI 출력 검증 케이스" |
| Live demo 시나리오 | 1개 (Scenario D 기반) — 새 공장 온보딩 |
| Portfolio 상태 | "설정 기반 확장 가능한 멀티테넌트 플랫폼" |

### Phase 3 — Production Readiness (Week 4)

| | |
|---|---|
| Deliverable | 24/7 운영 가정의 관측가능성 + 성능 + CI/CD |
| Components | Prometheus + Grafana + OTel + k8s 매니페스트 + GitHub Actions + Avro 도입 검토 |
| Docs | ADR 13, 14 (관측가능성, 성능 budget) · 마이그레이션 전략 문서 |
| AI 워크플로우 | 케이스 #3 — "성능 테스트 케이스 자동 생성 → 결과 분석 → AI 제안 최적화 검증" |
| Live demo 시나리오 | 1개 (메인 후보 C 일부) |
| Portfolio 상태 | "production-ready 멀티테넌트 제조 DX 플랫폼" |
| 성능 목표 | 1,000 msg/sec 인제스트, p99 API 응답 200ms, WS push 500ms 이내 |

### Phase 4 — Use Case Extension Point (Week 5+, optional)

| | |
|---|---|
| Deliverable | 다른 유즈케이스(품질 관리 또는 예측 유지보수) skeleton + 1 기능 |
| Components | 도메인 모듈 아키텍처 (포트-어댑터 플러그인) · 새 BC `quality/` 또는 `maintenance/` |
| Docs | ADR 15 (확장 포인트 아키텍처) |
| Live demo 시나리오 | 1개 (Scenario B — AI 오류 잡기) |
| Portfolio 상태 | "다중 유즈케이스 지원 모듈식 플랫폼" |

### Phase 5 — Live Demo Performance Prep (마지막 주)

| | |
|---|---|
| Deliverable | 면접 시연 폴리시 |
| Outputs | Main 시나리오 8~12분 대본 + 영상 백업 · B-plan 3~5분 대본 + 영상 · Wildcard 대본 · 1-pager 면접 소개서 · 5분 walkthrough 영상 |
| 리허설 | 시뮬레이션 면접 2회 (실제 시간 측정, 망쳤을 때 복구 시나리오 포함) |

### Phase별 우선순위 & cut 정책

시간 압박 시 cut 순서: Phase 4 → Phase 5 일부 → Phase 3 일부.  
**Phase 1, 2는 절대 cut 불가** (vertical slice + 멀티테넌시 = senior 시그널 baseline).

---

## 11. Live Demo Strategy

### 11.1 Main — Scenario C: 새 설비 타입 통합 (Sparkplug 확장, 8~12분)

흐름:
1. (30s) 요구사항: "새 설비 타입(예: 도장 부스) 추가하자"
2. (1m) OPC UA Companion Spec 참조 → LLM과 함께 Sparkplug B namespace 설계 → contracts/sparkplug/ 추가
3. (2m) Kotlin OT 게이트웨이: AI 생성 → Konsist 룰 통과 검증 → 단위 테스트
4. (2m) Python 도메인 모델 확장: AI 생성 → import-linter 통과 → pure 테스트
5. (2m) 시뮬레이터에 새 설비 추가 → 데이터 흐름 확인
6. (2m) 대시보드 자동 등록 (contract codegen 결과 활용)
7. (1m) 마무리: AI가 생성한 부분 vs 본인이 검증·수정한 부분 명시적으로 내레이션

핵심 시연 포인트:
- Contract-first → LLM drift 0
- BC 경계 → Konsist/import-linter 자동 검증
- Test pyramid → domain pure 테스트가 1초 미만에 통과

### 11.2 B-plan — Scenario A: 새 KPI 추가 (3~5분)

- ISO 22400 TEEP 또는 MTBF/MTTR 추가
- AI에게 산식 → property-based test 자동 생성 → 표준 문서 대조
- Domain Service에 추가 → API 노출 → 대시보드 위젯
- 짧고 안전. Main 망쳤거나 시간 부족 시.

### 11.3 Wildcard — Scenario E: 면접관 즉석 요청 (시간 가변)

- "면접관님이 추가하고 싶은 기능 있으신가요?" 메인 종료 후 시간 남으면.
- 즉석 spec → planning → 구현.
- **Fallback**: 5분 안에 못 끝낼 것 같으면 우아하게 "이건 spec 작성에서 멈추고 PR 형태로 마무리하겠습니다" 라고 후퇴.

### 11.4 영상 백업

모든 시나리오는 5~10분 풀-스피드 녹화본 사전 준비. 라이브 중 사고 시 영상으로 대체 + 코드 walkthrough.

---

## 12. ADR Roadmap

작성 우선순위 순:

1. Polyglot architecture (Python + Kotlin) — Phase 1
2. TimescaleDB over InfluxDB — Phase 1
3. Schema-per-tenant + migration path to RLS/Citus — Phase 1 (Phase 2 도입 명시)
4. Functional Core / Imperative Shell — Phase 1
5. Contract-first inter-service communication (LLM drift prevention) — Phase 1
6. Test speed tiering (local fakes, CI real) — Phase 1
7. E2E as QA — use case coverage gate — Phase 1
8. Domain modeling evolution (BC 점진 도입) — Phase 1 (실제 적용 Phase 2)
9. Inter-context communication (events + shared kernel) — Phase 2
10. Architectural fitness via tooling (ruff/mypy/eslint/detekt/Konsist) — Phase 1
11. Sparkplug B namespace design — Phase 1
12. OEE calculation per ISO 22400 — Phase 1
13. Observability stack — Phase 3
14. Performance budget (TPS, latency) — Phase 3
15. Use case extension point architecture — Phase 4

ADR 형식 (Michael Nygard 변형):
- Title
- Status (proposed / accepted / superseded by N)
- Context
- Decision
- Consequences (positive + negative + trade-offs)
- Sources / References (URL 인용 필수)
- Migration path (필요 시)

---

## 13. Acceptance Criteria

### 13.1 Phase 1 AC

- [ ] `README.md` at root, 5분 이내 `docker compose up` 으로 전체 동작
- [ ] 1 가상 공장 + 1 라인 + 5 설비 시뮬레이션 (Sparkplug B birth/death 정상)
- [ ] OEE/A/P/Q 실시간 대시보드 (라인 상태 변화 1초 이내 반영)
- [ ] ADR 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12 작성 완료
- [ ] `docs/KNOWN-UNKNOWNS.md` 작성
- [ ] `docs/DOMAIN-NOTES.md` (ISA-95/ISO 22400/Sparkplug B 흡수 노트, 인용 포함)
- [ ] `docs/USE-CASES.md` ↔ `tests/e2e/use_cases/` 1:1 매핑
- [ ] AI 워크플로우 케이스 #1 문서화 (`docs/AI-WORKFLOW/case-01.md`)
- [ ] 5분 walkthrough 영상
- [ ] CI 통과: ruff + mypy strict + import-linter + eslint + tsc strict + detekt + Konsist + ktlint + contract codegen drift
- [ ] `tests/domain/` 0개 mock/stub/fake, 1초 미만 실행
- [ ] Live demo 시나리오 1개 (5분 분량)

### 13.2 Phase 2 AC

- [ ] 가상 공장 3개 (KR / US / IN — 서로 다른 라인/설비/타임존/언어)
- [ ] `POST /tenants` 자동 onboarding 동작 (schema + 마이그 + hypertable + CA)
- [ ] BC `tenancy/`, `identity/` 분리 + import-linter / Konsist 룰 적용
- [ ] JWT 인증 + 역할 기반 권한 (tenant admin / operator / viewer)
- [ ] 다국어 (ko/en + 1개 더)
- [ ] ADR 9 작성 (ADR 8은 Phase 1에 기록, Phase 2에서 실제 적용)
- [ ] AI 워크플로우 케이스 #2 문서화
- [ ] Live demo 시나리오 2개 (Phase 1의 것 + 신규 1개)
- [ ] Cross-tenant 1개 시나리오 (전사 OEE 평균 — UNION ALL aggregator)

### 13.3 Phase 3 AC

- [ ] Prometheus 메트릭 (per-service, per-tenant)
- [ ] OTel traces (요청 경로 가시화)
- [ ] 구조화 로그
- [ ] k6 시나리오: 1,000 msg/sec 인제스트, p99 API 200ms, WS push 500ms — *측정값 README 포함*
- [ ] GitHub Actions CI/CD (테스트 → 빌드 → GHCR 푸시)
- [ ] Docker Compose prod 프로필 + k8s 매니페스트 예시
- [ ] 마이그레이션 전략 문서
- [ ] ADR 13, 14 작성
- [ ] Chaos test: 1개 컨테이너 kill 시나리오 + 회복 시간 측정

### 13.4 Phase 4 AC (optional)

- [ ] 새 BC (`quality/` 또는 `maintenance/`) 분리, ports/events 명시
- [ ] 1개 use case 실제 동작 + UI 위젯
- [ ] 확장 API 문서 (다음 사람이 새 BC 추가하는 가이드)
- [ ] ADR 15 작성

### 13.5 Phase 5 AC

- [ ] Main 시나리오 8~12분 라이브 시연 가능 (2회 리허설 시간 측정)
- [ ] B-plan 시나리오 3~5분 라이브 시연 가능
- [ ] Wildcard fallback 대본
- [ ] 모든 시나리오 영상 백업 (5~10분 풀-스피드)
- [ ] 1-pager 면접 소개서 (PDF)
- [ ] 5분 portfolio walkthrough 영상

---

## 14. KNOWN-UNKNOWNS (design 단계 명시)

### 14.1 운영 사실주의(C 수준)의 한계

- 실제 교대 인수인계 시점의 데이터 일관성 처리 — 자료만으론 확신 불가, *가정으로* 처리.
- 실제 PLC vendor별 OPC UA 구현 차이 — 시뮬레이터로 추상.
- 다국가 데이터 주권 법규(GDPR, 인도 DPDP 등) 세부 — 마이그 경로만 명시.
- 실제 ICS network segmentation (Purdue model 적용 디테일) — 데모 환경에선 단일 docker network.
- 진짜 24/7 운영의 hot patch / maintenance window 정책 — 가정으로 처리.

### 14.2 의도적 미해결 (마이그 경로만 명시)

- TimescaleDB Continuous Aggregate × RLS 미호환 (우리는 schema-per-tenant라 영향 없으나 알고 있음).
- Kafka exactly-once semantics (Phase 1은 at-least-once + idempotent로 충분).
- Multi-region active-active (마이그 경로만 명시, 구현 안 함).
- 100+ tenant 도달 시 RLS / Citus 전환.

---

## 15. Domain Sources (참고 자료)

- **ISA-95** — 제조 운영의 5계층 표준 (L0~L4).
- **ISO 22400** — 제조 KPI 정의 (OEE, Availability, Performance, Quality 산식).
- **OPC UA Companion Specifications** (OPC Foundation) — 특히 OPC UA for Machinery, Robotics, Machine Tools.
- **MQTT Sparkplug B** (Eclipse Foundation, Tahu reference impl).
- **NIST Smart Manufacturing reference architecture**.
- **공개 데이터셋**: Bosch Production Line Performance (Kaggle), NASA C-MAPSS Turbofan (Phase 4 옵션).
- **벤더 공식 문서**: Inductive Automation Ignition, PTC ThingWorx, Siemens MindSphere/Industrial Edge, AVEVA System Platform.

각 출처는 ADR 작성 시 URL 인용 필수.

---

## 16. Non-Goals (이 포트폴리오에서 *안* 할 것)

- 실제 PLC와의 통신 (시뮬레이터로 대체).
- ML/AI 모델 학습 (Phase 4 예측 유지보수는 *모델 inference 통합*만, 학습은 사전 모델 사용).
- 모바일 앱 (웹 대시보드만).
- 다국가 데이터 주권 실구현 (경로만 명시).
- 100+ tenant 스케일 검증 (3개로 멈춤).
- 사용자가 보지 않는 부분의 polish (admin UI 등은 minimal).
- "운영 사실주의" 흉내내기 (KNOWN-UNKNOWNS에 솔직히 명시).

---

## 17. Open Questions (작성 시점 미해결)

- Phase 1에 `device-simulator-kotlin` 을 별도 앱으로 분리할지 vs `ot-gateway-kotlin` 내부 모듈로 둘지 — *Phase 1 진입 시점에 결정*.
- React 상태 관리: TanStack Query 단독 vs + Zustand/Redux — *대시보드 복잡도 보고 결정*.
- k6 vs Locust vs Vegeta — *Phase 3 진입 시점에 결정* (다만 k6가 1순위 후보).
- Wildcard 시나리오 fallback의 "spec 작성으로 후퇴" 가 실제로 우아한지 — *Phase 5 리허설 때 검증*.

---

**End of Design Spec.**
