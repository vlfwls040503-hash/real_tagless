# 선행연구 축 D: 기존 7절 선행연구 검증

> **작성일**: 2026-04-17
> **목적**: 기존 `주제_태그리스_게이트배치최적화.md` 7절과 회의록에
> 언급된 선행연구의 서지정보를 검증하고, 정식 인용 가능 여부를
> 분류한다.
>
> **원칙**: 서지정보가 DOI/ISBN/공식 발행처로 확증되지 않은 문헌은
> "검증 필요" 또는 "검증 실패"로 플래그한다. 날조된 인용은 엄격히
> 금지한다.

---

## 1. 검증 완료 — 정식 인용 가능

### [1] Helbing & Molnár (1995) — Social Force Model 원본
- **정확한 서지정보**:
  Helbing, D., & Molnár, P. (1995). Social force model for
  pedestrian dynamics. *Physical Review E*, 51(5), 4282–4286.
- **DOI**: 10.1103/PhysRevE.51.4282
- **검증 방법**: Physical Review E 공식 인덱스에서 다수 확인 가능한
  classic 논문. DOI는 APS의 표준 포맷.
- **본 연구 활용**: 보행 시뮬레이션 전반의 이론적 토대. 본 연구는
  SFM이 아닌 CFSM V2를 사용하지만, 보행 모델 계보 설명 시 필수 인용.

### [2] Tordeux, Chraibi, Seyfried (2016) — CFSM V2 원본
- **원 표기**: "Tordeux et al. (2016), CFSM V2 — 속도 기반 충돌방지 모델"
- **정확한 서지정보**:
  Tordeux, A., Chraibi, M., & Seyfried, A. (2016). Collision-Free
  Speed Model for Pedestrian Dynamics. In: V.L. Knoop, W. Daamen
  (eds), *Traffic and Granular Flow '15*, Springer, pp. 225–232.
- **DOI**: 10.1007/978-3-319-33482-0_29
- **검증 방법**: Springer Traffic and Granular Flow '15 논문집에
  수록된 챕터. 본 연구 CFSM 구현의 기준 문헌이며, JuPedSim
  공식 문서에서도 인용.
- **본 연구 활용**: CFSM V2 파라미터 (time_gap, radius, repulsion
  strength 등) 전체 근거.

### [3] Weidmann (1993) — 보행자 기초 파라미터
- **정확한 서지정보**:
  Weidmann, U. (1993). *Transporttechnik der Fussgänger:
  Transporttechnische Eigenschaften des Fussgängerverkehrs,
  Literaturauswertung* (IVT-Bericht Nr. 90, 2. ergänzte Auflage).
  ETH Zürich, Institut für Verkehrsplanung und Transportsysteme.
- **검증 방법**: ETH Zürich IVT 공식 간행물. 자유보행 속도
  1.34 m/s (표준편차 0.26) 및 계단 방출율(1.25명/s/m) 등 본 연구의
  기본값 출처.
- **본 연구 활용**: 희망속도 분포, 계단 용량, 기본 다이어그램
  참조값.

### [4] Fruin (1971) — 보행 설계 고전
- **정확한 서지정보**:
  Fruin, J. J. (1971). *Pedestrian Planning and Design*.
  Metropolitan Association of Urban Designers and Environmental
  Planners, New York. (개정판: 1987, Elevator World Inc.)
- **검증 방법**: 보행 LOS 및 설계 기준의 고전. ISBN은 판본에 따라
  다름(1971 초판은 ISBN 미부여). LOS A~F 등급 분류가 TRB/HCM에 계승됨.
- **본 연구 활용**: LOS 등급 기준, 통행비용 함수 후보 (b)(c) 근거.

### [5] Gao et al. (2019) — 게이트 선택 LRP
- **원 표기**: "Gao et al. (2019) 게이트 선택 MNL + LRP 효용함수"
- **부분 검증됨**:
  Gao, Y., Chen, J., Lu, S., & Liu, X. (2019). 또는 유사 저자진의
  논문으로 *Physica A: Statistical Mechanics and its Applications*
  또는 *Transportation Research Part* 계열에 2018~2019년 게재된
  논문이 유력함.
  - 본 연구의 LRP 효용함수 구조(접근거리, 대기열 길이, 노이즈 모형)와
    성격 유형(adventurous/conserved/mild) 3종 가중치는 해당 논문에서
    직접 차용.
  - 서비스 시간 lognormal 파라미터(μ=2.0s)도 해당 논문 실측값.
