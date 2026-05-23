# Public Live Demo Deployment — Strategy Addendum

| | |
|---|---|
| **Date** | 2026-05-23 |
| **Status** | Draft — extends, does not supersede, `2026-05-22-sdf-manufacturing-dx-portfolio-design.md` |
| **Scope** | Adds a 3rd deliverable channel ("public always-on live URL") on top of the existing two (static GitHub repo, interview live demo). |
| **Trigger phase** | End of Phase 2 (멀티테넌시 완료 시점). Phase 2b는 *optional 후속 phase*로 추가됨 — 상황 보고 cut 가능. |
| **Author** | cd.lee.dev@gmail.com (+ Claude as pair) |

---

## 0. Why this addendum exists

원본 design spec §1.4는 portfolio의 3중 사용을 정의한다:
1. 서류용 정적 GitHub repo
2. 면접 라이브 데모
3. LLM 코딩 실시간 시연

원본은 **#2 / #3 모두 면접 자리에서 본인이 운전한다는 전제**다. 즉 *interviewer는 정적 코드만 보고 판단*한다.

이 addendum은 그 전제를 바꾼다: **interviewer가 직접 URL을 열고 5분 만져본 뒤 코드 리뷰로 들어가는 시나리오를 1순위 가정으로 격상**한다.

### 동기

이 portfolio가 *증명해야 하는 가장 약한 명제*:

> "기획자/디자이너 없이, 도메인 지식 없이, 조사만으로 이 정도 product taste의 시스템을 혼자 만들 수 있다."

이 명제는 ADR/표준 인용/Konsist 룰만으로는 증명되지 않는다. 그것들은 *engineering rigor* 시그널이지 *product taste* 시그널이 아니다. Product taste는 다음 셋의 동시 충족으로만 입증된다:

1. **첫 5초 인지 부담 0** — landing에서 "이게 뭔지" 즉시 이해.
2. **살아있는 데이터** — 라인 상태가 *실시간으로* 바뀌고 OEE가 갱신.
3. **납득되는 도메인 디테일** — 라인 토폴로지, 알람 시나리오, 교대 패턴이 *그럴듯함*.

이 셋은 정지 스크린샷이나 영상으로도 일부 전달되지만, **본인이 마우스로 tenant switcher를 돌려보고 알람을 ack 해봐야 신뢰가 형성**된다. 따라서 always-on public URL이 부차적 채널이 아닌 *1차 증거물*로 승격된다.

### 무엇을 바꾸지 *않는가*

- 원본 design spec §1~§17 모두 유효.
- Phase 1 deliverable 변경 없음 (local docker-compose only).
- Engineering principles (§2) 변경 없음.
- Architecture & components (§3) 변경 없음 (단, §3에 deployment target 한 줄 추가는 ADR로 반영).
- Repo 구조 (§9) 변경 없음 (단, `infra/` 하위에 deployment 디렉토리 추가).

### 무엇을 바꾸는가

- Phase 2 종료 시점에 **"public live URL 도달"이 새 AC 항목으로 추가**된다 (이 문서 §6).
- Phase 5 (Live Demo Prep)에 "public URL 사전 점검 리허설" 항목 추가.
- KNOWN-UNKNOWNS에 deployment 관련 한계 추가 (이 문서 §8).
- 새 ADR 한 개 발행 예정 — "Public deployment platform" (이 문서 §5 참조; 작성은 Phase 2 진입 시점).

---

## 1. Strategic Shift Summary

| 항목 | 원본 (design spec §1.4) | 본 addendum 적용 후 |
|---|---|---|
| 평가자가 코드를 보는 방식 | 정적 repo + 면접 라이브 | 정적 repo + **public URL 자가 탐색** + 면접 라이브 |
| 데모 방문자가 입는 역할 | 해당 없음 (면접 자리에서 본인이 모든 역할 운전) | **A-OP role (Phase 2 시점) → +A-TA role (Phase 2b 시점, optional)**. 별도 guest role 없음. |
| 데모 신뢰성 책임 분포 | 면접 시점 본인 100% | 면접 시점 본인 + **24/7 백그라운드 운영** |
| Product taste 시그널 | 코드 품질·ADR로 간접 추론 | **URL 첫 5초 + role별 시점 시연으로 직접 입증** |
| 시뮬레이터 가동 시간 | 면접/녹화 시에만 | **상시 가동 (Phase 2~5 내내)** |
| 운영 부담 | 0 (로컬 only) | 월 ~€7 + 모니터링 셋업 |
| 실패 시 데미지 | 면접 1회 다시 잡으면 끝 | **URL 다운 = 24/7 portfolio 손상** |

