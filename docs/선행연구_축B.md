# 선행연구 축 B: 병목 전이 / 다운스트림 혼잡 전파

> **작성일**: 2026-04-17
> **대상 RQ**: 본 연구 RQ3 — 게이트 처리속도 향상이 하류 구간 혼잡
> 증가로 전이되는 임계점 p* 존재 여부 검증.
> **원칙**: 차량 흐름 이론에서 정립된 병목 전이 이론을 보행 흐름으로
> 확장하는 관점에서 문헌을 조사한다. 검증 실패 항목은 플래그.

---

## 조사 범위 및 키워드

- bottleneck shift / bottleneck relocation
- pedestrian congestion propagation
- downstream congestion
- spillback pedestrian
- kinematic wave pedestrian
- queueing bottleneck transfer
- 교통 병목 전이 / 하류 혼잡

---

## 1. 차량 흐름 병목 전이 고전 이론 (확증 가능)

### [B-1] Lighthill & Whitham (1955) — LWR 모델 원조
- **서지**: Lighthill, M. J., & Whitham, G. B. (1955). On kinematic
  waves II: A theory of traffic flow on long crowded roads.
  *Proceedings of the Royal Society A*, 229(1178), 317–345.
- **DOI**: 10.1098/rspa.1955.0089
- **본 연구 활용**: 충격파(shock wave) 형성·전파 이론. 게이트의 방출률
  개선이 하류 방출 용량과 불일치할 때 전이 구간에서 정체 형성을
  설명하는 고전 이론.
- **검증 상태**: 확인됨

### [B-2] Richards (1956) — Shock wave on highway
- **서지**: Richards, P. I. (1956). Shock waves on the highway.
  *Operations Research*, 4(1), 42–51.
- **DOI**: 10.1287/opre.4.1.42
- **본 연구 활용**: LWR와 쌍을 이루는 고전. 상류 공급량이 하류 용량을
  초과할 때 shock의 상류 전파 — 본 연구의 "게이트 속도 개선 → 하류
  정체" 메커니즘에 직접 적용.
- **검증 상태**: 확인됨

### [B-3] Newell (1993) — 간이 동역학 이론
- **서지**: Newell, G. F. (1993). A simplified theory of kinematic
  waves in highway traffic (Parts I, II, III). *Transportation
  Research Part B: Methodological*, 27(4), 281–313.
- **DOI**: 10.1016/0191-2615(93)90038-C
- **본 연구 활용**: 병목 전이 현상을 triangular FD 기반으로 간명히
  설명. 본 연구의 정성적 해석 도구.
- **검증 상태**: 확인됨

### [B-4] Daganzo (1994) — Cell Transmission Model
- **서지**: Daganzo, C. F. (1994). The cell transmission model: a
  dynamic representation of highway traffic consistent with the
  hydrodynamic theory. *Transportation Research Part B*, 28(4),
  269–287.
- **DOI**: 10.1016/0191-2615(94)90002-7
- **본 연구 활용**: LWR를 이산화한 공학적 모델. 본 연구에서 직접
  적용하진 않지만, 병목 전이의 셀 단위 해석 모델로 인용 가능.
- **검증 상태**: 확인됨

### [B-5] Daganzo (1999) — Moving bottleneck
- **서지**: Daganzo, C. F. (1999). Remarks on moving bottlenecks
  *(working paper or Transportation Research B 관련)*.
- **검증 상태**: 검증 필요 (정확한 출간 정보 재확인)
- **본 연구 활용 예정**: "게이트 구간의 병목이 하류로 이동" 개념의
  이론적 참조.

---

## 2. 보행 병목 및 하류 전이 연구

### [B-6] Seyfried, Rupprecht, Passon, Steffen, Klingsch, Boltes (2009) — 병목 유량 실측
- **서지**: Seyfried, A., Rupprecht, T., Passon, O., Steffen, B.,
  Klingsch, W., & Boltes, M. (2009). New insights into pedestrian
  flow through bottlenecks. *Transportation Science*, 43(3), 395–406.
- **DOI**: 10.1287/trsc.1090.0263
- **본 연구 활용**: 보행 병목 용량 실측. 본 연구의 에스컬레이터
  병목 처리율 산정의 실증적 근거.
- **검증 상태**: 확인됨

### [B-7] Kretz, Grünebohm, Schreckenberg (2006) — 좁아지는 통로
- **서지**: Kretz, T., Grünebohm, A., & Schreckenberg, M. (2006).
  Experimental study of pedestrian flow through a bottleneck.
  *Journal of Statistical Mechanics: Theory and Experiment*, 2006,
  P10014.
- **DOI**: 10.1088/1742-5468/2006/10/P10014
- **본 연구 활용**: 병목 폭 변화에 따른 유량 실험. 본 연구의 출구
  에스컬레이터 폭(1m) 유량 가정의 benchmark.
- **검증 상태**: 확인됨

### [B-8] Hoogendoorn & Daamen (2005) — 병목에서 보행 자기조직화
- **서지**: Hoogendoorn, S. P., & Daamen, W. (2005). Pedestrian
  behavior at bottlenecks. *Transportation Science*, 39(2), 147–159.
