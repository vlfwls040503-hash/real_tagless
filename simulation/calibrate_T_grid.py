"""
CFSM time_gap (T) 그리드 서치 — V&V 검증 시뮬 활용.
V3 결과 list 처리 + stdout flush 수정 버전.
"""
from __future__ import annotations
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "simulation"))

import verify_cfsm_basic as vcb

T_GRID = [0.6, 0.7, 0.8, 0.9, 1.0]
results = []

for T in T_GRID:
    print(f"\n{'=' * 60}\n[T = {T}]\n{'=' * 60}", flush=True)
    vcb.CFSM_AGENT_PARAMS['time_gap'] = T

    # V2: 기본다이어그램 (RMSE 단일 float)
    try:
        v2_pass, v2_rmse = vcb.test_fundamental_diagram()
        print(f"\n[T={T}] V2 RMSE = {v2_rmse:.4f}", flush=True)
    except Exception as e:
        print(f"[T={T}] V2 ERROR: {e}", flush=True)
        v2_pass, v2_rmse = False, None

    # V3: 병목 유량 (list of [width, Js_sim, Js_sey, err_pct, status])
    try:
        v3_pass, v3_results = vcb.test_bottleneck_flow()
        # 평균 err%
        errs = [row[3] for row in v3_results]
        widths = [row[0] for row in v3_results]
        v3_mean_err = sum(errs) / len(errs)
        print(f"\n[T={T}] V3 mean err = {v3_mean_err:.2f}%  (폭별: {dict(zip(widths, [round(e,1) for e in errs]))})", flush=True)
    except Exception as e:
        print(f"[T={T}] V3 ERROR: {e}", flush=True)
        v3_pass, v3_mean_err, v3_results = False, None, None

    results.append({
        'T': T,
        'V2_pass': bool(v2_pass), 'V2_rmse': v2_rmse,
        'V3_pass': bool(v3_pass), 'V3_mean_err_pct': v3_mean_err,
        'V3_per_width': [list(row) for row in (v3_results or [])],
    })
    sys.stdout.flush()

# 요약 출력
print("\n" + "=" * 60, flush=True)
print("=== T 그리드 결과 요약 ===", flush=True)
print("=" * 60, flush=True)
print(f"{'T':>4} | {'V2 RMSE':>9} | {'V2':>4} | {'V3 평균err%':>11} | {'V3':>4}", flush=True)
print("-" * 55, flush=True)
for r in results:
    rmse_s = f"{r['V2_rmse']:.4f}" if r['V2_rmse'] is not None else "ERR"
    err_s  = f"{r['V3_mean_err_pct']:.2f}%" if r['V3_mean_err_pct'] is not None else "ERR"
    print(f"{r['T']:>4.1f} | {rmse_s:>9s} | {'PASS' if r['V2_pass'] else 'FAIL':>4} | "
          f"{err_s:>11s} | {'PASS' if r['V3_pass'] else 'FAIL':>4}", flush=True)

# 최적 T (V3 mean err 최소)
valid = [r for r in results if r['V3_mean_err_pct'] is not None]
if valid:
    best = min(valid, key=lambda r: r['V3_mean_err_pct'])
    print(f"\n[최적 T] = {best['T']} (V3 평균 err {best['V3_mean_err_pct']:.2f}%, V2 RMSE {best['V2_rmse']:.4f})", flush=True)

out = ROOT / "results" / "molit" / "calibration_T_grid.json"
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\n저장: {out}", flush=True)