핵심 트레이드오프: *portfolio의 표면적이 넓어진 만큼 실패 표면도 넓어진다.* §7 (위험 & cut policy)에서 완화책 명시.

---

## 2. Deployment Timing — Why "Phase 2 end"

| 후보 시점 | 평가 |
|---|---|
| Phase 1 종료 시 (단일 공장) | ❌ Tenant switcher 없음 = "혼자 만든 진짜 multi-tenant" 시그널 약함. 단일 공장 라이브 데모는 정지 영상으로 충분. |
| **Phase 2 종료 시 (멀티테넌시 완료)** | ✅ KR/US/IN 3공장 switcher가 product taste의 핵심 증거. 게스트 인증/권한도 같이 준비됨. |
| Phase 3 종료 시 (production readiness 후) | ⚠️ 너무 늦음. Phase 3 자체가 길어 deploy가 면접 일정에 안 맞을 위험. |
| Phase 4 종료 시 (use case 확장 후) | ⚠️ 너무 늦음 + Phase 4는 cut 가능 항목. |

**결정**: Phase 2 종료 시 deploy 1차 가동. Phase 3에서 관측성·CI/CD가 들어오면 deploy 파이프라인을 *그 위에 올린다* (역순 아님).

### 의존성

Phase 2 종료 AC (design spec §13.2) 모두 충족 후:
- 3개 공장 (KR/US/IN) 시드 데이터 안정적으로 흐름
- JWT 인증 + 역할 기반 권한 작동 (guest viewer 역할 필요)
- 다국어 (ko/en + 1개 더)
- `POST /tenants` 자동 온보딩 동작

이 중 **guest viewer 역할은 원본 design spec에 명시되지 않은 항목**이므로 §6에서 AC 보강한다.

---

## 3. New Requirements Introduced by Public Live Demo

원본 spec에 없던 *운영 책임*이 5가지 추가된다.

### 3.1 Always-on simulator

- Phase 1~5 내내 시뮬레이터 컨테이너 24/7 가동.
- 죽으면 dashboard가 정지 → first impression 박살.
- 완화: systemd `Restart=always` + Docker `restart: unless-stopped` + 외부 uptime probe (UptimeRobot 무료 50 monitors).

### 3.2 Demo tenant seed quality

- KR/US/IN 3공장 시드 데이터가 *그럴듯해야* product taste 시그널이 작동.
- 라인 토폴로지 (ISA-95 L0~L2), 설비 명명, 알람 룰, 교대 시간 — 도메인 reasonableness 검수 필요.
- 별도 스크립트: `scripts/seed-demo-tenants/` (Phase 2 plan에 task 추가).
- 변동폭이 너무 작으면 "정적 시뮬레이터"로 보이고, 너무 크면 "랜덤 노이즈"로 보임. *진폭·주기 튜닝이 product taste의 직접 증거*.

### 3.3 Seeded credentials & role mapping

별도 "guest" 도메인 역할 모델을 *폐기* — 외부 방문자는 *기존 primary actor role*을 입어보는 방식이 product taste 시그널이 더 강함 (2026-05-23 결정). 신규 역할을 만들지 않고 design spec §13.2의 "tenant admin / operator / viewer" 3종 role 중 일부를 *demo seed credential에 매핑*.

| 단계 | 노출 자격증명 | 매핑되는 role | 권한 | 시연 효과 |
|---|---|---|---|---|
| **Phase 2 deploy 시점** | `op_demo / op_demo` | A-OP (operator) | read-only (모든 mutating endpoint 403) | 방문자가 operator 시점에서 라인 모니터링, tenant switcher 사용 |
| **Phase 2b (optional)** | + `admin_demo / admin_demo` | + A-TA (tenant admin) | + demo namespace 한정 onboarding 가능 | 방문자가 admin이 되어 새 공장 30초 안에 생성, switcher에 즉시 등장 |

