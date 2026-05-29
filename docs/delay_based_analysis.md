# 통행비용 분리 측정 — 게이트 vs 시스템 (2026-04-20)

## 1. 목적
배합별 통행비용을 **자유보행 대비 지연시간 (delay)** 기준으로 측정. 지연을 "게이트 구간"과 "post-gate 구간"으로 분리하여 **병목 전이의 공간적 분포를 정량화**. 통일된 시간 지표(pass_rate와 gate_wait를 혼용하는 기존 프레임 극복)로 두 관점의 최적 cfg 비교.

## 2. 데이터 및 전제
### 사용 데이터
- **CFSM V2 (JuPedSim) 최신 기하구조로 재실행한 100 시나리오** (`results_cfsm_latest/`)
  - 실행일: 2026-04-20 17:00–17:14 (배치 런)
  - 이유: 기존 `results_v3/`는 2026-04-19 02:24 기준. 이후 space_layout.py(16:40), run_west_simulation_cfsm_escalator.py(16:54) 업데이트됨 → 재실행 필요.
- 시나리오 매트릭스: p ∈ {0.1, 0.3, 0.5, 0.7, 0.8} × cfg ∈ {1, 2, 3, 4} × seeds {42..46} = 100
- 각 시나리오: TRAIN_INTERVAL=150s, TRAIN_ALIGHTING=200, SIM_TIME=300s
- trajectory 샘플링 0.5s

### 가정
- 자유보행 속도 **V₀ = 1.34 m/s** (Weidmann 1993 평균; 개별 agent는 N(1.34, 0.26) 분포이나 free_time 계산에는 평균 사용)
- 정체 임계값 **v < 0.2 m/s** (거의 정지)
- 게이트 x좌표 **x = 12.0**, gate housing 길이 **~0.3 m**
- pre/post gate 매칭: CFSM에서 agent가 게이트 통과 시 **새 agent_id로 재생성**되므로, FIFO(gate_idx별 approach_enter_time 순)로 1:1 매칭. 100 시나리오 모두 417/417 (100%) 매칭 성공.

## 3. Agent별 지표 정의
trajectory의 실제 이동거리를 기준으로 free_time을 계산 (직선 가정이 아닌 **실제 경로 반영**):

| 지표 | 공식 | 의미 |
|---|---|---|
| `path_distance` | sum(‖Δx,Δy‖) pre + bridge + post | 총 이동거리 |
| `actual_time_total` | sink_time - spawn_time | 실제 총 통행시간 |
| `free_time_total` | path_distance / V₀ | 자유보행 가정시 최소 시간 |
| `total_delay` | actual - free | **총 지연** |
| `t_gate` | approach_enter_time | 게이트 통과 시점 |
| `gate_actual_time` | t_gate - spawn_time | 게이트까지 실제 시간 |
| `free_time_gate` | (pre_path + bridge/2) / V₀ | 게이트까지 자유보행 |
| `gate_delay` | gate_actual - free_gate | **게이트 지연** |
| `post_gate_delay` | total_delay - gate_delay | **post-gate 지연** |
| `congestion_pre` | Σ Δt where x<12 & speed<0.2 | 게이트 전 정체시간 |
| `congestion_post` | Σ Δt where x≥12 & speed<0.2 | 게이트 후 정체시간 |
| `w1_wait` | W1 zone 내 & speed<0.2 | 재정의 zone 대기 (게이트) |
| `w2_wait` | W2 zone 내 & speed<0.2 | 재정의 zone 대기 (upper 에스컬) |

**W1, W2 정의**: `docs/waiting_zones_v5.json` (p=0 궤적 기반 재정의)
- W1 게이트_대기: x∈[6.25,12.25], y∈[9.25,15.75], 33 m²
- W2 upper_에스컬_대기: x∈[21.75,26.75], y∈[21.75,26.0], 18 m²

## 4. 시나리오별 delay 결과 (5 seeds 평균, 초 단위)

