# 선행연구 축 C: 통행비용 함수 및 LOS 가중 방법론

> **작성일**: 2026-04-17
> **대상 RQ**: 연구설계 v2 4절 통행비용 함수 설계의 문헌 근거 확보.
> **원칙**: 검증된 표준 문헌 중심. 불확실한 항목은 "검증 필요" 플래그.

---

## 조사 범위 및 키워드

- pedestrian travel cost function
- perceived density cost
- LOS-weighted pedestrian flow
- pedestrian level of service (LOS)
- walking comfort density
- crowding cost transit
- value of crowding pedestrian
- 보행 서비스 수준 / 혼잡 비용 / 통행비용

---

## 1. LOS 및 밀도-속도 기본 문헌 (확증 가능)

### [C-1] Fruin (1971) *Pedestrian Planning and Design*
- **서지**: Fruin, J. J. (1971). *Pedestrian Planning and Design*.
  Metropolitan Association of Urban Designers and Environmental
  Planners, New York. (재판: 1987, Elevator World Inc.)
- **본 연구 활용**:
  - LOS A~F 등급표(인/㎡ 기준 boundary)의 **원조 문헌**
  - 속도-밀도 기본다이어그램 초기 형태
  - 통행비용 후보 (b) LOS 페널티 방식 및 (c) 비선형 승수의 근거
- **검증 상태**: 확인됨 (교통공학 고전)

### [C-2] TCQSM 3판 = TCRP Report 165 (2013)
- **서지**: Kittelson & Associates et al. (2013). *Transit Capacity
  and Quality of Service Manual, 3rd Edition* (TCRP Report 165).
  Transportation Research Board, Washington, D.C.
- **본 연구 활용**:
  - 보행 시설 LOS 기준 (Part 4, Chapter 10 Station Capacity)
  - 에스컬레이터/계단 처리율 표준값
  - 통행시간 기반 서비스 수준 지표
- **검증 상태**: 확인됨 (TRB 공식 발간). 4판 발간 여부는 별도 확인.

### [C-3] HCM (Highway Capacity Manual) — Pedestrian Facilities 챕터
- **서지**:
  - HCM 6판: Transportation Research Board (2016). *Highway
    Capacity Manual, 6th Edition: A Guide for Multimodal Mobility
    Analysis*. Washington, D.C.
  - HCM 7판: Transportation Research Board (2022). *Highway
    Capacity Manual, 7th Edition*. Washington, D.C.
- **본 연구 활용**:
  - 보행 시설 LOS 산정 공식 (Exhibit 24-x 관련)
  - Fruin의 LOS를 계승/개량한 공식 표준
- **검증 상태**: 확인됨 (국가 표준급 공식 간행물)

### [C-4] Weidmann (1993) *Transporttechnik der Fussgänger*
- **서지**: Weidmann, U. (1993). *Transporttechnik der Fussgänger:
  Transporttechnische Eigenschaften des Fussgängerverkehrs,
  Literaturauswertung* (IVT-Bericht Nr. 90). ETH Zürich.
- **본 연구 활용**:
  - 자유보행 속도 평균 1.34 m/s, 표준편차 0.26
  - 계단 하행 방출율 1.25 명/s/m
  - 밀도-속도 관계식 (Weidmann 공식)
- **검증 상태**: 확인됨

### [C-5] Older (1968) — 보행 속도-밀도 초기 관측
- **서지**: Older, S. J. (1968). Movement of pedestrians on footways
  in shopping streets. *Traffic Engineering and Control*, 10,
  160–163.
- **본 연구 활용**: 속도-밀도 감쇠 관계의 초기 실증
- **검증 상태**: 부분 검증 (연도/저널 확인됨, 페이지 재확인 권고)

---

## 2. 통행비용 함수 및 혼잡 가치 평가

### [C-6] Wardman (2004) — 대중교통 통행비용 가치
- **서지**: Wardman, M. (2004). Public transport values of time.
  *Transport Policy*, 11(4), 363–377.