- **DOI**: 10.1287/trsc.1040.0102
- **본 연구 활용**: zipping/layering 등 병목에서의 자기조직화.
  에스컬레이터 앞 군집 대기 행태의 이론적 근거.
- **검증 상태**: 확인됨

### [B-9] Helbing, Johansson, Al-Abideen (2007) — 군중 재난과 압박파
- **서지**: Helbing, D., Johansson, A., & Al-Abideen, H. Z. (2007).
  Dynamics of crowd disasters: An empirical study. *Physical Review
  E*, 75(4), 046109.
- **DOI**: 10.1103/PhysRevE.75.046109
- **본 연구 활용**: 하류 병목에서 상류로 전파되는 압박파 실증.
  "게이트→출구 방향의 역압박" 해석에 직접 인용 가능.
- **검증 상태**: 확인됨

---

## 3. 네트워크 보행/교통 병목 전이

### [B-10] Daganzo (2007) — 도시 네트워크 혼잡 전파
- **서지**: Daganzo, C. F. (2007). Urban gridlock: Macroscopic
  modeling and mitigation approaches. *Transportation Research Part
  B*, 41(1), 49–62.
- **DOI**: 10.1016/j.trb.2006.03.001
- **본 연구 활용**: 네트워크 단위 혼잡 전파. 보행 네트워크로의 확장
  가능성.
- **검증 상태**: 확인됨

### [B-11] Geroliminis & Daganzo (2008) — MFD
- **서지**: Geroliminis, N., & Daganzo, C. F. (2008). Existence of
  urban-scale macroscopic fundamental diagrams: Some experimental
  findings. *Transportation Research Part B*, 42(9), 759–770.
- **DOI**: 10.1016/j.trb.2008.02.002
- **본 연구 활용**: 네트워크 단위 기본다이어그램. 역사 전체의
  "처리량-누적 밀도" 관계로 확장 가능.
- **검증 상태**: 확인됨

---

## 4. 역사/AFC 특화 병목 전이 연구

### [B-12] (검증 필요) AFC 전이 및 게이트 하류 병목
- **탐색 대상 키워드**: "fare gate bottleneck shift",
  "AFC downstream congestion", "metro station platform crowding
  from gate"
- **검증 상태**: 검증 필요. 축 A 문헌 목록과 상당 부분 중첩되며,
  본 축 관점(병목 전이)에서 명시적으로 다룬 논문은 제한적이어서
  본 연구의 **novelty 입지**가 확보됨.

### [B-13] FHWA ETC(Electronic Toll Collection) 전용 차선
- **탐색 대상**: FHWA 간행 "ETC dedicated lane strategy" 보고서
- **검증 상태**: 검증 필요 (구체 보고서 번호 미상)
- **본 연구 활용 예정**: 고속도로 하이패스 전용 차선 정책이 **본선
  하류(램프/요금소 이후)**에 미치는 영향 — 본 연구의 아날로지
  (게이트 전용 분리 → 하류 에스컬레이터 영향)에 직접 대응.

---

## 5. 본 연구가 메우는 gap

### Gap 1 — 차량 이론 → 보행 이론 전이의 정량 검증 부족
- 차량(LWR, Newell, Daganzo)에서 병목 전이는 이론·실증 확립.
- 보행에서 병목 유량·자기조직화는 연구 있으나, **업스트림 용량 개선
  → 다운스트림 새 병목** 시나리오 연구는 드묾.
- 본 연구: 태그리스 도입이라는 현실 시나리오를 이용해 이 gap 검증.

### Gap 2 — AFC 전이 과도기 특화 연구 부재
- ETC(차량) 전용 차선의 전이 분석은 존재.
- 지하철 태그리스(보행)의 **과도기 운영**은 아직 정량 연구 희소.
- 본 연구: 국내 최초급 실증.

### Gap 3 — 임계점 p* 탐지 방법론
- 기존 연구는 "병목이 있다/없다"의 이분법.
- 본 연구: 독립변수 p를 연속적으로 변화시켜 **임계점의 위치**를
  탐지하는 분석 틀 제공.

---

## 6. 본 축에서 확보한 핵심 3편 (강도 순)

1. **Lighthill & Whitham (1955)** / **Richards (1956)** — 병목 전이
   이론의 고전. RQ3 프레이밍의 이론적 앵커.
2. **Helbing, Johansson, Al-Abideen (2007)** — 보행에서 압박파 실증.
3. **Seyfried et al. (2009)** — 보행 병목 용량 실측.

---

## 7. 추가 탐색 필요 방향

1. **Hoogendoorn & Bovy 후속**: 보행 network loading model
2. **Zhang, Seyfried 등 J-Stat-Mech 시리즈**: 보행 FD 최신 업데이트
3. **한국교통연구원(KOTI) 환승 혼잡 보고서**: 국내 맥락
4. **ETC 전용 차로 관련 국토부/FHWA 보고서**: 아날로지 보강

---
*본 문서는 연구설계 v2 §1-3(부분 최적화의 함정)과 §2-2 RQ3의 주
인용원으로 사용된다.*
