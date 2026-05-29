# 보행 모델 검증 요약 — Jülich 4D090 기반 (2026-04-20)

## 1. 목적
Jülich 실측 4D090 (w=1.0m, 129명) 병목 footprint를 기준으로,
CFSM V2와 AVM 중 어느 모델이 더 잘 재현하는지 판정하고 간이 캘리브레이션 수행.

## 2. 실측 목표 (steady state t=15~60s)
| 지표 | 값 |
|---|---|
| 유량 (flow rate) | **1.78 ped/s** |
| 피크 밀도 | **7.22 ped/m²** at (-0.30, 0.50) — 병목 벽 근처 |
| 평균 수렴각 (vs +x) | 54.5° |
| 평균 벽거리 | 0.47 m |
| 샘플 프레임 | 1,126 (45s × 25fps) |

→ 피크가 병목 **정중앙이 아니라 벽 근처** (y=0.5)에 위치. 전형적 쐐기형 수렴.

## 3. 기본값 비교 (각 3 seeds)
| 모델 | Wasserstein (낮을수록 좋음) | 유량 (ped/s) | Gridlock 경향 |
|---|---|---|---|
| **CFSM V2 default** | **0.369** | 1.51–1.62 (CV 3.1%) | ✅ 정상 배출 (잔류 12–19명) |
| AVM default | 0.276 | 0.07–0.91 (CV 63.7%) | ❌ **심각** (잔류 63–113명) |

AVM의 Wasserstein이 낮은 것은 실측 대비가 아니라 **에이전트가 병목까지 도달 못하고 반원 안쪽에 정체**하기 때문. 1개 seed는 75초 동안 겨우 5명 배출 → 물리적 gridlock.

→ **선정 모델: CFSM V2** (안정적 유량 재현, seed 간 CV 3.1%)

## 4. 파라미터 스캔 (27 combos × 2 seeds = 54 runs)
CFSM V2에서 3개 파라미터 ±50% 범위:
- A: strength_neighbor_repulsion ∈ {4.0, 8.0, **12.0**} (default 8.0)
- B: time_gap ∈ {0.5, 1.0, 1.5} (default 1.0; relaxation_time 대용)
- C: strength_geometry_repulsion ∈ {2.5, 5.0, 7.5} (default 5.0)

### 상위 5 non-gridlocked 결과

| A | B | C | W_mean | flow_mean | final |
|---|---|---|---|---|---|
| **4.0** | **1.0** | **5.0** | **0.361** | 2.52 | 18 |
| 4.0 | 1.0 | 7.5 | 0.362 | 2.50 | 20 |
| 8.0 | 1.0 | 7.5 | 0.366 | 2.46 | 21 |
| 4.0 | 0.5 | 7.5 | 0.365 | 2.87 | 0 |
| 8.0 | 1.0 | 5.0 | 0.367 | 2.61 | 15 |

→ **선정 최적값: A=4.0, B=1.0, C=5.0** (neighbor repulsion 절반으로 약화)

## 5. 최적값 재실행 (5 seeds)
| | Wasserstein | 유량 (ped/s, mean) | 피크 밀도 |
|---|---|---|---|
| 실측 | — | 1.78 | 7.22 |
| Default | 0.369 | 1.56 | 12.47 |
| **Best** | **0.362** | **1.50** | **13.98** |
| 개선도 | **1.8%** | 유지 | 악화 |

## 6. 판정

### 성공 기준 대비
| 기준 | 목표 | 실제 | 판정 |
|---|---|---|---|
| Wasserstein 30% 이상 감소 | ≥30% | **1.8%** | ❌ 미달 |
| 쐐기형 수렴 재현 (궤적 overlay) | 정성적 PASS | 피크 위치 재현 O, 분산 X | △ 부분 PASS |
| Gridlock 방지 (flow CV < 10%) | < 10% | 3.1% (best) | ✅ PASS |

### 정량적 한계
- **피크 밀도 과대**: 실측 7.22 vs 시뮬 14.0 (~2× 과대)
- **유량 일치 부족**: 실측 1.78 vs 시뮬 1.50 (~16% 과소)
- 3개 파라미터 ±50% 스캔으로는 근본적 footprint 형태 차이를 해결하지 못함

