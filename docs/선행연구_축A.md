# 선행연구 축 A: 시스템 전체 관점 역사 보행 시뮬레이션

> **작성일**: 2026-04-17
> **대상 RQ**: 본 연구의 공간 확장 정당성 — 게이트 구간만 보는 부분
> 최적화를 넘어, **계단·대합실·게이트·승강장/출구**를 통합 모델링한
> 선행연구가 있는가?
> **원칙**: 검증된 문헌 중심. 불확실한 항목은 "검증 필요" 플래그.

---

## 조사 범위 및 키워드

- metro station pedestrian simulation
- multi-zone pedestrian flow
- transit station LOS analysis
- subway station comprehensive simulation
- train station integrated pedestrian flow
- station-wide microsimulation
- integrated station model

---

## 1. 다구간 시뮬레이션 선행연구 (확증 가능)

### [A-1] Helbing, Molnár, Farkas, Bolay (2001) — 자기조직화
- **서지**: Helbing, D., Molnár, P., Farkas, I. J., & Bolay, K.
  (2001). Self-organizing pedestrian movement. *Environment and
  Planning B: Planning and Design*, 28(3), 361–383.
- **DOI**: 10.1068/b2697
- **본 연구 활용**: 다구간에서 자기조직화 현상(lane formation,
  oscillation at bottlenecks). 대합실→게이트→출구 흐름에서 나타날
  수 있는 현상 이해 기반.
- **검증 상태**: 확인됨

### [A-2] Daamen & Hoogendoorn (2003) — SimPed 시뮬레이터
- **서지**: Daamen, W., & Hoogendoorn, S. P. (2003). SimPed: a
  pedestrian simulation tool for large pedestrian areas. *Proceedings
  of the Euroconference "Pedestrian Evacuation Dynamics"*.
- **본 연구 활용**: 역사 전체 스케일 보행 시뮬레이터의 초기 사례.
  공간 분할과 journey routing 설계의 모범.
- **검증 상태**: 부분 검증 (학회 발표 논문, DOI 부재 가능)

### [A-3] Hoogendoorn & Bovy (2004) — 보행 네트워크 모델링
- **서지**: Hoogendoorn, S. P., & Bovy, P. H. L. (2004). Pedestrian
  route-choice and activity scheduling theory and models.
  *Transportation Research Part B: Methodological*, 38(2), 169–190.
- **DOI**: 10.1016/S0191-2615(03)00007-9
- **본 연구 활용**: 다구간 경로 선택 이론. 본 연구의 Journey
  네트워크(계단→게이트→출구) 설계의 이론적 근거.
- **검증 상태**: 확인됨

### [A-4] Bauer, Brändle, Seer, Ray, Kitazawa (2007) — 지하철역 microsim
- **서지**: Bauer, D., Brändle, N., Seer, S., Ray, M., & Kitazawa, K.
  (2007). Measurement of pedestrian movements: A comparative study
  on various existing systems. *Pedestrian Behavior: Models, Data
  Collection and Applications* (H. Timmermans ed.), Emerald Group.
- **본 연구 활용**: 지하철역 보행 관측 방법론. 현장조사 설계의
  참고.
- **검증 상태**: 부분 검증 (ISBN 978-0-08-045324-1, 장별 서지 재확인
  필요)

### [A-5] Hänseler, Molyneaux, Bierlaire (2017) — 역사 보행 시뮬 통계
- **서지**: Hänseler, F. S., Molyneaux, N. A., & Bierlaire, M.
  (2017). Estimation of pedestrian origin-destination demand in
  train stations. *Transportation Science*, 51(3), 981–997.
- **DOI**: 10.1287/trsc.2016.0700
- **본 연구 활용**: 역사 규모 OD 수요 추정. 본 연구의 승강장→출구
  flow 배분에 적용 가능.
- **검증 상태**: 확인됨 (EPFL TRANSP-OR 연구실, 본 축의 핵심 인용)

### [A-6] Molyneaux, Scarinci, Bierlaire (2018) — 보행 제어 시뮬
- **서지**: Molyneaux, N., Scarinci, R., & Bierlaire, M. (2018).
  Pedestrian management strategies for improving flow dynamics in
  transportation hubs. *hEART 2018 Conference*.
- **본 연구 활용**: transp-or/pedestrian-control-simulator의 바탕
  연구. 다구간 제어 정책(flow_gates, controlled_areas) 개념.
- **검증 상태**: 부분 검증 (학회 발표, DOI 부재)

