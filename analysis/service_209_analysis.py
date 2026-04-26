"""
SERVICE_TIME_MEAN = 2.09 시나리오 — 최적 cfg 산정.

흐름: zone 도출 (합집합) → 밀도 재집계 → G/S 최적 cfg + LOS E 비교
출력: results_service_209/OPTIMAL_CFG_209.txt
"""
from __future__ import annotations
from pathlib import Path
import sys
import json
import numpy as np
import pandas as pd
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "docs"))
from analysis.molit_los import WALKWAY_LOS, grade
from space_layout import SPACE  # noqa

RES = ROOT / "results_service_209"
RAW = RES / "raw"
SUMMARY = RES / "summary.csv"
OUT = RES / "OPTIMAL_CFG_209.txt"

PASS_RATE_MIN = 0.9
LOS_E_MAX = 1.0

BIN = 0.5
WAIT_SPEED = 0.5
DILATE_ITERS = 2
BUFFER = 0.25
THRESHOLD_FRAC = 0.08
MIN_DENSITY = 0.02
BBOX_DOMAIN = (-2.0, 36.0, -2.0, 27.0)


def los(d):
    return grade(d, WALKWAY_LOS)


def derive_zones(valid):
    x0, x1, y0, y1 = BBOX_DOMAIN
    x_edges = np.arange(x0, x1 + BIN, BIN)
    y_edges = np.arange(y0, y1 + BIN, BIN)
    H_total = np.zeros((len(x_edges) - 1, len(y_edges) - 1))
    n_used = 0
    for sid in valid:
        tp = RAW / f"trajectory_{sid}.csv"
        if not tp.exists():
            continue
        df = pd.read_csv(tp)
        df = df.sort_values(["agent_id", "time"]).reset_index(drop=True)
        grp = df.groupby("agent_id", sort=False)
        df["dx"] = grp["x"].diff(); df["dy"] = grp["y"].diff(); df["dt"] = grp["time"].diff()
        with np.errstate(invalid="ignore", divide="ignore"):
            df["speed"] = np.hypot(df["dx"], df["dy"]) / df["dt"]
        df = df[df["time"] >= 90.0]
        mask_q = df["state"] == "queue"
        mask_s = ((df["state"] == "passed") & df["speed"].notna()
                  & (df["speed"] < WAIT_SPEED))
        wait = df[mask_q | mask_s]
        if len(wait) == 0: continue
        H, _, _ = np.histogram2d(wait["x"], wait["y"], bins=(x_edges, y_edges))
        H_total += H
        n_used += 1
    cell = BIN * BIN
    H_density = H_total * 0.5 / cell / max(n_used, 1)
    thr = max(MIN_DENSITY, H_density.max() * THRESHOLD_FRAC)
    mask = H_density > thr
    mask_d = ndimage.binary_dilation(mask, iterations=DILATE_ITERS)
    labels, n_lab = ndimage.label(mask_d, structure=np.ones((3, 3)))
    clusters = []
    for lid in range(1, n_lab + 1):
        idx = np.where((labels == lid) & mask)
        if len(idx[0]) < 4: continue
        xi_min, xi_max = idx[0].min(), idx[0].max()
        yi_min, yi_max = idx[1].min(), idx[1].max()
        xmin = float(x_edges[xi_min]) - BUFFER
        xmax = float(x_edges[xi_max + 1]) + BUFFER
        ymin = float(y_edges[yi_min]) - BUFFER
        ymax = float(y_edges[yi_max + 1]) + BUFFER
        clusters.append({
            "x_range": (xmin, xmax), "y_range": (ymin, ymax),
            "area_m2": (xmax - xmin) * (ymax - ymin),
            "intensity": float(H_density[xi_min:xi_max+1, yi_min:yi_max+1].sum() * cell),
        })
    clusters.sort(key=lambda c: c["intensity"], reverse=True)
    # 이름 부여
    for i, c in enumerate(clusters):
        x_mid = 0.5 * sum(c["x_range"]); y_mid = 0.5 * sum(c["y_range"])
        if x_mid < 13 and 8 <= y_mid <= 17: c["name"] = "W_gate"
        elif x_mid > 20 and y_mid > 18: c["name"] = "W_esc_upper"
        elif x_mid > 20 and y_mid < 8: c["name"] = "W_esc_lower"
        else: c["name"] = f"W_other"
        c["id"] = f"W{i+1}"
    return clusters, n_used