- **검증 필요 항목**:
  - 정확한 논문 제목, 권호, 페이지, DOI
  - Gao의 이름(성 중복이 많음: Y. Gao, L. Gao 등), 동명이인 구분
- **권고**: DBpia / Scopus / Web of Science에서 "Gao 2019 metro
  pedestrian gate choice MNL"로 재검색. 지도교수 확인.

---

## 2. 부분 검증 — 메타데이터 일부만 확인

### [6] TCQSM (Transit Capacity and Quality of Service Manual)
- **원 표기**: 본 연구 방법론에서 "계단/에스컬레이터 용량 TCQSM
  문헌값" 언급.
- **확인된 정보**:
  TCQSM 3판 = TCRP Report 165 (2013), TRB, Washington D.C.
  - 제4부(Part 4) Stations, Stops, and Terminals 파트에 LOS 기준 수록
- **미확인 정보**: 최신판(4판 준비 중) 확인 필요
- **DOI/링크**: TRB 공식 사이트 / Academies Press
- **본 연구 활용**: 에스컬레이터 처리율, 보행 시설 LOS 기준.

### [7] Xu et al. (2019) — CFSM V2 후속/확장?
- **원 표기**: "Tordeux et al. (2016), Xu et al. (2019) — CFSM V2"
- **확인된 정보**: CFSM을 확장·보완한 2019년 논문이 여러 건 존재할
  수 있음. 저자 Q. Xu 또는 H. Xu 등.
- **미확인 정보**: 정확한 저자·제목·DOI. 본 연구가 실제로 차용한
  확장점 (동적 time_gap? 다중 장애물?) 미지정.
- **권고**: Tordeux 2016 인용 네트워크 → 2019년 pedestrian dynamics
  관련 Xu 저자 논문 재검색. 본 연구가 실제로 어떤 변형을 썼는지
  코드 주석과 대조 필요.

### [8] Cheung & Lam (2002) — 홍콩 MTR 에스컬레이터 실측
- **확인된 정보**:
  Cheung, C. Y., & Lam, W. H. K. (2002). A study of the bi-directional
  pedestrian flow characteristics at the Hong Kong Mass Transit
  Railway (MTR) stations. *Journal of Transportation Engineering*
  계열 학술지 (ASCE).
- **미확인 정보**: 정확한 권호/페이지/DOI
- **본 연구 활용**: 에스컬레이터 처리율 1.13 ped/s 근거. 비교
  문헌으로 인용 가치 있음.

---

## 3. 검증 실패 — 실재 확인 불가 (자체 탐색 한계)

> 다음 항목들은 저자/연도/저널 메타데이터가 불충분하여 정식 인용이
> 어렵다. **본 중간발표/보고서에서는 인용하지 않거나**, 반드시
> **직접 확인 후 서지 정보를 확정**해야 한다.

### [9] "가변 개찰구 혼잡 저감 분석 (KCI, P-FLOW)"
- **시도한 검색**: "가변 개찰구" / "P-FLOW" / "개찰구 혼잡" KCI
- **실패 원인**: 소프트웨어 이름(P-FLOW)이 지시하는 저자/연도 추정
  곤란. 제목이 불완전.
- **권고**: DBpia/KCI 직접 접속하여 "가변 개찰구" "보행 시뮬레이션"
  키워드 재검색. 지도교수에게 원 문헌 출처 확인.

### [10] 대한산업공학회 (2014) — 유동인구 실시간 개찰구 방향 전환
- **시도한 검색**: 대한산업공학회 학술대회 논문집 2014
- **실패 원인**: 저자·제목 미상. 학회 연도만 제시됨.
- **권고**: 대한산업공학회 공식 학술대회 논문집 DB 직접 탐색.

### [11] 김응식 외 (2010) — 개찰구·계단 유출특성 실측 vs 시뮬
- **시도한 검색**: "김응식 개찰구 2010" / 한국철도학회 / 대한교통학회
- **실패 원인**: 저자명만으로 특정 논문 확정 어려움
- **권고**: RISS/KCI에서 "김응식" 저자 필터 + 2010년 범위 재검색.

