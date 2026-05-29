# AVM 파라미터 캘리브레이션 — Jülich 4D090 공간 형태 매칭

**작성일**: 2026-04-20
**목적**: 기존 AVM 기본값으로 재현 실패한 Jülich 4D090 병목의 **공간 footprint**를 세 파라미터 튜닝으로 개선
**판정**: **FAIL (완료 기준 30% 개선 미달)**
**최적 조합**: A=3.0, B=0.3, C=0.05 (score=0.335, 베이스라인 0.308 대비 **9% 악화**)

---

## 1. 전제 및 설계

### 1.1 배경
[docs/julich_validation.md](./julich_validation.md) — AVM 기본값(strength=8.0, reaction=0.3, wall_buf=0.1)으로 병목 공간 밀도 상관 r=-0.10 (무상관). 본 캘리브레이션은 **공간 형태만** 타겟.

### 1.2 파라미터 매핑 (spec → jupedsim AVM)

| spec 명칭 | jupedsim 파라미터 | 의미 |
|---|---|---|
| A) pedestrian_repulsion_strength | `strength_neighbor_repulsion` | 이웃 반발 강도 |
| B) relaxation_time | `reaction_time` | 반응 시간 (≈ SFM relaxation 근사) |
| C) wall_repulsion_strength | `wall_buffer_distance` | 벽 완충 거리 (m) — AVM에 strength 파라미터 없음, buffer로 대체 |

### 1.3 스캔 그리드

| 파라미터 | 값 |
|---|---|
| A (strength_neighbor_repulsion) | [0.5, 1.0, 1.5, 2.0, 3.0] |
| B (reaction_time) | [0.3, 0.5, 0.8, ~~1.2~~] |
| C (wall_buffer_distance) | [0.05, 0.10, 0.20, 0.35] |
| seeds | [42, 43, 44] |

**B=1.2 제외**: jupedsim AVM의 `reaction_time` 허용 범위 (0, 1] — 초과 시 `Model constraint violation` 예외. 60개 run 실패.

**실제 성공 run**: 5 × 3 × 4 × 3 = **180** (실패 60 제외)

- SIM_TIME 60s (steady-state 형태만 필요)
- 분석 창 t=[10, 50]s
- 병목 폭 1.0m 고정

### 1.4 평가 지표 (공간 형태 중심)
1. **Jensen-Shannon divergence (JS)** — 2D 밀도 분포 유사도
2. **Wasserstein distance on x-marginal (w_x)** — 큐 꼬리 길이
3. **Wasserstein distance on |y|-marginal (w_y)** — 큐 폭 / 벽 근접도

**Composite score** = JS + w_x + w_y (낮을수록 좋음)

---

## 2. 실측 타겟

([data/julich/4D090_target_metrics.json](../data/julich/4D090_target_metrics.json))

- 분석 창: t=[10, 50]s (40초, 1001 frame)
- 격자: 0.2 m × 0.2 m, x∈[-2, 0], y∈[-2, 2]
- **Max density**: 7.82 ped/m²
- **평균 벽 거리**: 0.483 m (참가자 평균 0.48m 벽에서 떨어져 대기)

## 3. 베이스라인 (기본 AVM)

([data/julich/baseline_metrics.json](../data/julich/baseline_metrics.json))

| 지표 | 값 | 주석 |
|---|---:|---|
| JS div | 0.077 | 낮게 보이지만 패턴은 다름 (이전 r=-0.10) |
| w_x | 0.032 | |
| w_y | 0.199 | |
| **Score** | **0.308** | — 개선 목표점 |
| Sim max density | 25.0 ped/m² | **stuck agent 100% 셀 점유** |

**주의**: 베이스라인 score는 gridlock으로 agent가 hex 초기 배치에 붙어있어 marginal 분포가 우연히 obs와 유사. 물리적으로 현실적이지 않지만 **본 평가지표는 이 상황을 penalty 주지 못함**.

---

## 4. 스캔 결과 (180 run)

### 4.1 Top 10 조합

| A | B | C | score_mean | score_std | js_mean | w_x | w_y | exit_mean | wall_dist |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **3.0** | **0.3** | **0.05** | **0.335** | 0.006 | 0.075 | 0.048 | 0.213 | 67.7 | 0.633 |
| 3.0 | 0.5 | 0.05 | 0.348 | 0.006 | 0.082 | 0.052 | 0.214 | 64.0 | 0.634 |
| 2.0 | 0.3 | 0.05 | 0.351 | 0.004 | 0.079 | 0.049 | 0.222 | 66.7 | 0.641 |
| 1.0 | 0.8 | 0.05 | 0.356 | 0.039 | 0.075 | 0.052 | 0.229 | 53.0 | 0.649 |
| 2.0 | 0.5 | 0.05 | 0.357 | 0.021 | 0.090 | 0.047 | 0.220 | 64.3 | 0.638 |
| 1.5 | 0.5 | 0.05 | 0.359 | 0.029 | 0.092 | 0.041 | 0.225 | 67.7 | 0.643 |
| 3.0 | 0.3 | 0.10 | 0.382 | 0.035 | 0.124 | 0.050 | 0.208 | 45.3 | 0.629 |
| 2.0 | 0.8 | 0.05 | 0.391 | 0.054 | 0.123 | 0.056 | 0.212 | 50.3 | 0.632 |
| 1.5 | 0.8 | 0.05 | 0.394 | 0.036 | 0.109 | 0.044 | 0.241 | 61.0 | 0.657 |
| 1.0 | 0.3 | 0.05 | 0.400 | 0.006 | 0.096 | 0.054 | 0.250 | 57.3 | 0.663 |

