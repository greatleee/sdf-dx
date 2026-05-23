# Plan — Align backend conventions with the reference codebase

| | |
|---|---|
| **Date** | 2026-05-23 |
| **Status** | Temporary plan — disposable. /clear 후 cold-resume용. |
| **Scope** | Backend architecture conventions를 the reference codebase 패턴에 align. |
| **Branch** | `worktree-be-code-arch-doc` (현재) |
| **Reference** | `the reference codebase/` |

> **For cold resume**: §1 (context) → §2 (먼저 verify) → §3 (변경 사항) → §6 (실행 순서). §2 verify 결과에 따라 §3~§5가 조정될 수 있음.

---

## §1. Context — 왜 이 계획이 있는가

### 1.1 발견된 문제

`docs/architecture/2026-05-23-code-architecture.md` §8 + `.claude/rules/backend-code-architecture.md` §6 + ADR-0018이 ORM 사용을 too-strict하게 금지했음 ("adapter에서도 SQLAlchemy ORM 금지, Core만 사용"). 

the reference codebase의 실제 패턴은 더 nuanced함: **SQLAlchemy ORM은 adapter 내부에서 contained 형태로 사용**. ORM 클래스는 private (`_Order`), adapter 공개 메서드는 domain type / primitive만 노출. 도메인은 ORM을 모름.

사용자는 the reference codebase 패턴 전체와 align하기로 결정 (옵션 B). UoW, ports 위치, fakes 조직, ClockPort 등 다른 패턴도 함께 검토.

### 1.2 추가로 발견된 *의심*

the reference codebase의 `adapters/fakes.py:1099` 에서:
```python
def _dict_to_execution_row(row: dict[str, object]) -> RunRecord:
    return RunRecord.model_validate(row)
```

`RunRecord`는 `the reference codebase.domain.execution`에서 import — **도메인 타입이 Pydantic 모델일 가능성**. 만약 사실이면 ADR-0018 ("Pydantic at boundary only")도 over-strict. §2 verify에서 반드시 확인.

---

## §2. Verify FIRST (실행 전 반드시) — Lazy reasoning 재발 방지

내가 도구 없이 추론한 부분이 다 맞는지 확인. 순서:

### 2.1 폴더 구조 verify

```bash
ls the reference codebase/
```
확인할 것:
- `contexts/` 폴더 있는지? (없으면 BC 분리 안 함 — single-BC project일 수도)
- `ports/` top-level 있는지?
- `application/` 또는 `use_cases/` 어느 쪽?
- `domain/` 위치 (top-level vs contexts/<bc>/)
- `composition.py` 위치

### 2.2 Domain 타입이 Pydantic인지 verify

```bash
ls domain/
```
그 다음 2~3개 file 읽기:
- `domain/execution.py` (위의 `RunRecord` 확인)
- `domain/audit_log.py` 또는 `domain/shift.py`
- 결과로 알 것: Pydantic BaseModel을 쓰는지, `@dataclass(frozen=True)`을 쓰는지, 둘 다 섞는지

**중요**: 이 결과가 ADR-0018 수정 / supersede / 보강 여부를 결정.

### 2.3 Port shape verify

```bash
ls ports/
```
1~2개 port file 읽기 — Protocol 이름 (suffix 컨벤션), 메서드 시그니처 (도메인 타입 반환), 위치 (BC-local인지 flat인지) 확인.

### 2.4 Use case shape verify

`use_cases/` 또는 `application/` 폴더 listing + 1~2개 file 읽기. UoW가 어떻게 사용되는지, cross-BC 호출 패턴이 있는지 확인.

### 2.5 Adapter ORM containment 패턴 verify (확장)

`postgres_orders.py`는 ORM containment 확인됨. 다른 file 1~2개 추가 확인:
- `postgres_shift_config.py`
- `postgres_runs.py`
- `sqlalchemy_admin_operations.py`

→ containment 일관성 검증. (혹시 다른 패턴 섞여 있는지)

### 2.6 추가 의심점

- `system_clock.py`는 `ClockPort` Protocol 명시 없음 — class에 `now()`만 있음. Protocol 정의는 어디 있나? `ports/clock.py`? 확인.
- `LegacyUserReader` (legacy_user_reader.py) — 이거 무엇인가? 별도 패턴인지 확인.
- 다른 adapter가 `aiokafka` 같은 거 사용하는지 (Kafka adapter 패턴 reference로 활용 가능)

---

## §3. 확인 후 변경 — Arch doc

`docs/architecture/2026-05-23-code-architecture.md` 수정:

### §3.1 §1.2 (folder layout)

**현재**:
- `contexts/<bc>/ports.py` (BC-local)

**변경 (verify 후)**:
- the reference codebase이 top-level `ports/` flat이면 → `ports/<noun>.py` 로 변경
- 만약 BC-local이면 → 유지