| p | cfg | gate_delay | post_gate_delay | total_delay | post_share | n_serviced |
|---|---|---|---|---|---|---|
| 0.1 | 1 | 16.5 | 9.1 | **25.5** | 0.36 | 414 |
| 0.1 | 2 | 22.2 | 7.1 | 28.6 | 0.25 | 414 |
| 0.1 | 3 | 29.8 | 3.2 | 31.5 | 0.10 | 406 |
| 0.1 | 4 | 40.6 | 3.0 | 42.2 | 0.07 | 348 ⚠ |
| 0.3 | 1 | 15.5 | 11.3 | 25.4 | 0.44 | 408 |
| 0.3 | 2 | **13.1** | 11.4 | **24.4** | 0.47 | 414 |
| 0.3 | 3 | 17.0 | 8.3 | 25.0 | 0.33 | 414 |
| 0.3 | 4 | 23.8 | 5.4 | 27.7 | 0.19 | 402 |
| 0.5 | 1 | 20.0 | 9.5 | 28.2 | 0.34 | 354 |
| 0.5 | 2 | 15.0 | 12.5 | **26.9** ★sys | 0.46 | 412 |
| 0.5 | 3 | **11.6** ★gate | 18.0 | 29.2 | 0.61 | 414 |
| 0.5 | 4 | 13.9 | 16.6 | 29.4 | 0.56 | 414 |
| 0.7 | 1 | 39.4 | 10.6 | 46.4 | 0.23 | 256 ⚠ |
| 0.7 | 2 | 22.0 | 9.8 | 30.1 | 0.33 | 391 |
| 0.7 | 3 | 14.8 | 16.6 | 30.4 | 0.55 | 411 |
| 0.7 | 4 | **10.1** | 18.2 | **28.2** | 0.65 | 413 |
| 0.8 | 1 | 48.9 | 8.4 | 52.4 | 0.16 | 222 ⚠ |
| 0.8 | 2 | 25.5 | 8.7 | 32.5 | 0.27 | 365 |
| 0.8 | 3 | 18.4 | 15.5 | 32.0 | 0.48 | 406 |
| 0.8 | 4 | **12.5** | 16.4 | **28.5** | 0.57 | 411 |

★gate = 게이트 관점 최적, ★sys = 시스템 관점 최적
⚠ = 100명 이상 unserviced (시간 내 통과 실패)

## 5. 두 관점 최적 cfg 비교

| p | 게이트 관점 최적 cfg | 시스템 관점 최적 cfg | 일치? |
|---|---|---|---|
| 0.1 | **cfg 1** | cfg 1 | ✓ |
| 0.3 | **cfg 2** | cfg 2 | ✓ |
| 0.5 | **cfg 3** (gate=11.6s) | cfg 2 (total=26.9s) | ✗ **불일치** |
| 0.7 | **cfg 4** | cfg 4 | ✓ |
| 0.8 | **cfg 4** | cfg 4 | ✓ |

### p=0.5 불일치에 대한 paired t-test
- H0: cfg3 (gate-opt)과 cfg2 (sys-opt)의 total_delay 동일
- n = 5 (seed 매칭), t = 2.616, **p-value = 0.059**, Cohen's d = **1.17 (large effect)**
- 평균 차이 = **+2.38 s** (cfg3이 cfg2보다 시스템 delay 2.4s 더 큼)
- 95% CI: [-0.15, +4.91]

**해석**: p = 0.059로 α=0.05 기준 통계적으로는 경계선이지만, 효과크기는 매우 큼(d=1.17). seed=5로 검정력 제한. **실무적으로는 cfg 2 선택 권고**. 게이트 관점만 보고 cfg 3을 선택하면 시스템 총 delay는 +2.4s (9% 증가).

## 6. 병목 전이 정량화

### post_gate_delay_share 히트맵 (post-gate delay 비율)

| p \\ cfg | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| 0.1 | 0.36 | 0.25 | 0.10 | 0.07 |
| 0.3 | 0.44 | 0.47 | 0.33 | 0.19 |
| 0.5 | 0.34 | 0.46 | **0.61** | **0.56** |
| 0.7 | 0.23 | 0.33 | **0.55** | **0.65** |
| 0.8 | 0.16 | 0.27 | **0.48** | **0.58** |

### 병목 전이 패턴
1. **cfg 증가 → post_share 증가** (p=0.5 기준 34%→46%→61%→56%)
2. **p 증가 → 같은 cfg에서 post_share 증가** (cfg=3 기준 10%→33%→61%→55%→48%)
3. **정성적 구조 변화**:
   - (p=0.1, cfg=1): post_share = 36%, 게이트 병목 지배
   - (p=0.8, cfg=4): post_share = 58%, **upper 에스컬 병목 지배** — 병목이 물리적으로 **~25m 동쪽으로 이동**

→ RQ1 "병목이 게이트에서 출구 계단/에스컬레이터로 전이된다"의 **정량 증거** 확보. 전이는 **연속적/점진적**이며, cfg 선택이 전이 속도 조절.