def recount(zones, scenarios):
    rows = []
    for sid, p, cfg, seed, pr, sp, ps in scenarios:
        agent_csv = RAW / f"agents_{sid}.csv"
        traj_csv = RAW / f"trajectory_{sid}.csv"
        if not (agent_csv.exists() and traj_csv.exists()): continue
        a = pd.read_csv(agent_csv)
        served = a.dropna(subset=["service_start_time"])
        if len(served) >= 2:
            t_first = served["service_start_time"].min()
            t_last = served["service_start_time"].max()
            tp_active = len(served) / max(t_last - t_first, 1e-6)
        else:
            tp_active = np.nan
        td = pd.read_csv(traj_csv)
        td = td[td["time"] >= 90.0]
        times = sorted(td["time"].unique())
        row = {
            "scenario_id": sid, "p": p, "config": cfg, "seed": seed,
            "spawned": sp, "passed": ps, "pass_rate": pr,
            "avg_travel_time": a["travel_time"].dropna().mean() if a["travel_time"].notna().any() else np.nan,
            "avg_gate_wait": a["gate_wait_time"].dropna().mean() if a["gate_wait_time"].notna().any() else np.nan,
            "throughput_active": tp_active,
        }
        for z in zones:
            x0, x1 = z["x_range"]; y0, y1 = z["y_range"]
            in_zone = ((td["x"] >= x0) & (td["x"] <= x1) &
                       (td["y"] >= y0) & (td["y"] <= y1))
            sub = td[in_zone]
            counts = sub.groupby("time").size().reindex(times, fill_value=0)
            active = counts[counts > 0]
            row[f"{z['id']}_avg"] = (active.mean() / z["area_m2"]) if len(active) else 0.0
            row[f"{z['id']}_pk"] = counts.max() / z["area_m2"]
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    # 1. summary 로드 (scenarios)
    sm = pd.read_csv(SUMMARY)
    sm["pass_rate"] = sm["passed"] / sm["spawned"].clip(lower=1)
    sm = sm[sm["config"].isin([1,2,3,4,5,6])]
    keep = sm[sm["pass_rate"] >= PASS_RATE_MIN]
    valid_sids = keep["scenario_id"].tolist()
    scenarios = list(zip(sm["scenario_id"], sm["p"], sm["config"].astype(int),
                          sm["seed"], sm["pass_rate"], sm["spawned"], sm["passed"]))
    print(f"전체: {len(sm)}, 유효(pass_rate>={PASS_RATE_MIN}): {len(valid_sids)}")

    # 2. zone 도출
    print("zone 도출 중...")
    zones, n_zone = derive_zones(valid_sids)
    print(f"zone 도출 완료 (n_used={n_zone}):")
    for z in zones:
        print(f"  {z['id']} {z['name']}: x={z['x_range']} y={z['y_range']} "
              f"area={z['area_m2']:.1f}m^2")

    # 3. 밀도 재집계
    print("밀도 재집계 중...")
    df = recount(zones, scenarios)
    df.to_csv(RES / "density_209.csv", index=False, encoding="utf-8-sig")

    # 4. 분석
    df_v = df[df["pass_rate"] >= PASS_RATE_MIN].copy()
    # W2 컬럼 식별
    w2_id = next((z["id"] for z in zones if "esc_upper" in z["name"]), None)
    if w2_id is None:
        # 면적 기준 두번째로 큰 cluster (보통 게이트 다음)
        w2_id = zones[1]["id"] if len(zones) >= 2 else zones[0]["id"]
    print(f"W2 = {w2_id}")

    agg = df_v.groupby(["p", "config"]).agg(
        travel=("avg_travel_time", "mean"),
        gate_wait=("avg_gate_wait", "mean"),
        W2_avg=(f"{w2_id}_avg", "mean"),
        W2_pk=(f"{w2_id}_pk", "mean"),
        n=("seed", "count"),
    ).reset_index()

    out = []
    add = out.append
    add("=" * 100)
    add(f"SERVICE_TIME_MEAN = 2.09s 시나리오 — 최적 cfg 산정")
    add("  (기존 2.7s 시나리오와 비교를 위한 단일 변수 변동)")
    add("=" * 100)
    add(f"\n[데이터]")
    add(f"  150 시나리오 (5p × 6cfg × 5seed) 중 pass_rate≥0.9 → {len(df_v)}건 사용")
    add(f"  W2 zone (에스컬 앞): {next(z for z in zones if z['id']==w2_id)['area_m2']:.1f} m²")

    # 시뮬 결과 표
    add("\n" + "=" * 100)
    add("[표 1] 시뮬 결과 — (p × cfg) 별 측정값")
    add("=" * 100)
    add(f"  {'p':>4} {'cfg':>4} {'n':>3} | {'W2 평균':>7} {'LOS':>4} | "
        f"{'W2 peak':>8} {'LOS':>4} | {'통행시간':>9} | {'게이트 대기':>11}")
    add(f"  {'-'*4} {'-'*4} {'-'*3} | {'-'*7} {'-'*4} | {'-'*8} {'-'*4} | "
        f"{'-'*9} | {'-'*11}")
    for _, r in agg.iterrows():
        add(f"  {r['p']:>4.1f} {int(r['config']):>4d} {int(r['n']):>3d} | "
            f"{r['W2_avg']:>6.3f}  {los(r['W2_avg']):>3} | "
            f"{r['W2_pk']:>7.3f}  {los(r['W2_pk']):>3} | "
            f"{r['travel']:>7.1f}s | {r['gate_wait']:>9.1f}s")

    # G vs S
    add("\n" + "=" * 100)
    add("[표 2] G 최적화 cfg vs S 최적화 cfg — 각각의 LOS")
    add("=" * 100)
    add("")
    add("내용: G = 게이트 대기 최소 cfg, S = 통행시간 최소 cfg.")
    add("       OK = LOS E (W2 peak ≤ 1.0) 통과. X = LOS F 위반.")
    add("")
    add(f"  {'p':>4} | {'G cfg':>5} | {'gate_wait':>9} | {'travel':>7} | "
        f"{'W2 peak':>8} {'LOS':>4} {'OK?':>3} | "
        f"{'S cfg':>5} | {'gate_wait':>9} | {'travel':>7} | "
        f"{'W2 peak':>8} {'LOS':>4} {'OK?':>3}")
    add(f"  {'-'*4} | {'-'*5} | {'-'*9} | {'-'*7} | {'-'*8} {'-'*4} {'-'*3} | "
        f"{'-'*5} | {'-'*9} | {'-'*7} | {'-'*8} {'-'*4} {'-'*3}")
    rows = []
    p_list = sorted(agg["p"].unique())
    for p_val in p_list:
        sub = agg[agg["p"] == p_val]
        rg = sub.loc[sub["gate_wait"].idxmin()]
        rs = sub.loc[sub["travel"].idxmin()]
        g_ok = "O" if rg["W2_pk"] <= LOS_E_MAX else "X"
        s_ok = "O" if rs["W2_pk"] <= LOS_E_MAX else "X"
        add(f"  {p_val:>4.1f} | cfg{int(rg['config']):>2d} | "
            f"{rg['gate_wait']:>7.1f}s | {rg['travel']:>5.1f}s | "
            f"{rg['W2_pk']:>7.3f}  {los(rg['W2_pk']):>3}   {g_ok:>3} | "
            f"cfg{int(rs['config']):>2d} | "
            f"{rs['gate_wait']:>7.1f}s | {rs['travel']:>5.1f}s | "
            f"{rs['W2_pk']:>7.3f}  {los(rs['W2_pk']):>3}   {s_ok:>3}")
        rows.append({
            "p": p_val,
            "G_cfg": int(rg["config"]), "G_gw": rg["gate_wait"], "G_tr": rg["travel"], "G_W2pk": rg["W2_pk"], "G_ok": rg["W2_pk"] <= LOS_E_MAX,
            "S_cfg": int(rs["config"]), "S_gw": rs["gate_wait"], "S_tr": rs["travel"], "S_W2pk": rs["W2_pk"], "S_ok": rs["W2_pk"] <= LOS_E_MAX,
        })

    # 채택 결정 + 최종 권고
    add("\n" + "=" * 100)
    add("[표 3] 채택 결정 + 최종 cfg")
    add("=" * 100)
    add("")
    add("규칙: G/S 같으면 그 cfg / G≠S 면 S 채택 / 둘 다 LOS 위반이면 LOS 통과 cfg 중 travel 최저")
    add("")
    add(f"  {'p':>4} | {'채택 cfg':>9} | {'gate_wait':>9} | {'travel':>7} | "
        f"{'W2 peak':>8} {'LOS':>4} | 사유")
    add(f"  {'-'*4} | {'-'*9} | {'-'*9} | {'-'*7} | {'-'*8} {'-'*4} | {'-'*40}")
    for r in rows:
        p_val = r["p"]
        g_eq_s = (r["G_cfg"] == r["S_cfg"])
        if g_eq_s and r["S_ok"]:
            chosen = r["S_cfg"]; saw = "G=S, LOS 통과"
        elif g_eq_s and not r["S_ok"]:
            sub = agg[(agg["p"] == p_val) & (agg["W2_pk"] <= LOS_E_MAX)]
            if len(sub) == 0: chosen = None; saw = "G/S LOS 위반, 대체 후보 없음"
            else:
                alt = sub.loc[sub["travel"].idxmin()]
                chosen = int(alt["config"])
                saw = f"G/S(cfg{r['G_cfg']}) LOS F → cfg{chosen}"
        else:
            if r["S_ok"]:
                chosen = r["S_cfg"]
                saw = f"G(cfg{r['G_cfg']}) LOS 위반, S 채택"
            else:
                sub = agg[(agg["p"] == p_val) & (agg["W2_pk"] <= LOS_E_MAX)]
                if len(sub) == 0: chosen = None; saw = "G/S 모두 위반, 대체 없음"
                else:
                    alt = sub.loc[sub["travel"].idxmin()]
                    chosen = int(alt["config"])
                    saw = f"G/S 모두 위반 → cfg{chosen}"
        if chosen is None:
            add(f"  {p_val:>4.1f} | {'없음':>9s} | {'-':>9s} | {'-':>7s} | "
                f"{'-':>8s} {'-':>4} | 운영 불가")
        else:
            r2 = agg[(agg["p"] == p_val) & (agg["config"] == chosen)].iloc[0]
            add(f"  {p_val:>4.1f} | {'cfg'+str(chosen):>9s} | "
                f"{r2['gate_wait']:>7.1f}s | {r2['travel']:>5.1f}s | "
                f"{r2['W2_pk']:>7.3f}  {los(r2['W2_pk']):>3} | {saw}")

    text = "\n".join(out)
    print(text)
    OUT.write_text(text, encoding="utf-8")
    print(f"\n저장: {OUT}")

    # zone 정보 저장
    with open(RES / "zones_209.json", "w", encoding="utf-8") as f:
        json.dump([{"id": z["id"], "name": z["name"],
                    "x_range": list(z["x_range"]), "y_range": list(z["y_range"]),
                    "area_m2": z["area_m2"]} for z in zones],
                  f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
