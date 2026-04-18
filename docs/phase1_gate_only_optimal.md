# Phase 1: 게이트-only 재분석

## 1-2. 구간별 회귀 R² 비교

모델: `y ~ p + config + p:config`

| 종속변수 | R² | 해석 |
|---|---|---|
| `avg_travel_time` (총 통행시간) | **0.696** | - |
| `avg_gate_wait` (게이트 대기 (구간별)) | **0.727** | - |
| `avg_post_gate` (후처리 (구간별)) | **0.552** | - |
| `esc_wait_proxy` (에스컬 대기 proxy) | **0.567** | - |

→ **avg_gate_wait R² > avg_travel_time R²**. 구간별 측정이 총 통행시간보다 배합 효과를 더 잘 포착.

### avg_gate_wait 회귀 세부
```
               coef  std_err  p_value
Intercept  -16.2017   3.9399   0.0001
p          102.8596   7.2417   0.0000
config      14.6320   1.4387   0.0000
p:config   -38.9056   2.6443   0.0000
```
- `p:config` 교호 계수가 -38.91로 매우 유의. p와 config의 조합이 중요하다는 증거.

## 1-3. 기준별 최적 배합

| p | gate-only (avg_gate_wait↓) | total (avg_travel_time↓) | pass_rate↑ |
|---|---|---|---|
| 0.1 | **1** | 1 | 1 |
| 0.3 | **2** | 2 | 2 |
| 0.5 | **3** | 3 | 3 |
| 0.7 | **4** | 4 | 4 |
| 0.8 | **4** | 4 | 4 |

**모든 p 수준에서 3가지 기준 최적 배합 동일** → 게이트-에스컬 trade-off 가 최적 선택을 바꿀 만큼 크지 않음.