## 7. 기존 분석(pass_rate, gate_wait)과의 일치/불일치
- **pass_rate 기준**: 기존 배치에서 cfg 4는 pass_rate ↓ (특히 p=0.1, 0.7, 0.8에서 unserviced 급증)
  → delay 분석과 일관: cfg 4가 p=0.1에서는 과도(total_delay=42.2s, unserviced 67명).
- **gate_wait (기존 지표)**: 주로 queue에서 대기 시간만 포함. **post-gate의 느린 보행/에스컬 대기는 포함 안됨**.
- **총 delay (본 분석)**: pre + post 통합하여 **시스템 관점에서 일관**.
- p=0.5에서 관점 불일치는 기존 프레임으로는 drowse — gate_wait만 보면 cfg 3이 최적처럼 보임. total delay가 정답.

## 8. 발표 메시지 권고

### 핵심 메시지
> "배합 선택은 **게이트 관점**이 아니라 **시스템 관점**으로 해야 한다. 게이트 지연을 최소화하는 cfg가 총 통행비용을 최소화하지 않는 구간(p=0.5)이 존재하며, 이 지점에서 병목이 가장 빠르게 전이된다."

### RQ별 정량 근거
- **RQ1 (병목 전이)**: post_share가 cfg와 p에 따라 7%→65%로 **9배 변화** → 전이 실증.
- **RQ2 (역설)**: (p=0.1, cfg=4)에서 총 delay 42.2s vs (p=0.1, cfg=1) 25.5s — **전용 게이트 과잉 → 전체 delay 65% 증가**. 동일 p에서 cfg를 늘린다고 시스템 개선 아님.
- **RQ3 (가변 운영)**: 최적 cfg가 p에 따라 1→2→2→4→4로 단조 증가 → **혼입률별 가변 운영의 명시적 근거**.

### 보조 메시지
1. **p=0.5는 설계 결정점**: 게이트 관점과 시스템 관점이 갈라지는 유일한 구간. 운영자 교육 자료에 강조.
2. **post-gate 병목은 upper 에스컬**: W1(게이트) 대기 vs W2(upper 에스컬) 대기 패턴으로 확인 (W2_wait: p=0.1 1.6s → p=0.8 8.5s).

## 9. 한계
1. **seed=5 검정력 부족**: p=0.5 불일치가 p=0.059로 경계. seed 확대 필요.
2. **자유보행 1.34 m/s 고정**: 개별 agent desired_speed는 N(1.34, 0.26) 분포이나 free_time은 평균값. 결과: 빠른 agent는 실제 자유보행 시간이 더 작아 delay가 과대평가, 느린 agent는 과소평가.
3. **Weidmann 독일 기준**: 한국 첨두 통근 실제 속도 미검증.
4. **CFSM V2 한계**: `docs/model_validation_summary.md`에서 확인된 피크 밀도 ~2배 과대 가능성. 절대 delay값은 보수적 해석.
5. **Zone 재정의 기반은 p=0 데이터**: p>0에서 새 대기 zone 출현 가능성 (예: p=0.5 cfg3 Z3B LOS F). 본 분석 W1/W2로 커버되지 못한 체증은 congestion_pre/post 지표로 포착.

## 10. 생성 파일
### 코드
- `simulation/analyze_delay_cfsm.py` — agent별 delay 지표 추출
- `simulation/delay_figures_stats.py` — figure + 통계검정

### 데이터
- `results_cfsm_latest/summary.csv` — 배치 전통 집계 (100 시나리오)
- `results_cfsm_latest/delay_analysis.csv` — 시나리오별 delay 지표 (100 행)
- `results_cfsm_latest/agent_level_delay.csv` — agent별 delay (38,408 행)
- `results_cfsm_latest/delay_stats.json` — 최적 cfg + 검정 결과

### 발표용 시각자료
- `figures/delay_breakdown.png` — p별 cfg별 gate+post 지연 분해 (stacked bar)
- `figures/optimal_cfg_delay_based.png` — 관점별 최적 cfg 및 delay 비교

## 11. 후속 작업 (권장)
1. **seed 확대 (10회)**: p=0.5 불일치의 통계 유의성 확정
2. **desired_speed 개별 반영**: `free_time = path / agent.desired_speed` (각자 자기 속도 기준)로 재계산
3. **LOS 가중치 적용**: delay에 LOS D/E/F disutility 가중 → "weighted system cost"
4. **첨두/비첨두 비교**: TRAIN_ALIGHTING 변경 (120 vs 200)
5. **양방향 보행류**: 현재 단방향 하차만 — 승차 추가 시 병목 구조 변화