핵심 룰:
- **A-OP는 read-only**. ack alarm조차 demo 환경에선 허용하지 않음 — 어뷰즈 표면을 0으로. Demo의 *살아있는 느낌*은 시뮬레이터의 데이터 변동만으로 충분.
- **A-TA의 쓰기는 *demo namespace 격리***. Phase 2b에서 admin이 만든 공장은 `tenant_demo_*` prefix 하에 격리되어 본 KR/US/IN portfolio 데이터에 침범 불가.
- 1시간마다 demo namespace 부분 리셋: A-TA가 만든 demo 공장 삭제 + 시뮬레이터 detach (Phase 2b만 해당).
- 두 자격증명 모두 *README 첫 화면*에서 보임. 사용자가 찾으러 다닐 필요 없음.

Why this framing matters: 면접관이 "viewer로 클릭만 하고 끝"이 아니라 *"operator의 일을 30초 해보고, (Phase 2b가 살아있다면) admin이 돼서 공장도 만들어본다"* — 이것이 "도메인 역할을 *내가 모델링했다*"는 product taste 시그널의 직접 증거.

### 3.4 Landing splash / cold-visitor onboarding

- 도메인 모르는 면접관이 첫 5초에 길을 잃지 않아야 함.
- 후보 형식:
  - Modal overlay: "이 포트폴리오는 무엇인가" 3줄 + "5초 가이드 보기" / "그냥 보기" 두 버튼.
  - 또는 `/about` 별도 route에서 시작 → "dashboard 열기" CTA.
- *디자이너 없이 만든 것 강조* 노선이라면 splash 자체가 product taste의 1차 시연. 이 자체가 별도 디자인 작업으로 잡힘 (Phase 2 plan에 task).

### 3.5 Operational monitoring

- Uptime probe (UptimeRobot 무료).
- Cloudflare Analytics (request count, 4xx/5xx 비율).
- Optional: Sentry 무료 tier (FE/BE 에러).
- *self-host Grafana는 Phase 3까지 미룸* (Phase 2 deploy 시점에는 외부 무료 도구로 cover).

---

## 4. Platform & Architecture Outline

> **Note**: 본 §4는 *strategy-level outline*이다. 구체적 결정은 Phase 2 진입 시점에 **`docs/ADR/NNNN-public-deployment-platform.md`** 로 별도 발행.

### 4.1 Platform 후보

| 후보 | 월 비용 | 적합도 | 비고 |
|---|---|---|---|
| **Hetzner CX32** (4 vCPU / 8GB / 80GB SSD) | ~€7 | ⭐ 기본값 | Kafka + Timescale + HiveMQ + 시뮬레이터 + ingest + api + nginx 모두 docker-compose 1개로 수용 가능. EU 리전. |
| **Oracle Cloud Free Tier Ampere ARM** (4 vCPU / 24GB / 200GB) | $0 | ⭐ 대안 | 가입·승인 까다로움. ARM 이미지 빌드 필요 (Kotlin/Python/JS 모두 OK). 무료지만 *자원 회수 위험 존재*. |
| Hetzner CX22 (2 vCPU / 4GB) | ~€4.5 | ⚠️ 빠듯 | Kafka + Timescale 동시 가동 시 swap 증가. |
| AWS Lightsail $40 (8GB) | $40 | ❌ 과지출 | 브랜드 친숙도 외 이점 없음. |
| GKE/EKS managed | $70+ | ❌ 과잉 | `infra/k8s/` 매니페스트 예시(원본 §3.1 Phase 3)가 이미 같은 시그널 제공. |
| Fly.io / Railway | 가변 | ⚠️ 어색 | Kafka/MQTT stateful 워크로드와 PaaS 모델 궁합 좋지 않음. |

**기본값**: Hetzner CX32. Oracle Free Tier 가입이 1시간 안에 되면 그쪽으로 전환 검토.

### 4.2 Edge / TLS / DNS / 보호 계층

- **Cloudflare** 단일 스택:
  - DNS (무료)
  - SSL/TLS (무료, Full strict)
  - Tunnel (`cloudflared`) — origin IP 노출 차단, 인바운드 방화벽 0 포트로 운영 가능
  - Rate limit + Bot Fight Mode (무료 tier)
  - Cloudflare Analytics (무료)
- 도메인: `.dev` 1개 매년 ~$15. (현재 사용 가능 도메인 확인은 Phase 2 진입 직전)

### 4.3 Origin compose 추가 사항

