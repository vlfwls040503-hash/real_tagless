# 베이스라인 측정 결과

> 작성일: 2026-04-17
> 목적: CFSM V2 기본 파라미터에서 에스컬레이터 진입부 수렴
> oscillation 현상을 정량 재현하고, 전략 비교의 기준선 확보.

## 시나리오

- 공간: 10m × 10m 대합실 + 폭 1.0m × 길이 3m 통로
- 스폰: x=0.5, y=2.5~7.5 (폭 5m)에서 Poisson 유입
- 출구: 통로 끝 x=12.5~13.0 (에스컬레이터 종단)
- 목표 좌표: 통로 중심
- CFSM V2 파라미터 (성수역 시뮬과 동일):
  - time_gap = 0.80s
  - radius = 0.15m
  - strength_neighbor = 8.0
  - range_neighbor = 0.1m
  - desired_speed ~ N(1.34, 0.26), clip [0.8, 1.5]
  - dt = 0.05s

## 지표

| 지표 | 정의 | 해석 |
|------|------|------|
| heading_change_mean | agent별 단위시간당 heading 변화량 평균 (deg/s) | 진동 |
| heading_change_p90 | heading_change의 90퍼센타일 | 최악 진동 |
| backward_ratio | desired 방향과 actual 속도의 내적 < 0 시간 비율 | 역행 |
| speed_in_zone | 측정 영역 내 평균 속도 (m/s) | 병목 진입부 속도 |
| density_mean / max | 측정 영역(x=7~10, y=4~6)의 밀도 (인/m²) | 혼잡도 |
| spawned / exited | 총 스폰 수 / 출구 통과 수 | 처리량 |

## 결과 (3 seed 평균)

| 유입률 (ped/s) | heading_mean | heading_p90 | backward | speed_zone | density_mean | density_max | spawned | exited |
|---|---|---|---|---|---|---|---|---|
| 2.0 (저) | 86.4 | 236.9 | 0.166 | 0.920 | 0.80 | 2.00 | 51.7 | 29.0 |
| 4.0 (중) | **208.6** | 599.7 | 0.139 | 0.486 | 2.06 | 4.06 | 98.0 | 34.3 |
| 6.0 (고) | **226.3** | 665.1 | 0.123 | 0.407 | 2.54 | 4.78 | 139.0 | 36.0 |

## 관측

- 유입률 2.0 → 4.0에서 **heading_change_mean이 86 → 209 deg/s로 2.4배 증가**. 진동 현상이 고혼잡에서 확연히 재현됨
- heading_p90은 유입률 4.0에서 **600 deg/s** 초과 → 일부 에이전트가 초당 1.6회전 수준의 극심한 방향 변화
- backward_ratio는 유입률 증가 시 소폭 감소 (0.166 → 0.123). 고혼잡에서는 역행할 공간도 줄어드는 것으로 해석 가능
- speed_zone은 0.92 → 0.41 m/s로 55% 감소 — 병목 진입부에서 자유보행 1.34 m/s 대비 69% 감속
- 처리량(exited)은 유입률 증가 대비 둔화 (rate 2→6에서 29→36, 24% 증가뿐) → 출구 용량 포화 확인

## 해석

유입률 4.0 ped/s가 **진동 현상이 뚜렷하게 발생하면서도 시뮬 런타임이 현실적인 균형점**. 이후 전략 비교는 이 유입률을 주 기준으로 삼는다 (rate=2는 효과 약하고, rate=6은 신호가 포화됨).

## 재현 방법

```bash
cd C:\Users\aaron\tagless\experiments\escalator_convergence_test
py -3.12 run_experiments.py --strategies baseline
```

결과: `results/summary.json` 의 `"baseline"` 항목.