### [A-7] Molyneaux, Scarinci, Bierlaire (2021) — 보행 제어 정책
- **서지**: Molyneaux, N., Scarinci, R., & Bierlaire, M. (2021).
  Design and analysis of control strategies for pedestrian flows.
  *Transportation*, 48(4), 1767–1806.
- **DOI**: 10.1007/s11116-020-10111-1
- **본 연구 활용**: 본 연구와 가장 근접한 선행연구. 다구간 보행 흐름
  에서 제어 정책(gate, 분리) 효과 정량화. 본 연구의 "게이트 배합
  전략"은 이 연구의 "pedestrian control strategy"와 개념적으로 유사.
- **검증 상태**: 확인됨

---

## 2. 지하철역 특화 연구

### [A-8] Lee, Lam, Wong (2006) — 홍콩 MTR 역사 시뮬레이션
- **서지**: Lee, J. Y. S., Lam, W. H. K., & Wong, S. C. (2006).
  Pedestrian simulation model for Hong Kong underground stations.
  *Proceedings of IEEE Intelligent Transportation Systems Conference*.
- **본 연구 활용**: 홍콩 MTR 지하철역 다구간 시뮬. 본 연구와 유사한
  구조(승강장→대합실→게이트→출구).
- **검증 상태**: 부분 검증 (학회 자료, DOI 부재 가능)

### [A-9] 국내 지하철 역사 시뮬레이션 연구
- 개별 문헌 특정은 검증 필요
- **탐색 대상**: 대한교통학회지, 한국철도학회 논문집, 국토계획(대한
  국토·도시계획학회), 공간정보학회지
- **본 연구 활용 예정**: 국내 역사 LOS 평가/보행 시뮬 사례를
  benchmark로 활용
- **검증 상태**: 검증 필요

---

## 3. 본 연구가 메우는 gap

### Gap 1 — 다구간 통합 모델링의 **제어 변수(게이트 배합)** 부재
- [A-7] Molyneaux 2021: 제어 전략은 다루지만 "태그/태그리스 혼재"
  같은 **이질 서비스율(heterogeneous service rate)** 처리는 안 함.
- 본 연구: 게이트 배합(태그 전용/태그리스 전용/겸용 버퍼) 자체가
  제어 변수.

### Gap 2 — 병목 전이를 **명시적 RQ로 설정**한 연구 드묾
- 기존 다구간 연구는 대부분 "역사 전체 평균 LOS 개선"에 초점.
- 본 연구는 "업스트림 최적화 → 다운스트림 악화" 역설을 핵심 검증
  대상으로 삼음 (축 B와 연계).

### Gap 3 — AFC 과도기 운영 정책 연구 부재
- 태그리스는 2023년 우이신설선이 세계 최초 상용화 → 도입 기간이 짧음.
- 혼재 상황의 정량적 연구가 아직 축적되지 않음.
- 본 연구는 **첫 국내 사례 연구** 중 하나로 자리잡음.

### Gap 4 — MNL Choice Set 차별화 + 시스템 전체 비용 결합
- Gao et al. (2019) 등 MNL 게이트 선택 연구는 **게이트 구간 국소
  최적화**에 머물고, 하류 비용을 반영하지 않음.
- 본 연구는 Choice Set 차별화(이용자 유형별 가용 게이트)와 시스템
  전체 통행비용을 **한 목적함수**에 통합.

---

## 4. 추가 탐색 필요 방향

1. **중국 지하철 대규모 시뮬 연구**: 베이징·상하이·광저우 역사 대상
   AnyLogic/MassMotion/VISSIM Viswalk 연구 다수 존재 추정 → CNKI
   탐색.
2. **일본 역사 시뮬**: Tanaka, Yamamoto, Fujita 등 — 개찰구 특화
   연구.
3. **한국 도시철도 시뮬 연구**: KOTI, 국토연구원, 학회지 전수 재탐색.
4. **transp-or/pedestrian-control-simulator 공식 논문**: Molyneaux
   2018/2021 외 후속 발표 확인.

---

## 5. 본 축에서 확보한 핵심 3편 (강도 순)

1. **Molyneaux, Scarinci, Bierlaire (2021)** — 다구간 제어 전략의 이론적
   기반 (TRANSP-OR 연구실).
2. **Hänseler, Molyneaux, Bierlaire (2017)** — 역사 OD 수요 추정.
3. **Hoogendoorn & Bovy (2004)** — 다구간 경로 선택 이론.

위 3편은 본 연구의 **"역사 전체 관점"** 프레이밍의 이론·방법론 기반.

---
*본 문서는 중간발표 이후 국내 문헌 확증 + Molyneaux 계열 후속 논문
확인으로 rev.2 업데이트 예정.*