**관찰**
- Top 10 모두 **C=0.05** (최소 벽 완충) — 벽에 가까이 대기해야 실측에 근접
- A=3.0이 3개, A=2.0이 2개 → **강한 반발**이 유리
- B 영향은 상대적으로 작음

### 4.2 전체 스캔 시각화

[figures/calibration_scan_heatmap.png](../figures/calibration_scan_heatmap.png)

(rows = B, cols = C, 각 셀은 A값에 따른 score 곡선)

### 4.3 최적 파라미터 vs 베이스라인

| 지표 | 베이스라인 | 최적 (A=3.0, B=0.3, C=0.05) | Δ |
|---|---:|---:|---:|
| Score | **0.308** | **0.335** | **+9% (악화)** |
| JS div | 0.077 | 0.075 | -3% (개선) |
| w_x | 0.032 | 0.048 | +49% (악화) |
| w_y | 0.199 | 0.213 | +7% (악화) |
| 평균 벽 거리 | n/a | 0.633 | 목표 0.483 (+31% 더 떨어짐) |

**완료 기준 "Wasserstein 30% 이상 감소" 미달**. 30% 개선을 위해서는 score < 0.216 필요, 실제 0.335.

---

## 5. 검증 (최적 파라미터 × 10 seeds)

[data/julich/calibration_runs/validate_traj_A3.0_B0.3_C0.05.csv](../data/julich/calibration_runs/validate_traj_A3.0_B0.3_C0.05.csv)

### 5.1 유출 안정성 (부수 발견)

| seed | 100 | 101 | 102 | 103 | 104 | 105 | 106 | 107 | 108 | 109 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| exited | 66 | 65 | 67 | 67 | 62 | 60 | 62 | 63 | 66 | 72 |

- **평균 64.1, std 3.3** (범위 60-72)
- 이전 베이스라인은 seed별 **1-97 범위** (극단적 gridlock 발생) → **확률적 gridlock 해소** 확인
- 이건 완료 기준에 없지만 **물리적 현실성 측면에서 유의미**

### 5.2 공간 footprint

[figures/calibrated_density_heatmap.png](../figures/calibrated_density_heatmap.png)

- 실측: x=-0.5~0 구간 고밀도 쐐기
- 최적: 병목 앞 고밀도 + y 방향으로 더 확산 (실측보다 넓음)
- Diff: 병목 바로 앞(|y|<0.5, x∈[-0.5, 0])은 시뮬 **부족**, 주변(|y|>0.8)은 시뮬 **과잉**

### 5.3 궤적 중첩

[figures/calibrated_trajectory_overlay.png](../figures/calibrated_trajectory_overlay.png)

- 실측: 부채꼴형으로 병목 수렴, 개별 궤적 명확
- 최적: 궤적이 병목으로 수렴하나 **중앙 집중도 약함**, 가장자리 궤적 많음

---

## 6. 한계 및 해석

### 6.1 왜 개선 실패했나

**핵심 원인 3가지**:

1. **평가지표의 gridlock 허점**: JS/Wasserstein은 marginal·flattened 분포 기반. 베이스라인 gridlock으로 agent가 hex 위치에 얼어붙으면 그 분포가 우연히 obs의 쐐기형과 marginal 수준에서 유사해짐. 실제 spatial correlation은 여전히 나쁨(이전 r=-0.10)지만 평가지표에는 안 잡힘.
   - 교훈: **spatial correlation (Pearson)을 공동 평가지표로 추가** 필요

2. **AVM 등방성 반발의 구조적 한계**: 강한 반발 + 작은 벽 완충(C=0.05)이 최적이었지만, 여전히 agent들이 **중앙으로 쏠리는 구조**를 만들지 못함. 실측의 쐐기형 집중은 **목표 지향성**(goal attraction)의 강도가 반발을 이겨야 하는데, AVM에서는 이 비대칭을 만들기 어려움.

3. **고정값들이 병목**: time_gap=0.80, anticipation_time=1.0, range=0.1 모두 고정. 이들이 공간 형태에 미치는 영향이 스캔 3개 파라미터보다 클 가능성.

### 6.2 재현 성공한 측면
- **확률적 gridlock 해소**: exit count std 3.3 (베이스라인 ~40)
- **JS div 미세 개선** (0.077 → 0.075, 3%)
- **벽 거리 일부 개선**: 작은 C 값이 벽 접근 허용

### 6.3 재현 여전히 실패한 측면
- **공간 집중도**: 벽에서 멀어짐 (0.63 vs 실측 0.48)
- **쐐기형 응집 패턴**: 부재
- **종합 score**: 악화