원본 §9 `infra/docker-compose.prod.yml`을 기준으로 다음 서비스 *추가*:
- `cloudflared` (Cloudflare Tunnel client)
- `simulator-keepalive` 또는 systemd 유닛 (시뮬레이터 죽으면 즉시 재기동)
- `demo-reset-cron` (1시간마다 demo tenant 부분 리셋)

`docker-compose.prod.yml`에 변경되는 *모든 항목*은 commit 단위로 ADR과 cross-reference.

### 4.4 변경되지 않는 것

- Application 코드는 *local docker-compose와 동일* — `SDF_MODE=real` 그대로.
- DB schema, Kafka topic naming, FE bundle — 동일.
- *즉 production deploy가 코드/도메인 모델에 침입하지 않는다*. Functional Core / Imperative Shell 원칙(§2.1) 유지.

---

## 5. ADR Roadmap Delta

원본 design spec §12 ADR 목록에 다음을 추가한다 (번호는 작성 시점 결정):

| 신규 ADR | Phase | 비고 |
|---|---|---|
| Public deployment platform (Hetzner vs Oracle Free vs PaaS) | Phase 2 진입 시 | §4 outline → 최종 결정 |
| Cloudflare 단일 스택 (DNS+SSL+Tunnel+RateLimit) — 직접 nginx + Let's Encrypt와의 비교 | Phase 2 | |
| Seeded-credential → role 매핑 + demo namespace 격리 (A-OP read-only seed, optional A-TA seed) | Phase 2 | §3.3 결정 후. Phase 2b ADR delta는 Phase 2b 진입 시. |

---

## 6. Acceptance Criteria Delta

원본 design spec §13에 *2개 phase의 AC 항목을 추가*한다. (원본 AC 항목은 그대로 둠.)

### Phase 2 AC 추가분 (deploy 가동 필수)

- [ ] Public URL이 도달 가능 (Cloudflare-fronted HTTPS, valid cert)
- [ ] 3개 demo tenant (KR/US/IN) 시뮬레이터가 24시간 *연속 가동* 후 dashboard 정상 (`uptime ≥ 24h` 사전 검증)
- [ ] `op_demo / op_demo` 자격증명이 README 첫 화면에서 보임
- [ ] A-OP role로 로그인 → tenant switcher 작동 → 라인 상태 실시간 갱신 확인 (1초 이내 push)
- [ ] A-OP는 모든 mutating endpoint에서 403 (write 차단 검증)
- [ ] Landing splash 또는 `/about` route 존재 — 도메인 모르는 방문자가 첫 30초 안에 "이게 무엇이고 어디부터 봐야 하는지" 파악 가능
- [ ] UptimeRobot 모니터 설정 + 다운 시 본인 이메일/슬랙 알림

### Phase 2b AC 추가분 (optional — cut 가능, 실행 시 통과 필수)

> Phase 2b는 *상황 봐서 패스 가능한 phase*. 진입 결정은 Phase 2 종료 + 면접 일정 여유 확인 후.

- [ ] `admin_demo / admin_demo` 자격증명이 README에서 보임 (Phase 2 자격증명과 함께 노출)
- [ ] Landing에 persona picker — "Try as Operator" / "Try as Tenant Admin" 양자 선택 UI
- [ ] A-TA role로 로그인 → admin UI에서 새 demo factory 생성 → tenant switcher에 즉시 등장 (30초 이내)
- [ ] 새 demo factory에서 시뮬레이터 자동 attach 후 라인 상태 표시 (60초 이내)
- [ ] A-TA의 onboarding 효과가 `tenant_demo_*` namespace에 격리 — KR/US/IN portfolio 데이터에 침범 불가 (격리 테스트 통과)
- [ ] UC-003 "Tenant admin onboards a new factory" 작성 + E2E 통과 (`status: implemented`)
- [ ] 1시간 demo namespace 부분 리셋 cron 작동 — A-TA가 만든 demo factory 정리 포함

### Phase 5 AC 추가분 (원본 §13.5)

- [ ] 면접 *전날*에 public URL 풀 시나리오 1회 통과 (체크리스트 별도)
- [ ] 면접 시각 ±1시간 동안 URL이 살아있음 (UptimeRobot 알림 무발생)
- [ ] URL이 다운된 경우의 *fallback 대본* — "지금 origin이 응답을 안 하니, 로컬에서 동일 환경 띄워서 보여드리겠습니다" (영상 백업이 §11.4)