- **DOI**: 10.1016/j.tranpol.2004.05.001
- **본 연구 활용**: 통행비용 함수 후보 (a) 가중합 방식의 α 계수
  (시간 가치) 근거. 대기시간/차내 혼잡 시간의 상대 가중치.
- **검증 상태**: 확인됨 (Transport Policy 표준 인용)

### [C-7] Wardman & Whelan (2011) — 혼잡 비용 산정
- **서지**: Wardman, M., & Whelan, G. (2011). Twenty years of
  rail crowding valuation studies: evidence and lessons from
  British experience. *Transport Reviews*, 31(3), 379–398.
- **DOI**: 10.1080/01441647.2010.519127
- **본 연구 활용**: 혼잡도별 통행 비용 배수 — 본 연구 후보 (c)
  비선형 승수 m(ρ)의 국제 실증값 참고.
- **검증 상태**: 확인됨

### [C-8] Tirachini, Hensher, Rose (2013) — 대중교통 혼잡 종합
- **서지**: Tirachini, A., Hensher, D. A., & Rose, J. M. (2013).
  Crowding in public transport systems: Effects on users, operation
  and implications for the estimation of demand. *Transportation
  Research Part A: Policy and Practice*, 53, 36–52.
- **DOI**: 10.1016/j.tra.2013.06.005
- **본 연구 활용**: 혼잡이 수요·운영·비용 전반에 미치는 영향의
  종합 리뷰. 통행비용 함수 설계의 이론적 체계 제공.
- **검증 상태**: 확인됨

### [C-9] Li & Hensher (2011) — 대중교통 혼잡가치 메타분석
- **서지**: Li, Z., & Hensher, D. A. (2011). Crowding and public
  transport: A review of willingness to pay evidence and its
  relevance in project appraisal. *Transport Policy*, 18(6), 880–887.
- **DOI**: 10.1016/j.tranpol.2011.06.003
- **본 연구 활용**: 혼잡 지불의사(WTP) 수치 — α/β 계수 범위의
  해외 benchmark.
- **검증 상태**: 확인됨

---

## 3. 보행 기본다이어그램 및 속도-밀도 관계

### [C-10] Zhang, Klingsch, Schadschneider, Seyfried (2012)
- **서지**: Zhang, J., Klingsch, W., Schadschneider, A., &
  Seyfried, A. (2012). Ordering in bidirectional pedestrian flows
  and its influence on the fundamental diagram. *Journal of
  Statistical Mechanics: Theory and Experiment*, 2012, P02002.
- **DOI**: 10.1088/1742-5468/2012/02/P02002
- **본 연구 활용**: 기본다이어그램의 순서 효과. 본 연구에서는 사용
  하지 않지만 양방향 확장 시 참고.
- **검증 상태**: 확인됨

### [C-11] Seyfried, Steffen, Klingsch, Boltes (2005)
- **서지**: Seyfried, A., Steffen, B., Klingsch, W., & Boltes, M.
  (2005). The fundamental diagram of pedestrian movement revisited.
  *Journal of Statistical Mechanics: Theory and Experiment*, 2005,
  P10002.
- **DOI**: 10.1088/1742-5468/2005/10/P10002
- **본 연구 활용**: single-file 실험 데이터. 본 연구의
  `calibrate_cfsm.py`에 FZJ Seyfried (2005) 데이터 적용됨.
  - 직접 통행비용 함수에 사용되진 않으나, 속도-밀도 관계의
    ground truth로 활용.
- **검증 상태**: 확인됨 (JuPedSim 공식 예제에도 인용)

### [C-12] Cheung & Lam (2002) — 홍콩 MTR 양방향 흐름
- **서지**: Cheung, C. Y., & Lam, W. H. K. (2002). A study of the
  bi-directional pedestrian flow characteristics at the Hong Kong
  Mass Transit Railway (MTR) stations. *Journal of Transportation
  Engineering (ASCE)*.
- **본 연구 활용**: 홍콩 MTR 보행 특성, 에스컬레이터 처리율 근거.
- **검증 상태**: 부분 검증 (권호/페이지/DOI 재확인 필요)

