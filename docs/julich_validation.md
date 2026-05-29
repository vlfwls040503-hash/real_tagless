# Jülich 4D090 AVM 병목 형태/동역학 재현 검증

**작성일**: 2026-04-20
**목적**: 기존 AVM 파라미터로 현실 병목(Jülich 4D090, w=100cm)의 형태·동역학을 재현하는지 확인 (파라미터 튜닝 아님)
**판정**: **FAIL — partial** (속도 프로파일만 충족)

---

## 1. 실험 개요

### 1.1 대상 데이터
- **실측**: `data/julich/4D090_trajectory.csv` (w=100cm, h0 normal, 129명, 75.16s)
- **시뮬**: `data/julich/simulated_4D090.csv` (129명 × 5 seed, 100s)

### 1.2 시뮬 구성 ([simulation/julich_bottleneck.py](../simulation/julich_bottleneck.py))

**Geometry**
- 병목 폭 1.0 m, 길이 0.2 m (원점 중심)
- 초기 배치: **반원 반경 3.3 m** (스펙 2m는 129명 수용 불가 — hex 간격 0.36m로 조밀 배치)
- 병목 후: x∈[0.2, 3.2], y∈[-2, +2]

**AVM 파라미터 (기존 프로젝트 값 그대로)**
```python
time_gap=0.80, radius=0.15,
strength_neighbor_repulsion=8.0, range_neighbor_repulsion=0.1,
wall_buffer_distance=0.1, anticipation_time=1.0, reaction_time=0.3,
desired_speed ~ Weidmann N(1.34, 0.26) clip[0.8, 2.0]
```

**초기 조건 / 실행**
- 129명 t=0 동시 spawn, 초기 속도 0
- `SIM_TIME=100s`, dt=0.04s (25fps, Jülich 맞춤)
- seed 42~46 (5회)

### 1.3 좌표 정렬 확인
- Jülich 4D090 x 범위 [-7.70, +2.00], 속도 프로파일에서 x=0 기점으로 속도 급증 (0.29 → 0.70 m/s) → **Jülich 병목 위치 = x=0** 확인
- 시뮬도 x=0에서 병목 시작 → **좌표계 정렬 OK**

### 1.4 spec 대비 차이점
| 항목 | spec | 실제 | 이유 |
|---|---|---|---|
| 반원 반경 | 2 m | **3.3 m** | 129명 × 반경 0.15 패킹 불가 (밀도 20 ped/m² 초과) |
| 초기 배치 | 무작위 | hex grid + 소량 jitter | 초기 중첩 violation 방지 |
| SIM_TIME | 100 s | 100 s | |
| 저장 간격 | 0.04 s | 0.04 s | |
| agent 수 | 129 | 129 | ✓ |

---

## 2. 결과 요약

| 지표 | 실측 | 시뮬 | 기준 | 판정 |
|---|---:|---:|---|---|
| A) 밀도 공간 상관 r | — | — | > 0.6 | **FAIL** (r = **-0.10**) |
| B) 밀도 시계열 상관 r | — | — | > 0.7 | **FAIL** (r = **0.41**) |
| D) 속도 프로파일 RMSE | — | — | < 0.25 m/s | **PASS** (RMSE = **0.15**) |
| E) 축적 범위 오차 | -4.60 m | -3.04 m | < 30 % | **FAIL** (**34 %**) |
| **유출량 (참고)** | **1.72 ped/s** | **0.47 ped/s** (평균, seed별 0.01~0.96) | — | 보조 |

---

## 3. 지표 상세

### A) 대기 구역 밀도 공간 분포

**Heatmap**: [figures/julich_density_heatmap.png](../figures/julich_density_heatmap.png)

- 셀 0.2 m × 0.2 m, 시간 창 t=[5, 60]s 평균
- 공간 상관계수 **r = -0.10** (사실상 무상관)
- 실측 max: 7.25 ped/m² (셀 점유율 29%, 혼잡 구역)
- 시뮬 max: 25.00 ped/m² (= 셀 100% 점유, **stuck agent 존재 의미**)

**관찰**
- 실측: 병목 바로 앞 0.5m에서 고밀도 → 뒤로 완만히 감소하는 **쐐기형 밀집**
- 시뮬: 병목 바로 앞에 stuck agent 클러스터 → 주변은 낮음 → **국지적 정체**가 공간으로 번지지 못함
- 차이 heatmap (실측 - 시뮬): 대부분 양수 (실측이 더 넓게 밀집), 시뮬은 좁은 hot spot만 형성

### B) 병목 앞 0.5 m 밀도 시계열

**그래프**: [figures/julich_density_timeseries.png](../figures/julich_density_timeseries.png)

- 영역: x∈[-0.5, 0], |y|<1.0 (1 m²)
- 시간 상관 **r = 0.41** (약한 양의 상관)
- 피크 밀도: 실측 **6.04** ped/m² (t=23s) vs 시뮬 **6.74** ped/m² (t=23s)
- **피크 시점은 정확히 일치**, 피크 값도 유사