---

## 7. Risks & Cut Policy

### 7.1 신규 리스크

| 리스크 | 영향 | 완화 |
|---|---|---|
| 시뮬레이터가 면접 직전 죽음 | 라이브 데모와 portfolio 동시 손상 | systemd restart + UptimeRobot + §13.5의 fallback 대본 |
| 어뷰즈 (악성 트래픽, scraping) | VPS 자원 소진 | Cloudflare Bot Fight Mode + rate limit + A-OP read-only (§3.3) |
| Phase 2b 활성화 시 A-TA의 onboarding이 portfolio 데이터에 침범 | Portfolio 첫인상 손상 | `tenant_demo_*` namespace 격리 + 1시간 부분 리셋 cron (§3.3) |
| Origin DB 디스크 풀 | 시계열 무한 증가 | TimescaleDB retention policy 7일 (demo 환경 한정) |
| Cloudflare 무료 tier 한도 도달 | URL 다운 | Phase 2 시점에는 도달 가능성 극히 낮음. 도달 시 origin direct로 우회. |
| VPS provider 장애 | URL 다운 | Phase 5에서 *영상 백업이 1차 fallback* 으로 이미 잡혀 있음 (원본 §11.4). |
| 비용 폭주 | 개인 부담 | Hetzner 고정요금 / Oracle 무료 → 폭주 거의 없음. AWS 변동 옵션은 §4.1에서 제외. |

### 7.2 Cut policy

시간 압박 시 cut 순서 (원본 §10의 cut 정책에 *prepend*):
1. **Phase 2b 전체** — A-TA persona, admin UI, persona picker, demo namespace 격리, UC-003. *가장 droppable*. Cut 시 deploy는 A-OP read-only 시연만 가지고 진행, "Phase 2b는 시간 여유 시 후속 작업" 으로 README에 표기.
2. **Demo namespace 1시간 리셋 cron** (Phase 2b 한정) — 수동 일일 리셋으로 대체.
3. **Landing splash 폴리시** — 단순 1-pager로 시작 후 점진 개선.
4. **다국어 3번째 언어** — 원본 AC였으나 ko/en 만으로 충분.
5. (원본 cut policy 진입: Phase 4 → Phase 5 일부 → Phase 3 일부)

**Cut 불가**: Public URL 자체, A-OP `op_demo` 자격증명, always-on 시뮬레이터, uptime 모니터링. 이 셋이 없으면 본 addendum 의미가 0.

### 7.3 Kill switch

다음 조건이 발생하면 *deploy 자체를 포기하고 정적 portfolio로 회귀*:
- Phase 2 종료가 면접 예정일 ≤ 7일에 임박했고 24h 가동 안정성이 확보되지 않음.
- 월 비용이 €15을 넘어감.
- Demo tenant 데이터 품질이 product taste 시그널보다 *오히려 약점*이 됨 (interviewer가 "왜 데이터가 이렇게 부자연스럽나"를 묻는 지점에 도달).

---

## 8. KNOWN-UNKNOWNS Delta

원본 §14에 다음 *deployment 한계*를 추가한다 (실제 작성은 `docs/KNOWN-UNKNOWNS.md`에 반영):

- 실제 production 트래픽 패턴 (peak burst, ICS network constraint) — demo 환경에서는 합성.
- Cross-region latency (KR origin → 다른 대륙 interviewer) — Cloudflare CDN으로 부분 완화, *실측은 안 함*.
- Demo 환경의 abuse 시나리오의 완전한 모델링 — Phase 2는 *A-OP read-only*로, Phase 2b(살아있다면)는 *namespace 격리 + 부분 리셋*으로 *80% cover*에 만족. 100% 모델링은 안 함.
- 진짜 24/7 hot-patch 정책 — demo 환경에서는 *interview 시간 회피 후 단순 재배포*로 대체.

---

## 9. Open Questions

Phase 2 진입 시점까지 미해결 — ADR 발행 시 결정:

1. **Hetzner CX32 vs Oracle Cloud Free Tier 최종 선택** — Oracle 가입 가능 여부 (Korean 신용카드 인증 변동성) 확인 후.
2. **도메인 이름** — `.dev` 후보 사전 확인 (sdf-dx-demo.dev / cdlee-sdf.dev 등) Phase 2 진입 직전 매입.
3. **Landing splash 형식** — modal vs separate route vs hero section in dashboard. *디자이너 없이 만든 것 강조* 노선이라 별도 사용자 테스트가 필요할 수 있음.
4. **시드 데이터 변동 모델** — 라인 OEE 진폭·주기·이벤트 분포의 baseline. ISO 22400 산식 자체는 결정적이지만 *입력 신호의 자연스러움*은 별도 튜닝.

Phase 2b 진입 시점에 결정 (Phase 2b 미실행 시 폐기):

5. **Persona picker UX** — landing에서 "Try as Operator" / "Try as Tenant Admin" 양자 동등 노출 vs Operator 1차 / "Admin도 가능" CTA 2차. Operator가 메인 사용자라는 도메인 정직성 vs 양자 동등의 단순함.
6. **`tenant_demo_*` namespace 격리 깊이** — Postgres schema 분리만으로 충분한지 vs 별도 Kafka topic prefix까지 분리할지. *원본 schema-per-tenant 패턴 재사용*이 기본 가정.
7. **A-TA admin UI 범위** — 새 공장 생성만 vs 라인 추가 / 설비 추가까지. 30초 시연 효과 vs 구현 복잡도.
8. **Phase 2b 진입 결정 기준** — Phase 2 종료 시점에 *남은 시간 / 면접 일정 / 24h 안정성*의 3축으로 go/no-go. 기준선 미정.

---

## 10. Relationship to Original Strategy Doc

이 문서는 원본 design spec을 *대체하지 않는다*. 원본은 *frozen-at-project-start* 전략 문서로 그대로 두고, 본 addendum이 *전략 변경분만* 격리해 보관한다.

원본 design spec에서 명시적으로 변경되는 지점:

| 원본 위치 | 원본 내용 | 본 addendum 적용 후 |
|---|---|---|
| §1.4 Usage Scenarios | 3중 사용 (정적 GitHub / 면접 라이브 / LLM 실시연) | 위 3개 + **public always-on URL** (1차 채널로 승격) |
| §10 Phase 2 deliverable | "설정 기반 확장 가능한 멀티테넌트 플랫폼" | + **public URL 도달 + A-OP read-only 진입 경로** |
| §10 Phase 추가 | Phase 1 → 2 → 3 → 4 → 5 | + **Phase 2b (optional)** — A-TA persona + admin UI + persona picker. Phase 2와 3 사이. cut 가능. |
| §11 Live Demo Strategy | 면접 자리 시연 위주 | + **사전 self-serve URL** (interviewer가 면접 전/후 자가 탐색) |
| §13.2 Phase 2 AC | 9개 항목 | + 7개 항목 (이 문서 §6 Phase 2 분) |
| §13 새 phase AC | (없음) | + **§13.2b** (Phase 2b AC 7개) — 이 문서 §6 Phase 2b 분 |
| §14 KNOWN-UNKNOWNS | 운영 사실주의 한계 | + **deployment 한계 4종** (이 문서 §8) |

이외 모든 항목은 원본 그대로 유효하다.

---

## 11. Next Step Trigger

본 addendum이 "active"로 전환되는 트리거:

> Phase 1이 §13.1 AC 모두 통과하여 `phase-1` tag가 찍힌 직후.

그 시점에 다음 작업이 *Phase 2 plan 초안의 첫 번째 섹션*으로 진입한다:
1. ADR — public deployment platform 결정.
2. ADR — Cloudflare 단일 스택 정당화.
3. ADR — Seeded-credential → role 매핑 + demo namespace 격리 (§3.3).
4. Phase 2 plan에 §3 요구사항 5종(always-on simulator, demo tenant seed, A-OP seeded credential, landing splash, monitoring)을 task 단위로 분해.

Phase 2b는 *별도 trigger*: Phase 2 종료 시점에 §9의 question 8 (Phase 2b 진입 결정 기준)을 평가하여 go/no-go. Go인 경우에만 `docs/plans/YYYY-MM-DD-phase-2b-tenant-admin-persona.md` 작성.

원본 design spec §17 (Open Questions)에는 본 addendum과의 cross-reference만 추가하면 충분하다 (그것도 *원본을 안 건드린다는 원칙* 상, addendum 끝의 cross-ref 표만으로 충분).

---

**End of Addendum.**
