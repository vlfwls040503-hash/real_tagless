# Phase 1-1: Timestamp 활용 가능성 검증

## 보유 Timestamp

| 시점 | 의미 |
|---|---|
| spawn_time | 에이전트 생성 (계단 하행 후) |
| queue_enter_time | 소프트웨어 큐 진입 |
| service_start_time | 게이트 서비스 시작 (큐 pop) |
| escalator_enter_time | 에스컬 capture zone 진입 = 에스컬 서비스 시작 |
| sink_time | 에스컬 서비스 완료 (최종 제거) |

## 산출 가능한 구간

| 구간 | 계산 | 의미 |
|---|---|---|
| approach_time | queue_enter − spawn | 스폰 후 게이트 큐 도달까지 |
| **gate_wait_time** | service_start − queue_enter | **게이트 큐 대기 (정확)** |
| post_service_to_esc | escalator_enter − service_start | 게이트서비스+보행+에스컬큐 |
| escalator_service | sink − escalator_enter | 에스컬 이동 시간 (~0.85s 고정) |

## 에스컬 큐 대기 (순수)는 직접 계산 불가

이유: 에이전트가 capture zone에 **물리적으로 도착한 시각**은 미기록. `escalator_enter_time`은 '포획된' 시각 = 서비스 시작 시각.

### Proxy 제안
```
esc_wait_proxy = post_gate_time - (gate_service_avg + walk_time_lower)
              = (sink - service_start) - (2.0*(1-p) + 1.2*p) - 9.0
```
- gate_service_avg: p별 평균 게이트 서비스 시간
- walk_time_lower = 9.0s (게이트→에스컬 ~12m, 1.34m/s 하한)
- **한계**: 상수 보행시간 가정. 혼잡 시 실제 보행이 길어짐을 무시.
- 따라서 esc_wait_proxy는 **순수 대기 + 보행 혼잡**의 합으로 해석.

### 검증 (p=0.5, cfg=3, s42 파일럿)
- serviced: 417명
- post_service_to_esc: 평균 26.82s, p95 48.91s
- escalator_service: 0.855s (고정)
- → escalator_service는 '대기' 아님. post_service_to_esc가 실질 지표.