### §3.2 §3.2 (cross-BC sync queries)

ports 위치 변경 시 import 경로 업데이트:
- 현재: `from contexts.monitoring.ports import LineStateReader`
- 변경: `from ports.line_state import LineStateReader`

### §3.3 §3.3 (DomainEventDispatcher) + Unit of Work 추가

새 §3.3a (or §3.5) — **Unit of Work pattern**:
- `shared_kernel/uow.py` 또는 top-level에 `UnitOfWork` Protocol
- `adapters/sqlalchemy_uow.py`에 `SqlAlchemyUnitOfWork` (the reference codebase 패턴 그대로 mirror)
- `async with uow:` 안에서 도메인 event dispatch가 commit 전에 일어남
- Failure 시 `__aexit__`가 rollback

### §3.4 §5 (Clock)

**현재**: `Callable[[], datetime]` (간단) 또는 `Clock` Protocol (multi-method)
**변경**: 항상 `ClockPort` Protocol 사용 — the reference codebase과 정렬

```python
# ports/clock.py (location verify 필요)
class ClockPort(Protocol):
    def now(self) -> datetime: ...
```

`SystemClock` / `FixedClock` 양쪽 다 이 Protocol 구현.

### §3.5 §8 (Persistence) — 대폭 수정

**삭제**:
- "Forbidden in core: ... SQLAlchemy ORM declarative base on domain types" — keep this part, it's correct
- "Allowed at adapters: SQLAlchemy Core (not ORM)" — wrong, replace

**대체**:
- **Rule**: 도메인이 ORM 모르고, ORM 클래스가 adapter 밖으로 leak 안 하면 OK.
- ORM containment 패턴 example (the reference codebase `postgres_orders.py` mirror):
  ```python
  class _Base(DeclarativeBase): pass
  
  class _Order(_Base):
      __tablename__ = "orders"
      id: Mapped[int] = mapped_column(...)
      # ...
  
  class PostgresOrdersRepo:
      """Public adapter — Protocol implementation. ORM class never leaks."""
      def __init__(self, session: AsyncSession) -> None:
          self._s = session
      
      async def insert_order(self, *, line_id: int, ...) -> int:
          row = _Order(line_id=line_id, ...)
          self._s.add(row)
          await self._s.flush()
          return int(row.id)
  ```
- Convention: ORM declarative class는 항상 underscore prefix (private). Adapter public 메서드는 primitive / domain type만 반환.
- UoW pattern 사용 (위 §3.3 참조).

### §3.6 §10 (Tests)

추가:
- Fakes는 단일 파일 (`adapters/fakes.py`)에 모음. the reference codebase과 정렬.
- Cross-BC test scenario를 위해 `InMemoryDataset` 같은 shared mutable state class 도입.
- Fakes는 working implementation — DB-side CHECK constraint / generated column도 미러링.

### §3.7 §2 (DDD terminology)

**Possibly relax**:
- 현재: "Repository ✗ — use Reader/Writer ports"
- the reference codebase: `PostgresOrdersRepo` 같은 `*Repo` suffix 사용
- 변경 검토: `*Repo` suffix 허용 (adapter class 이름에 한해서). port 이름은 `*Reader` / `*Writer` / `*Port` 유지.

§2.1 naming consequences 업데이트.

---

## §4. 변경 — Rules file

`.claude/rules/backend-code-architecture.md` 수정 항목:

- **§1 Layer placement**: ports 위치 (top-level vs BC-local) verify 결과 반영
- **§4 Clock**: `Callable[[], datetime]` 제거, `ClockPort` Protocol을 default로
- **§6 ORM**: 완전 재작성 — containment rule + UoW + example
- **§9 Naming**: `*Repo` suffix 허용 추가 (adapter class에 한해)
- **§10 Tests**: 단일 `fakes.py` + `InMemoryDataset` 패턴 추가
- 끝에 reference 명시: "Reference impl: `the reference codebase`"

---

## §5. 변경 — Phase 1 plan header

`docs/plans/2026-05-22-phase-1-single-factory-vertical-slice.md`:

기존 known conflict 4종에서 ORM 관련 정정 + 추가:
- (c) Pydantic 위치 — `domain Pydantic 사용 여부 verify 결과에 따라 정정` (가능)
- 추가: (e) ORM containment 패턴 — adapter는 ORM 사용 OK, 단 private class
- 추가: (f) UoW pattern — session lifecycle은 `SqlAlchemyUnitOfWork`
- 추가: (g) Ports 위치 (verify 후 확정)
- 추가: (h) `ClockPort` Protocol always

---

## §6. 새 artifacts — ADR

작성 순서 (verify 결과 반영 후):

### ADR-0019: Persistence with ORM containment

