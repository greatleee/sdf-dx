# Backend Code Architecture Doc — Pre-write Discussion Notes

| | |
|---|---|
| **Date** | 2026-05-23 |
| **Status** | Working notes — disposable. Archive after arch doc lands. |
| **Scope** | Pre-arch-doc discussion capture. Not a phase plan. |
| **Author** | cd.lee.dev@gmail.com (+ Claude) |
| **Branch** | `worktree-be-code-arch-doc` |

> **목적**: arch doc 본문 작성 전에 도달한 합의/발견한 gap/미결 결정을 cold-resume 가능한 형태로 박아둠. arch doc 완성 후 `docs/plans/archive/`로 이동.

---

## 1. 합의된 사항

### 1.1 Doc의 정체

**Backend 코드 아키텍처 가이드.** Python + Kotlin 양쪽 코드 작성 시 모두 참조.

핵심 framing:
- **FC/IS (Bernhardt)** 가 코드 구조의 메인 패턴.
- **DDD tactical pattern** 은 *모델링 어휘*로 일부만 차용. FC/IS와 충돌하면 FC/IS 우선.
- FC/IS와 DDD tactical은 같은 layer가 아님 — FC/IS = 코드 구조, DDD tactical = 모델링 어휘. doc은 "DDD pattern을 FC/IS 어느 쪽에 매핑할지" framing으로.
- 모델이 default로 아는 내용은 적게. 워크플로우 specific / non-default한 것 위주.

### 1.2 DDD tactical 각 패턴의 운명 (doc에 명시할 매핑)

| Pattern | FC/IS 매핑 | doc 명시 필요? |
|---|---|---|
| Value Object | Core (pure data) | 자명, 생략 |
| Aggregate | Core data + pure 함수 (OO 메서드 ❌) | 필요 — "OO 메서드" 패턴 버린다는 것 |
| Domain Event | Core가 값으로 return, Shell이 emit | 필요 — emit 위치 |
| Repository | Shell only. "domain interface + infra impl" 추상화 ❌ | 필요 |
| Domain Service | 순수 로직 → Core, IO 섞이면 use-case (Shell) | 필요 — 용어 사용 여부 결정 |
| Factory | 그냥 함수 | 생략 |
| Entity (mutable) | data + transition function (self-mutation ❌) | 필요 |

**용어 사용 권장**:
- "Aggregate" 단어 **안 씀** → "domain module root data type"
- "Repository" **안 씀** → `<Noun>Reader` / `<Noun>Writer` port (plan 이미 이렇게 함)
- "Domain Service" **안 씀** → pure 로직 = core 함수, IO 섞이면 application use case

### 1.3 Python + Kotlin — 한 doc + per-language callout

- 80%는 language-agnostic (원칙, mapping, BC/aggregate 호출 규칙, 트랜잭션 위치, validation, test 피라미드)
- 20%는 callout으로 분리:

| 항목 | Kotlin | Python |
|---|---|---|
| 불변성 idiom | `data class` + `val` + `.copy()` | `@dataclass(frozen=True, slots=True)` |
| Sum type | `sealed class/interface` | tagged dataclass union (discriminator literal) |
| DI (clock/uuid) | 생성자 주입, `java.time.Clock` 표준 | 함수 인자 or Protocol |
| Async | `suspend` (IO 경계 형식적 가시) | `async def` |
| 모듈 경계 enforcement | `internal`, `-Xexplicit-api=strict`, Konsist | convention + `import-linter` |
| ORM 충돌 회피 | JPA 회피, Exposed/JOOQ 권장 | SQLAlchemy Core or asyncpg raw |
| Pure 강제력 | suspend로 IO 가시화 | 100% convention + import-linter rule |

**원칙은 같고 idiom만 다름** — 언어별 챕터 분리 ❌, 각 규칙 옆 callout 박스 inline ✅.

### 1.4 Error 표현 — "분리안" 채택 (idiom 구체는 미정, B6)

- **Core 내부**: 양쪽 모두 "실패를 값으로 return". 원칙 통일.
- **Shell 경계**: exception 던져도 OK.
- **표현 idiom은 언어별로 다름** — 통일 강요 안 함. ← 이게 "분리안"의 정수.

구체 idiom은 §3.2 결정 대기 (B6).

### 1.5 Plan 처리 — "Option C" (forward reference)

발견: Phase 1 plan은 wrong-from-day-one 부분 있음 (arch 규칙 확정 전 작성됨). 단, 5000줄 plan 중:
- **구조** (folder layout, import-linter rule, Konsist arch test, docker-compose, contracts/codegen, ADR scaffold) → 대부분 맞음
- **code sample** (`raise X` throwing core, `datetime.now()` 산재) → arch doc 규칙과 충돌
- **gap** (cross-BC use case 위치, shared_kernel 경계) → 추가 필요

`docs/SOT-LAYERS.md` line 74 명시: phase plan은 "Never updated to reflect drifted code". 재작성은 SOT-LAYERS 정신 위반.