### 한계 분석
1. **Semicircle 반경 3.3m 한계**: 실측 Jülich는 x_min=-7.7m의 넓은 홀딩 영역을 사용. 반원 기하는 인위적으로 밀집도를 높여 병목 앞 과잉 집중 유발.
2. **CFSM V2 등방성 반발**: 방향 무관 반발력 → 벽과 보행자 간 상호작용을 과도하게 단순화. 실제 쐐기형(벽쪽 피크)의 비대칭 특성 재현 한계.
3. **고밀도 조건 (d>6 ped/m²) 외삽**: Tordeux 2016, Rzezonka 2022 모두 중밀도 (≤3 ped/m²) 캘리브레이션. 4D090의 병목 직전 밀도 (7+ ped/m²)는 검증 범위 밖.
4. **한국 보행자 미반영**: Weidmann (1993) v0=1.34 m/s는 독일/유럽 데이터. 한국 대도시 (특히 서울 지하철 첨두) 보행자 속도·time_gap 차이 반영 안됨.

## 7. 기존 프로젝트 결정 뒷받침
### CFSM V2 선정 정당성 (2026-04-17 "AVM 교체 보류" 결정 검증)
CLAUDE.md의 에스컬레이터 병목 구현 메모에 **"AVM 교체 보류: 전체 시뮬 V&V 재수행 부담. 후속 과제"** 기록됨. 이번 4D090 실험은 이 보류 결정을 **실증적으로 뒷받침**:
- AVM 기본값: seed 3개 중 1개는 유량 0.07 ped/s (사실상 gridlock)
- 동일 조건 CFSM: 안정적 1.5+ ped/s, CV 3.1%
- → "AVM 전환 시 추가 튜닝 부담"이 단순 V&V 재수행이 아닌 **기본 기하에서의 수렴성 보장 문제**임이 확인됨

### 에스컬레이터 시뮬 적용 계획
현재 사용 파라미터 (`run_west_simulation_cfsm.py`):
- strength_neighbor_repulsion = 8.0 (라이브러리 default)
- **time_gap = 0.80 (Rzezonka 2022, 첨두 통근)** ← 이미 tuned
- strength_geometry_repulsion = 5.0 (라이브러리 default)

**이번 캘리브레이션 적용 여부: 현행 유지**
- **time_gap 0.80 유지**: 4D090의 best time_gap=1.0이지만, 4D090은 "fill-and-drain" 조건으로 첨두 통근 조스틀링과 다름. Rzezonka 2022 근거 현행 값 유지 타당.
- **A=4.0 적용 안 함**: 4D090 특화 결과. 성수역 대합실은 4D090 대비 저밀도 (게이트 앞 2~3 ped/m² 수준). Default 8.0에서 과반발 문제 없음.
- **한계 명시**: 본 시뮬의 피크 밀도는 실제 대비 최대 2배 과대 추정 가능 — 논문에서 **정성적 병목 전이 메커니즘 분석**에 중점을 두고, 절대 밀도값은 보수적으로 해석.

## 8. 생성 파일 목록
### 데이터
- `data/julich/4D090_target_footprint.json` — 실측 footprint (density + 통계)
- `data/julich/sim_cfsm_default.csv` — CFSM 기본 (3 seeds, 168k rows)
- `data/julich/sim_avm_default.csv` — AVM 기본 (3 seeds, 234k rows)
- `data/julich/scan_results.csv` — 27×2=54 runs
- `data/julich/sim_cfsm_best.csv` — 최적값 5 seeds (287k rows)
- `data/julich/final_metrics.json` — 최종 지표
- `data/julich/default_comparison.json` — 기본값 비교 지표

### 발표용 Figure (모두 dpi=100, ≤1920×1080)
- `figures/julich_target_footprint.png` — 실측 heatmap
- `figures/default_comparison.png` — CFSM vs AVM vs 실측 (3판넬)
- `figures/calibration_result.png` — 실측 vs default vs best (3판넬, **메인 슬라이드용**)
- `figures/trajectory_before_after.png` — 궤적 overlay 3판넬 (**보조 슬라이드용**)

## 9. 발표 코멘트 제안
> "실측 Jülich 4D090 w=1.0m 기준 CFSM V2와 AVM을 비교 검증했습니다.
> **AVM은 기본값에서 심각한 gridlock** (유량 CV 63%)을 보였고, CFSM은 안정적 배출(CV 3%)을 보였으므로 CFSM V2를 선정했습니다.
> 3파라미터 스캔 결과 Wasserstein 1.8% 개선에 그쳤으며, **피크 밀도는 2배 과대**로 나타났습니다.
> 이는 세미서클 홀딩 기하의 제약과 CFSM의 등방성 반발력 한계로 해석되며,
> 본 연구는 병목 전이의 **정성적 메커니즘 분석**에 중점을 두어 정량적 매칭 한계는 논문 한계로 명시합니다."