---

## 4. 한국 연구 (국내 LOS 적용)

> 본 섹션의 항목들은 일부 검증 필요. 실제 확증은 DBpia/KCI 접속
> 후 중간발표 이후 rev.2로 업데이트.

### [C-13] 김황배·원제무 류 — 도시철도 환승역 보행 LOS
- **서지 후보**: 김황배, 원제무 외 (2000년대~2010년대). 도시철도
  환승역 보행 서비스 수준 평가 연구 — 대한교통학회지 또는 한국철도
  학회 논문집.
- **검증 상태**: 검증 필요 (정확한 권호/제목 확인 요함).
- **본 연구 활용 예정**: 국내 LOS 적용 사례, 통행비용 가중치의
  국내 benchmark.

### [C-14] 한국철도학회 / 대한교통학회 논문집
- 다수의 지하철 환승역 보행 시뮬 논문 존재 가능.
- **검증 상태**: DBpia/KCI 접근 후 확정 예정.

### [C-15] 국토연구원 / 한국교통연구원(KOTI) 보고서
- 대중교통 시설 LOS 및 혼잡 관련 연구 보고서 다수 발간.
- **검증 상태**: 기관 공식 사이트 확인 필요.

---

## 5. 통행비용 함수 후보 3종 비교 매핑

| 후보 | 수식 개요 | 근거 문헌 | 파라미터 추정 가능성 | 장단점 요약 |
|------|-----------|-----------|---------------------|-------------|
| **(a) 가중합** | TC = α·T + β·∫ρ·dt | Wardman 2004, Tirachini 2013, Li&Hensher 2011 | α,β 2개 — 문헌값 범위에서 민감도 분석 | 단순·해석 용이 / 비선형성 무시 |
| **(b) LOS 페널티** | TC = T + Σ w_k·t_k | Fruin 1971, TCQSM 2013, HCM 2016/2022 | w_k 6개 — 임의 가중, 정책 의사소통에 유리 | 직관적 / 계단형 불연속 |
| **(c) Fruin 비선형 승수** | TC = ∫ m(ρ)·dt | Fruin 1971, Weidmann 1993, Zhang 2012, Seyfried 2005 | m(ρ) = v_free/v(ρ) 형태면 파라미터 프리 | 연속·물리 정합 / 식 선택 민감 |

---

## 6. 본 연구 권고안

### 권고 (연구설계 v2 §4-5와 동일)

- **주 지표**: 후보 **(c) Fruin 비선형 승수**. RQ3 임계점 탐지에
  불연속성 최소화가 필수.
- **보조 지표**: 후보 **(b) LOS 페널티**. 중간발표/최종보고서
  시각화 및 정책 함의 전달용.
- **검증 지표**: 후보 **(a) 가중합**. 세 지표가 동일한 p*를 지목하면
  결과 강건성 확보.

### 민감도 분석 계획

| 파라미터 | 수준 | 문헌 근거 |
|----------|------|----------|
| α (시간가치) | 0.5 / 1.0 / 1.5 (상대) | Wardman 2004 |
| β (밀도비용) | 0.3 / 0.6 / 1.0 | Tirachini 2013 |
| w_F (LOS F 페널티) | 1.5 / 3.0 / 5.0 | Fruin 1971 등급 간격 |
| m(ρ) 함수형 | 선형 / 이차 / Weidmann | Weidmann 1993 실증 곡선 |

---

## 7. 추가 탐색 필요 방향

1. **국내 지하철 대상 LOS 연구** — DBpia/KCI에서 직접 검색
2. **혼잡 가치 한국 연구** — KOTI, 국토연구원 보고서
3. **TCQSM 4판 출간 여부** — 2026년 기준 확인
4. **보행 혼잡의 심리적 비용** (perceived crowding psychology) —
   본 연구 통행비용의 "지각비용(perceived cost)" 서술에 추가 근거

---
*본 문서는 연구설계 v2 §4와 상호 참조하며, rev.2에서 한국 연구
확정 후 업데이트.*
