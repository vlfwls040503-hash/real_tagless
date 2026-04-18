# Phase 1-3 종합 보고서: 게이트-only 최적화 + 에스컬 부작용 관찰

**생성일**: 2026-04-18

## TL;DR

> **병목 전이 현상은 관측되나 (r=+0.48, R²=0.23), 현재 시뮬 조건에서 최적 배합 선택까지 바꿀 만큼 크지는 않음.** 즉 "정성적 전이 O, 정량적 임계점 미도달". 논문 RQ3 가설은 부분 입증.

## 주요 결과

### 1. 구간별 R² (회귀 `y ~ p + config + p:config`)
| 종속변수 | R² |
|---|---|
| 총 통행시간 | 0.696 |
| 게이트 대기 | 0.727 |
| 후처리 (에스컬 포함) | 0.552 |

→ **게이트 대기 R²(0.727) > 총(0.696) > 후처리(0.552)**. 구간별 측정이 배합 효과 포착력 더 강함.

### 2. 최적 배합 (기준별 동일)

| p | gate-only | total | pass_rate | 일치? |
|---|---|---|---|---|
| 0.1 | 1 | 1 | 1 | O |
| 0.3 | 2 | 2 | 2 | O |
| 0.5 | 3 | 3 | 3 | O |
| 0.7 | 4 | 4 | 4 | O |
| 0.8 | 4 | 4 | 4 | O |

### 3. 병목 전이 증거 (Phase 2-2 핵심)

| x (게이트 처리율) | r | p-value | R² |
|---|---|---|---|
| 이론 처리율 | +0.109 | - | 0.012 |
| **실측 처리율** | **+0.476** | 5.729e-07 | **0.226** |

실측 기준 **유의한 양의 상관** → 게이트가 실제로 빨리 처리할수록 에스컬 대기 증가. 병목 전이 직접 증거.

### 4. 최적 배합에서의 post_gate 비율

| p | 최적 cfg | post_gate / total (%) |
|---|---|---|
| 0.1 | 1 | 50% |
| 0.3 | 2 | 56% |
| 0.5 | 3 | 59% |
| 0.7 | 4 | 62% |
| 0.8 | 4 | 56% |

**최적 배합에서 post_gate가 총 시간의 절반 이상 (26-62%)**. 게이트 최적화가 전체 시간을 줄이지만 에스컬이 상대적 주 병목으로 전환.

## 결론 (A/B/C)

- **A 측면 ("에스컬 여유, 전이 없음")**: 최적 배합이 모든 기준에서 일치.
- **B 측면 ("전이 관측")**: 실측 처리율↑ → 에스컬 대기↑ (r=+0.48).
- **결론: 하이브리드 A+B**. 정성적으로는 전이 O, 최적 선택까지 바꿀 임계점은 미도달.

## 그래프

- [gate_throughput_vs_escalator_density.png](figures_phase3/gate_throughput_vs_escalator_density.png)
- [optimal_config_comparison.png](figures_phase3/optimal_config_comparison.png)
- [escalator_density_heatmap.png](figures_phase3/escalator_density_heatmap.png)

## 세부 문서

- [docs/phase1_timestamp_check.md](../docs/phase1_timestamp_check.md)
- [docs/phase1_gate_only_optimal.md](../docs/phase1_gate_only_optimal.md)
- [docs/phase2_escalator_observation.md](../docs/phase2_escalator_observation.md)
- [docs/phase3_tradeoff_analysis.md](../docs/phase3_tradeoff_analysis.md)

## 제약 및 후속 필요 사항

- zone3/4_max_density가 거의 상수 (x=23~25 정의 한계). 에스컬 실제 큐는 x=25~35 capture zone 내부 → sim runner에서 capture_zone 내 에이전트 수를 별도 기록하면 정확한 에스컬 혼잡도 시계열 확보 가능.
- esc_wait_proxy는 상수 보행시간(9s) 가정. 실제 혼잡 시 보행 지연까지 포함되는 합성 지표. 분리하려면 "capture zone 진입 시각" 추가 timestamp 필요.
- 에스컬 용량 sensitivity(현재 1개당 0.85s 고정) 스캔 시 병목 전이 임계점 정량화 가능할 것.