**관찰**
- 초기 (t < 10s) 증가 경향은 유사
- 중반 (t=30~50s) 실측은 고밀도 유지, 시뮬은 정체/해소 반복 (seed별 분산)
- 후반 (t > 55s) 실측 감소 (유출 완료), 시뮬은 느리게 감소 (gridlock 지속)

### C) 궤적 수렴 패턴

**그래프**: [figures/julich_trajectory_overlay.png](../figures/julich_trajectory_overlay.png)

- 랜덤 20명 궤적 비교
- **실측**: 병목 앞 1~2m부터 부채꼴형 수렴 (y 범위 축소하며 x방향 직진)
- **시뮬**: 궤적이 짧음 (대부분 agent가 끝까지 이동 못함), 병목 바로 앞에서 x 정체 후 소수만 관통

### D) 속도 공간 분포

**그래프**: [figures/julich_velocity_profile.png](../figures/julich_velocity_profile.png)

- x 구간 -3m ~ +2m, 0.2m bin 평균 속도
- **RMSE = 0.154 m/s** (기준 0.25 이하 → **PASS**)
- 최저 속도: 실측 0.15 m/s (x≈-2.5m), 시뮬 0.01 m/s (x≈-2.7m) — 시뮬이 더 정체
- 병목 통과 후 가속 패턴(x>0.2에서 속도 증가)은 두 곡선 모두 유사

**해석**: 속도 RMSE만 PASS인 이유 — 정체 구역에서 둘 다 **낮은 속도**여서 수치 차이가 작게 잡힘. 하지만 "동역학의 유사성"이 아니라 **"둘 다 멈춰 있어서 같아 보이는 것"**에 가까움.

### E) 축적 범위 (밀도 ≥ 1 ped/m²)

- 실측 평균 큐 꼬리 위치: **x = -4.60 m** (병목 뒤 4.6m까지 큐 형성)
- 시뮬 평균 꼬리: **x = -3.04 m**
- 오차 **34 %** (기준 30% 초과 → **FAIL**)
- **구조적 제약**: 시뮬은 반원 3.3m로 물리적 한계. 실측(-7.7m까지 agent 존재)과 직접 비교 불공정.

### 정성 시각화

**스냅샷**: [figures/julich_snapshots_comparison.png](../figures/julich_snapshots_comparison.png)

t=10, 20, 30, 45, 60s에서 실측(상단)/시뮬(하단) 산점도:
- **t=10s**: 실측은 이미 병목 앞 쐐기 형성. 시뮬은 hex grid 패턴이 아직 남아있음 + 병목 앞 소수만 이동.
- **t=30s**: 실측은 쐐기가 뒤로 물러나며 유출 진행. 시뮬은 초기 위치 거의 그대로, 병목 앞 압착.
- **t=60s**: 실측은 거의 비어감. 시뮬은 여전히 다수 agent가 원위치 부근.

**결론**: 시뮬은 **초기 hex 격자 패턴이 60s까지 상당 부분 유지**됨. 줄이 "형성되었다가 해소"되는 실측 동역학을 재현 못함.

---

## 4. 유출량 (보조 참고)

| seed | 유출 agent | 유출률 (ped/s) |
|---:|---:|---:|
| 42 | 8 | 0.08 |
| 43 | 57 | 0.57 |
| 44 | 1 | 0.01 |
| 45 | 96 | 0.96 |
| 46 | 75 | 0.75 |
| **평균** | **47.4** | **0.47** |
| **실측** | **129 / 75.16s** | **1.72** |

- 시뮬 유출률 실측의 **27 %** 수준
- seed별 편차 거대 (0.01~0.96 ped/s) → **확률적 gridlock**: 동일 파라미터에서 초기 배치 작은 차이로 완전 정체 vs 부분 유출 갈림
- 이 편차 자체가 AVM의 **메타 안정성 부족** 징후

---

## 5. 판정 및 해석

### 5.1 종합 판정: **FAIL (partial)**

| 기준 | 결과 |
|---|---|
| 모든 지표 충족 | ✗ |
| 속도 RMSE | ✓ (하지만 의미적 PASS 아님 — §3 D 해석 참조) |
| 공간 밀도 패턴 | ✗ (r=-0.10, 무상관) |
| 시계열 밀도 | ✗ (r=0.41, 약상관) |
| 축적 범위 | ✗ (34%, 구조적 원인 포함) |

### 5.2 재현 안 되는 측면 (구체)
1. **줄(queue) 형성의 공간 구조**: 실측의 부채꼴·쐐기형 압축 패턴이 시뮬에서 소실. 시뮬은 점상 hot spot + 초기 격자 잔존.
2. **동역학 흐름**: 실측은 "줄이 생기고 → 병목으로 쏠려 → 유출되며 짧아짐"의 명확한 phase가 있으나, 시뮬은 gridlock에 빠져 phase 전환 없음.
3. **확률적 안정성**: seed별 유출 1~96명 편차. 동일 파라미터·동일 초기 패턴에서 결과가 양극화 → 물리 모델이 비결정론적 gridlock 민감.

