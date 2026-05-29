미터링 (상류/하류 분리) + Pareto (효율성-안전성) 분석
========================================

[표/]
  delta_table.csv               baseline 대비 (p, K) 별 통행시간/밀도 변화 + 종합평가
  pareto_frontier_table.csv     Pareto frontier 여부 표시
  upstream_downstream_summary.csv  상류/하류 metric (게이트 라인 x=12 분리)

[그림/]
  k_comparison_p50.png          p=0.5 K=2 vs K=3 평면 비교 (상류 큐 + 하류 군집)
  upstream_vs_downstream_metrics.png   K별 상류/하류 peak 밀도 막대
  pareto_scatter.png            효율(통행시간) vs 안전(밀도) Pareto 산점도

[스크립트/]
  metering_pareto.py            본 분석 자동화 스크립트

[baseline/]
  baseline_summary.csv          p=0 K=0 시뮬 5 seed 결과 (delta 기준)


─── 분석 영역 정의 ───
게이트 라인 x = 12.0 m
상류부 (Pre-gate): x ∈ [0, 12], y ∈ [5, 20]
하류부 (Post-gate): x ∈ [13.5, 36], y ∈ [-2, 28]
W2 zone (에스컬 앞): x ∈ [23.75, 28.75], y ∈ [20.75, 24.75], 20 m²


─── 핵심 결과 ───
Baseline (p=0 K=0): 통행시간 52.59s, W2 peak 0.61

채택 K (LOS D ≤ 1.0 제약):
  p=0.1 → K=1: 53.09s (+0.95%),  W2pk 0.64
  p=0.3 → K=2: 50.46s (-4.04%),  W2pk 0.81
  p=0.5 → K=2: 49.95s (-5.02%),  W2pk 0.84
  p=0.7 → K=2: 57.52s (+9.37%),  W2pk 0.54
  p=0.8 → K=4: 48.09s (-8.55%),  W2pk 0.95

가변 운영 가중평균 통행시간 = 52.09s
  (baseline 52.59s 대비 -0.50s, -0.95%)