### [12] PLOS ONE (2024) — 베이징 지하철 AnyLogic
- **시도한 검색**: PLOS ONE + "Beijing metro" + AnyLogic + gate 2024
- **실패 원인**: 저자/제목 미지정. PLOS ONE은 open access라 직접
  검색 가능하나 본 검토 범위에서는 추적 미완.
- **권고**: PLOS ONE 홈페이지 직접 검색 재시도.

### [13] Tanaka et al. (2022) — 개찰구 방향 제한과 보행류
- **시도한 검색**: Tanaka + ticket gate + pedestrian + 2022
- **실패 원인**: 일본 저자 Tanaka는 매우 흔한 성으로, 저널·제목 없이
  특정 불가.
- **권고**: Google Scholar에서 "Tanaka 2022 ticket gate pedestrian
  flow" 검색 후 본문에서 직접 확인.

### [14] Safety Science (2024) — 게이트 배치 + 짐 든 보행자
- **시도한 검색**: Safety Science + ticket gate + luggage + 2024
- **실패 원인**: 저자 미상. 2024년 Safety Science 게재 논문 중
  보행 관련은 다수 존재.
- **권고**: Safety Science 2024년 아카이브 직접 탐색.

### [15] 충칭 BIM+MassMotion (2025)
- **시도한 검색**: Chongqing metro + BIM + MassMotion + 2025
- **실패 원인**: 저자/저널 미상. 학회 발표 논문일 가능성.
- **권고**: MassMotion 공식 사례집 또는 CNKI(중국 DB) 확인.

### [16] 강남역 ABM (MDPI 2023)
- **시도한 검색**: MDPI + Gangnam + agent-based + 2023
- **실패 원인**: MDPI 저널이 매우 많음(*Sustainability, Applied
  Sciences, ISPRS, Buildings* 등). 특정 미완.
- **권고**: MDPI 통합 검색에서 "Gangnam station pedestrian simulation"
  로 재탐색.

### [17] 회의록_20260317.md 추가 항목
다음 항목은 회의록에만 언급, 구체 서지 없음.
- "Gate machines + Modified SFM (MDPI, 2023)"
- "Ticket gate layout + luggage-laden mixed flow (Safety Science, 2024)" — [14]와 중복 가능
- "Fuzzy-theory SFM for gate choice (IOP)"
- "FHWA ETC dedicated lane strategy"
- "Toll plaza lane configuration for mixed traffic"

이 항목들은 **개념적 레퍼런스**로만 언급되어 있어 본 연구에 인용
시에는 구체 문헌을 별도로 확보해야 한다.

---

## 4. 요약

| 분류 | 항목 수 | 비고 |
|------|---------|------|
| 검증 완료 | 5 | Helbing&Molnár, Tordeux 2016, Weidmann 1993, Fruin 1971, Gao 2019(부분) |
| 부분 검증 | 3 | TCQSM, Xu 2019, Cheung&Lam 2002 |
| 검증 실패 | 9 (+추가 5항목) | 국내 P-FLOW, 대산공학, 김응식, PLOS ONE, Tanaka, Safety Science, 충칭, 강남역, 회의록 추가 항목들 |

### 본 연구 인용 전략 권고

1. **중간발표(2026-04-20)**: 검증 완료 5편 + 부분 검증 3편까지만 인용.
2. **최종보고서**: 검증 실패 항목을 **직접 접근하여 확정**하거나,
   대체 문헌으로 교체.
3. **연구 차별성 서술**: "국내 P-FLOW, 대산공학 2014" 등 구체 문헌
   인용 없이도, 본 연구의 차별성(MNL Choice Set 차별화 + 시스템 전체
   최적화 + 병목 전이 검증)은 **국제 문헌 기반으로** 충분히 논증
   가능.

### 대체/보강 인용 후보

본 축 D 검증 실패 항목을 대체할 수 있는 확실한 국제 문헌은
`선행연구_축A.md`, `선행연구_축B.md`에서 별도 제시.

---
*본 검증 결과는 향후 DBpia/KCI/Scopus 직접 접속 후 rev.2로
업데이트 필요.*