### 6.4 AVM 모델 한계
- 등방성 힘 기반 → 군중 내부 응집력 재현 어려움
- CLAUDE.md의 "진동 원인은 방향 불안정 — CFSM 등방성" 주석과 일치
- jupedsim AVM은 Xu 2021 논문 기반이나, 실험실 병목 데이터 calibration은 별도

### 6.5 후속 개선 방향

**단기 (같은 모델 내)**
1. 평가지표에 **spatial Pearson correlation** 추가
2. 고정 파라미터 확장 스캔: `time_gap`, `anticipation_time`, `range_neighbor_repulsion`
3. 초기 배치를 hex 대신 **실측과 동일 분포**로

**중기 (모델 변경)**
1. CFSM V2 기반 동일 검증 (현 에스컬 시뮬 모델)
2. SFM classic 비교
3. Xu 2021 AVM의 `anticipation_time=0` 설정(≈고전 CVM)

---

## 7. 에스컬 시뮬 적용 검토

### 7.1 현 에스컬 시뮬과의 관계

현 [run_west_simulation_cfsm_escalator.py](../simulation/run_west_simulation_cfsm_escalator.py)는 **CFSM V2** 기반. 본 캘리브레이션 대상 **AVM**과 다른 모델.

**이식 가능성**:
- 파라미터 구조 다름 → **직접 이식 불가**
- CFSM에도 time_gap, radius 등 유사 파라미터 있으나 내부 동역학이 다름
- 시사점 수준: "반발 강도 낮추고 벽 완충 작게" 방향성 정도

### 7.2 현 에스컬 시뮬 결과 영향

**재시뮬 불필요**. 이유:
1. 에스컬 시뮬은 **소프트웨어 큐**가 병목 물리 제어 (agent 위치 명시적 관리)
2. CFSM V2 파라미터는 프로젝트 내 **별도 보정** (Rzezonka 2022 근거)
3. 본 AVM 실패 결과가 CFSM V2 타당성에 **직접적 반박은 아님**

### 7.3 보고서 방법론 절에 추가할 경계

> "본 시뮬 병목은 물리 기반 압축이 아닌 소프트웨어 큐 제어이며, 같은 계열의 AVM 순수 물리 모델은 Jülich 4D090 공간 형태 재현에 실패(docs/avm_calibration.md 참조)한 바 있음. 따라서 본 시뮬의 병목 형태는 질적 재현보다 **처리율·대기시간 측정에 한정하여** 해석해야 함."

### 7.4 후속 과제
1. **CFSM V2 동일 Jülich 검증** (우선순위 HIGH)
2. 두 모델 비교 후 에스컬 시뮬용 최적 선택
3. 방법론에 "물리 모델 한계" 명시

---

## 8. 결론

1. **캘리브레이션 목표 미달**: score 0.308 → 0.335 (9% 악화)
2. **부수 성과**: 확률적 gridlock 해소 (유출 std 40 → 3)
3. **근본 원인**: AVM 등방성 + 평가지표의 gridlock 허점
4. **다음 단계**: CFSM V2에 대한 동일 검증 + 고정 파라미터 확장 스캔 + 평가지표 보강

---

## 9. 생성 파일 목록

| 경로 | 설명 |
|---|---|
| [simulation/julich_calibration.py](../simulation/julich_calibration.py) | 스캔 스크립트 (240 combos) |
| [simulation/extract_julich_target.py](../simulation/extract_julich_target.py) | 타겟 지표 추출 |
| [simulation/compute_baseline_js.py](../simulation/compute_baseline_js.py) | 기본 AVM 점수 |
| [simulation/analyze_calibration.py](../simulation/analyze_calibration.py) | 집계·시각화 |
| [simulation/julich_validate_traj.py](../simulation/julich_validate_traj.py) | 10-seed 검증 |
| [data/julich/4D090_target_metrics.json](../data/julich/4D090_target_metrics.json) | 타겟 밀도 |
| [data/julich/baseline_metrics.json](../data/julich/baseline_metrics.json) | 기본 AVM 점수 |
| [data/julich/calibration_runs/progress.jsonl](../data/julich/calibration_runs/progress.jsonl) | 180 run 로그 |
| [data/julich/calibration_runs/best_params.json](../data/julich/calibration_runs/best_params.json) | Top 10 |
| [data/julich/calibration_runs/validate_traj_A3.0_B0.3_C0.05.csv](../data/julich/calibration_runs/validate_traj_A3.0_B0.3_C0.05.csv) | 10-seed 궤적 |
| [figures/calibration_scan_heatmap.png](../figures/calibration_scan_heatmap.png) | 전체 스캔 |
| [figures/calibrated_density_heatmap.png](../figures/calibrated_density_heatmap.png) | 최적 vs 실측 밀도 |
| [figures/calibrated_trajectory_overlay.png](../figures/calibrated_trajectory_overlay.png) | 궤적 중첩 |

## 10. 본 과제에서 하지 않은 것 (명시)
- AVM 코드 수정
- 다른 모델 비교
- 기계학습 기반 모델
- 성수역 시뮬 재실행
- 고정 파라미터(time_gap 등) 스캔 (후속으로 이관)