ADR-0018 옆에 배치. 핵심: "ORM은 adapter 내부에서 contained — 도메인은 ORM 모름." the reference codebase `postgres_orders.py` 인용.

### ADR-0020: Unit of Work pattern

`SqlAlchemyUnitOfWork` 채택. Session lifecycle + per-feature repos + commit/rollback 통일. the reference codebase `sqlalchemy_uow.py` 인용.

### ADR-0021: Ports at <verify-determined-location>

verify 결과에 따라:
- top-level flat이면: "ADR-0021: Ports at top-level (flat)"
- BC-local이면: 별도 ADR 불필요 (현재 룰 유지)

### ADR-0022: ClockPort Protocol standardized

`Callable[[], datetime]` 대신 항상 Protocol. the reference codebase `system_clock.py` + `FixedClock` 패턴 인용.

### ADR-0023 (optional): Single fakes.py + InMemoryDataset

테스트 fake 조직 표준화. the reference codebase `fakes.py` 인용.

### ADR-0018 처리 (Pydantic)

verify §2.2 결과에 따라:
- **case A**: the reference codebase domain이 stdlib dataclass만 사용 → ADR-0018 유지
- **case B**: the reference codebase domain이 Pydantic 사용 → ADR-0018 supersede 또는 보강. 새 ADR-0024 "Pydantic in domain — when and how" 작성 검토. 룰 완화.

---

## §7. 새 artifacts — Memory

`/Users/cdlee/.claude/projects/-Users-cdlee-personal-sdf-dx/memory/`에 추가:

### reference_codebase.md (type: reference)

```yaml
---
name: reference-codebase
description: the reference codebase is the canonical reference impl for backend architecture patterns. Check first when deciding on persistence / ports / fakes / UoW / clock / Pydantic placement.
metadata:
  type: reference
---

Path: `the reference codebase/`

Confirmed patterns (verify by reading current files — patterns may evolve):
- SQLAlchemy ORM with containment (private `_Order`, public adapter returns primitives) — `adapters/postgres_orders.py`
- Unit of Work — `adapters/sqlalchemy_uow.py`
- Clock as Protocol — `adapters/system_clock.py` + `FixedClock` in fakes
- Single `adapters/fakes.py` with `InMemoryDataset` shared across fakes
- Ports location (flat vs BC-local) — VERIFY before citing

When making a backend architecture decision for sdf-dx, read corresponding the reference codebase file first.
```

MEMORY.md index에 1줄 추가.

---

## §8. 실행 순서 (commits)

각 commit은 cold-resume 가능하도록 self-contained하게.

1. **(1 commit)** §2 verification — 단순 reads + 결과를 이 plan 파일에 추가 ("Verified findings" 섹션 신설). plan은 working notes이므로 in-place 편집 OK.

2. **(1 commit)** ADR-0019 (ORM containment) + ADR-0020 (UoW) — 결정 시점에 즉시 박음.

3. **(1 commit)** ADR-0021 (ports location, 필요 시) + ADR-0022 (ClockPort) + ADR-0018 처리 (verify 결과 반영).

4. **(1 commit)** arch doc 업데이트 — §1.2, §2.1, §3, §5, §8, §10. 큰 Write.

5. **(1 commit)** rules file 업데이트 — §1, §4, §6, §9, §10.

6. **(1 commit)** Phase 1 plan header 업데이트 — known conflicts 정정 + 추가.

7. **(1 commit)** reference memory + MEMORY.md index.

8. **(1 commit, 마지막)** 이 plan 파일을 archive로 이동: `docs/plans/archive/2026-05-23-reference-codebase-alignment-plan.md`. AI-WORKFLOW case-01 작성 검토 (over-strict 규칙 → reference 발견 → 정렬 패턴).

---

## §9. Resume guide (after /clear)

1. 이 파일을 처음부터 끝까지 읽기.
2. §2.1~§2.6 verification 먼저 수행 — 결과를 이 파일에 inline 추가.
3. §3~§5 변경 사항을 verification 결과로 조정.
4. §8 commit 순서대로 진행.
5. 도중에 새로 발견되는 패턴 / 의문점은 이 파일 §10 (신설)에 기록 후 진행.

**Decision authority**: verify 단계에서 분명히 보이는 패턴은 그대로 채택. 모호한 케이스 (예: BC 분리 안 한 sdf-dx vs 분리된 the reference codebase의 차이)는 user에게 surface 후 결정.

**Anti-pattern 재발 방지**: "X is the reference standard" 만으로 carry하지 말 것. 패턴마다 *실제 코드*를 한 번씩 확인. 이 plan 자체가 이전 lazy reasoning audit의 결과물이므로 같은 실수 반복 금지.

---

## §10. (실행 중 추가될) Verified findings + new questions

(verify 단계에서 채워질 영역)

---

**End of temporary plan. /clear 후 §9 Resume guide부터 시작.**