### 5.3 원인 추정

**A. AVM 자체의 한계 (가장 유력)**
- jupedsim AVM은 **등방성 반발**(strength_neighbor_repulsion=8.0, range=0.1) → 고밀도에서 agent가 사방으로 동일 힘 받아 방향 불안정 (CLAUDE.md의 "진동 원인은 방향 불안정" 주석과 일치)
- anticipation_time=1.0은 agent가 미래 충돌을 회피하려 역행·정체 강화
- 초기 packed configuration → 다수 agent가 동시에 anticipation 상호작용 → deadlock

**B. 한국/독일 보행자 차이는 아님**
- Jülich 실험 참가자는 독일인 아닌 **학생·자원자**, 태그리스 통근자와는 성격 다름. 다만 본 실험은 "물리 모델 자체의 현실성"을 보는 것이므로 문화 변수 영향은 적음.

**C. 병목 geometry 차이**
- 실측 holding area는 길이 ~7.7m (유입 gradual). 본 시뮬은 3.3m 반원에 packed → **초기 밀도 차이**가 AVM 반응에 지배적.
- 공정 비교를 위해서는 시뮬 holding area를 실측과 동일하게 재현해야 함.

**D. 파라미터 미보정**
- time_gap=0.80은 Rzezonka 2022의 **"첨두 통근자 중간값"**. 실제 병목 실험 값은 0.5 이하 가능.
- 현재 파라미터는 **플랫폼 일반 보행용**, 병목 압축용 아님.

### 5.4 후속 보정 방향
1. **AVM 파라미터 민감도 분석** (tune만 금지된 이번과 달리, 별도 과제)
   - time_gap 0.3~1.0 스캔
   - strength_neighbor_repulsion 2~10 스캔
2. **초기 배치 완화**: packing 밀도를 4~5 ped/m² 이하로
3. **AVM → CFSM V2 대체 테스트**: 현재 메인 시뮬은 CFSM V2이므로 동일 Jülich 조건 재실행 비교
4. **Gradient-based spawn**: 실측처럼 agents가 먼 holding에서 점진적 접근하는 방식

---

## 6. 에스컬 시뮬 측정 신뢰도에 대한 함의

현 에스컬 병목 시뮬 ([run_west_simulation_cfsm_escalator.py](../simulation/run_west_simulation_cfsm_escalator.py))은:
- **CFSM V2** 기반 (본 검증의 AVM과 다른 모델)
- **소프트웨어 큐**가 병목 물리 제어 (에이전트 위치 직접 관리, 진짜 물리적 압축 아님)
- 따라서 본 검증의 FAIL 결과가 **직접적 타격은 아님**

다만:
- 에스컬 실험에서 AVM 계열 모델을 물리 압축용으로 사용하려는 시도는 **신뢰 어려움** (본 결과로 확인)
- 소프트웨어 큐 방식이 현실 병목의 "쐐기형 압축 패턴"을 재현하지 못하는 한계는 여전히 존재 → 본 시뮬의 **결과 해석 시 주의**

---

## 7. 생성 파일 목록

| 경로 | 설명 |
|---|---|
| [simulation/julich_bottleneck.py](../simulation/julich_bottleneck.py) | 시뮬 스크립트 (AVM, 129명, 5 seed) |
| [simulation/analyze_julich_validation.py](../simulation/analyze_julich_validation.py) | 분석·시각화 스크립트 |
| [data/julich/simulated_4D090.csv](../data/julich/simulated_4D090.csv) | 시뮬 trajectory (1.29M 행) |
| [data/julich/validation_metrics.json](../data/julich/validation_metrics.json) | 수치 지표 |
| [figures/julich_density_heatmap.png](../figures/julich_density_heatmap.png) | 밀도 heatmap (obs/sim/diff) |
| [figures/julich_density_timeseries.png](../figures/julich_density_timeseries.png) | 병목 앞 0.5m 밀도 시계열 |
| [figures/julich_velocity_profile.png](../figures/julich_velocity_profile.png) | x축 속도 프로파일 |
| [figures/julich_snapshots_comparison.png](../figures/julich_snapshots_comparison.png) | 5개 시점 스냅샷 |
| [figures/julich_trajectory_overlay.png](../figures/julich_trajectory_overlay.png) | 궤적 20명 겹침 |

---

## 8. 본 검증에서 하지 않은 것 (명시)

- AVM 파라미터 튜닝 (spec대로)
- 4D100 (h1 variant) 비교
- 유출량 기반 판정 (보조 참고)
- 에스컬 시뮬 수정