**채택 방식 (Option C)**:
1. Plan 헤더에 forward reference 1줄 추가:
   > `**Code Architecture:** <arch-doc-path> — 이 plan의 code sample이 arch doc과 충돌하면 arch doc이 정답.`
2. **Plan code sample은 손대지 않음.** sub-agent가 task 실행 시 충돌 발견하면 arch doc 규칙으로 함수 시그니처 조정.
3. 실행 중 plan 자체 편집 금지 (SOT-LAYERS 그대로).

**기각된 옵션**:
- A (plan 재작성): 5000줄 scaffold 투자 = 정신 위반
- B (그대로 + 실행 시 reconcile): sub-agent가 wrong code copy-paste 위험 실재

---

## 2. 발견된 진짜 gap (arch doc이 채워야 할 delta)

> **중요**: 아래 항목들은 이미 design spec / plan 에 있는 것이 아닌, **새 doc만 채울 수 있는 빈자리**. 기존에 있는 건 링크만.

### 2.1 이미 있는 것 (새 doc은 *링크만*)

- FC/IS 4-bullet 원칙 → `docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md` §2.1
- BC 점진 도입 + "shared_kernel + 도메인 이벤트 + ports만" → spec §2.2
- Drift toolchain matrix (Python/TS/Kotlin) → spec §6 (매우 자세함)
- Folder layout → spec §9.1, §9.2
- Test pyramid → spec §7
- import-linter forbidden contract, Konsist `domain ↛ adapters` 룰 → Phase 1 plan 이미 적용
- ADR-4 (FC/IS), ADR-8 (BC evolution), ADR-9 (inter-context), ADR-10 (toolchain) 예약됨

### 2.2 Gap들

**B1. Plan과 "분리안"의 즉각 충돌**

현재 Phase 1 plan code sample 전체가 `raise X` (core에서 throw). 분리안 적용 시 시그니처 변경되는 함수들:
- `apply_event(...) -> State` → `... -> StateChange | InvalidTransition`
- `Topology.machine_by_sparkplug_node_id(...) -> Machine` → `... -> Machine | NotFound`
- `compute_oee(...) -> OeeResult` → 그대로 (실패 없음)
- ingest `normalize(...) -> Record` → `... -> Record | InvalidRecord`

→ arch doc이 "core는 실패를 값으로" 규칙을 박으면 plan code sample 자동으로 끌려옴 (Option C로 처리).

**B2. DDD 용어 vs plan 실태**

Plan 어디에도 "Aggregate" / "Repository" / "Domain Service" 단어 안 나옴. 대신:
- `LineModel` (Kotlin), `Topology` (Python) = 사실상 *aggregate root + 변환 함수*
- `LineStateReader` Protocol = *port (Reader)*, traditional Repository 아님

→ §1.2 권장 (DDD 용어 안 쓰기) 그대로 doc에 박음.

**B3. Cross-BC 호출 위치 — Phase 2 직전에 터질 gap** ⬅ **결정 필요**

Plan에 `contexts/monitoring/application/`, `contexts/topology/application/` 둘 다 존재 = BC 내부에 use case. import-linter는 `independence` contract로 BC 간 직접 import 금지.

**문제**: cross-BC use case (예: "라인 상태 조회 시 topology에서 machine 메타 조인")는 어디 사는가?

옵션:
- **A**: `application/`을 BC 안에 두고, 다른 BC import는 event / shared_kernel / port via composition으로만 — 엄격
- **B (권장)**: top-level `src/sdf_api/use_cases/` 신설, cross-BC orchestration만 거기. BC 내부 `application/`은 BC-local만
- **C**: `monitoring`이 `topology.ports`만 import 허용 (도메인은 금지) — 부분 완화

권장 근거: B가 BC 격리 가장 깔끔. 단, sub-agent가 cross-BC use case 만들 때 "어디 두지?"로 매번 헤매지 않음.

**B4. shared_kernel 경계**

현재 plan: ID newtype만 (`FactoryId/LineId/MachineId`). Spec §9.1엔 "TenantId, Timestamp" 까지.

doc에 박을 룰:
- shared_kernel **허용**: IDs (UUID newtype), cross-cutting VOs (Tenant, Timestamp newtype)
- shared_kernel **금지**: Aggregate, domain service, BC 간 공유 이벤트 (Kafka로)
- 안 박으면 shared_kernel 비대화

**B5. Clock/UUID 주입 — 부분만 적용**

Plan tests는 `t(1), t(2)` 식 시간 주입 ✅. 하지만 명시된 *규칙*은 없음.

doc에 박을 규칙:
- Core: `datetime.now()` / `uuid4()` / `random` 직접 호출 ❌
- Shell이 inject: Python `Callable[[], datetime]` 또는 자체 `Clock` Protocol. Kotlin은 `java.time.Clock` 표준.
- import-linter / Konsist 룰로 enforce 가능 (core에서 `datetime.now`, `uuid.uuid4` import 금지) — toolchain matrix에 추가 contract

**B6. Error 표현의 *구체적* idiom 결정** ⬅ **결정 필요**

"분리안" 채택은 합의됨. 구체 형태:

| | Kotlin | Python |
|---|---|---|
| 옵션 1 | stdlib `Result<T>` | `returns` lib (의존성 추가) |
| **옵션 2 (권장)** | sealed class `Outcome` 자체 정의 | tagged union (`Literal` discriminator + dataclass) |
| 옵션 3 | arrow-kt `Either` (의존성) | — |

권장 근거: 옵션 2 = 외부 의존성 없음, idiom 손실 적음. `apply_event` 예시 = `sealed class StateChangeOutcome { data class Applied; data class Rejected }` / Python `StateChange = Applied | Rejected`.

---

## 3. Arch doc 배치 — SOT-LAYERS.md와의 관계 ⬅ **결정 필요**

이 doc은 현재 `docs/SOT-LAYERS.md` 7층 (Strategy / ADR / Functional surface / AC / AI-WORKFLOW / Plan / Code) 어디에도 안 들어맞음:
- Strategy 아님 (코드 컨벤션은 "why this portfolio"가 아님)
- ADR 아님 (개별 결정 아님, 컨벤션 집합)
- Functional surface 아님 (사용자 행동 아님)
- AC / Plan / Code 아님

**선택**:
1. **(권장) 신규 layer 추가** — "Engineering Conventions" (변경 빈도: 컨벤션 진화 시점만 freeze 해제). SOT-LAYERS.md 업데이트 + `docs/architecture/` 폴더 신설.
2. **ADR 다발로 쪼개기** — ADR-4 (FC/IS), ADR-9 (inter-context), 신규 ADR-X (error-as-value), ADR-Y (clock injection), ADR-Z (cross-BC use case 위치). User가 "문서 하나" 원했으니 거부.
3. **design spec §2에 흡수** — Spec은 frozen rule. supersede 새 spec 필요 → heavy.

권장 근거: 1번. Living guide (코드 컨벤션 진화 시점만 편집, 평소엔 freeze). ADR-fest로 쪼개면 cross-reference 미궁.

---

## 4. 결정 (2026-05-23 완료)

1. **B3 — Cross-BC 동기 쿼리 위치**: ✅ **옵션 B (top-level `src/sdf_api/use_cases/`)**. BC들은 peer, import-linter independence 유지, cross-BC use case만 top-level에 둠.
2. **B6 — Error sum type idiom**: ✅ **자체 sealed class / tagged union**. Kotlin은 `sealed class`, Python은 `@dataclass(frozen=True)` + `Literal` discriminator union. 외부 lib 0.
3. **§3 — Doc 배치**: ✅ **신규 layer "Engineering Conventions"** SOT-LAYERS.md에 추가 + `docs/architecture/` 폴더 신설. Living guide, 컨벤션 진화 시점만 편집.

### 추가 합의 (대화 중 확정)
- **Cross-BC 상태 전파**: **in-process `DomainEventDispatcher`** (외부 lib 0). Kafka는 telemetry pipeline 전용. 마이그 경로: BC 분리 시 dispatcher impl을 Kafka producer로 교체, public interface 동일.
- Plan 처리: Option C (forward reference, code sample 무손상) 그대로.
- Python+Kotlin: 한 doc + per-language callout 그대로.

→ §5 진행 순서대로 commit 시작.

---

## 5. 결정 후 진행 순서 (commits)

1. **(1 commit)** `docs/SOT-LAYERS.md` — "Engineering Conventions" layer 추가 (결정 #3 yes 시).
2. **(1 commit)** `docs/architecture/2026-05-23-code-architecture.md` skeleton — TOC + section headers + status: draft.
3. **(1~2 commits)** arch doc 본문 작성:
   - §1 원칙 (FC/IS 링크 to spec §2.1, 짧게)
   - §2 DDD tactical mapping (§1.2 표 기반)
   - §3 BC / cross-BC / cross-aggregate 호출 규칙 (B3 결정 반영)
   - §4 Error 표현 (B6 결정 반영, "분리안" 명문화)
   - §5 Clock/UUID/Random injection 규칙 (B5)
   - §6 shared_kernel 경계 (B4)
   - §7 Per-language callout 매트릭스 (§1.3 표)
   - §8 Persistence (ORM 충돌 회피 — language별)
   - §9 Lint/enforcement 추가 contracts (B5 enforce용)
4. **(1 commit)** Phase 1 plan 헤더에 forward reference 1줄 추가 (Option C). code sample 무손상.
5. **(N commits)** ADR-4 (FC/IS), ADR-9 (inter-context), ADR-신규 (error-as-value), ADR-신규 (clock-injection) — arch doc의 *결정 부분*을 ADR로 frozen snapshot.

---

## 6. 부수 효과

이 working note 자체가 `docs/AI-WORKFLOW/case-NN.md` 소재 후보:
- "plan을 미리 다 쓰고 보니 arch 규칙이 사후에 정착 → forward reference 패턴으로 drift containment"
- [[project_viewer_attention_model]]상 commit log shape에 직접 나타나는 시그널.

---

**End of working notes. Resume cold from §4 (결정 3개) when ready.**
