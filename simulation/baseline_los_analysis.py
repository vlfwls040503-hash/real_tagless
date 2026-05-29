"""LOS analysis for p=0 baseline vs existing v3 scenarios.

Outputs:
  - results_baseline/los_comparison.csv
  - figures/los_comparison.png
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
BASELINE_JSON = ROOT / "results_baseline" / "p0_summary.json"
V3_SUMMARY = ROOT / "results_v3" / "summary.csv"
OUT_CSV = ROOT / "results_baseline" / "los_comparison.csv"
FIG = ROOT / "figures" / "los_comparison.png"
FIG.parent.mkdir(parents=True, exist_ok=True)

# Fruin LOS thresholds (ped/m^2)
LOS = [("A", 0.31), ("B", 0.43), ("C", 0.72), ("D", 1.08), ("E", 2.17), ("F", float("inf"))]
LOS_D_LIMIT = 1.08   # 대합실/대기공간 최소
LOS_E_LIMIT = 2.17   # 환승통로 최소

# Zone classification per 국토부 고시 2025-241호
ZONE_CATEGORY = {
    "z1": ("대합실", "D"),        # concourse overall (50x25=1250 m^2)
    "z2": ("대기공간", "D"),       # gate cluster (4x7=28 m^2)
    "z3a": ("환승통로", "E"),      # upper escalator region (8x3=24 m^2)
    "z3b": ("대기공간", "D"),      # upper escalator waiting (2x3=6 m^2)
    "z3c": ("환승통로", "E"),      # upper escalator far (10x3=30 m^2)
    "z4a": ("환승통로", "E"),      # lower escalator region
    "z4b": ("대기공간", "D"),      # lower escalator waiting (2x3=6 m^2)
    "z4c": ("환승통로", "E"),      # lower escalator far
}

ZONES = ["z3a", "z3b", "z3c", "z4a", "z4b", "z4c"]  # user-spec figure zones
ZONE_LABELS = ["3A", "3B", "3C", "4A", "4B", "4C"]


def density_to_los(d: float) -> str:
    for grade, upper in LOS:
        if d < upper:
            return grade
    return "F"


def meets_standard(zone: str, density: float) -> tuple[bool, str]:
    """국토부 고시 기준 초과 여부."""
    _, req_grade = ZONE_CATEGORY.get(zone, ("환승통로", "E"))
    limit = LOS_D_LIMIT if req_grade == "D" else LOS_E_LIMIT
    return density < limit, req_grade


def main() -> None:
    # Load baseline
    with open(BASELINE_JSON) as f:
        baseline = json.load(f)
    bl_agg = baseline["aggregated"]

    # Build baseline summary row
    baseline_row = {
        "scenario": "p=0 (baseline)",
        "p": 0.0, "config": None,
    }
    for z in ZONES:
        baseline_row[f"{z}_max"] = bl_agg[f"{z}_max"]["mean"]
        baseline_row[f"{z}_max_std"] = bl_agg[f"{z}_max"]["std"]
        baseline_row[f"{z}_los"] = density_to_los(bl_agg[f"{z}_max"]["mean"])
        ok, req = meets_standard(z, bl_agg[f"{z}_max"]["mean"])
        baseline_row[f"{z}_req"] = req
        baseline_row[f"{z}_pass"] = ok

    print("=== p=0 Baseline (5 seeds mean) ===")
    for z, lbl in zip(ZONES, ZONE_LABELS):
        d = baseline_row[f"{z}_max"]
        std = baseline_row[f"{z}_max_std"]
        los = baseline_row[f"{z}_los"]
        req = baseline_row[f"{z}_req"]
        ok = baseline_row[f"{z}_pass"]
        status = "PASS" if ok else "FAIL"
        print(f"  Zone {lbl}: max={d:.3f}±{std:.3f} ped/m^2 -> LOS {los}  "
              f"(requires {req}, {status})")

    # Load v3 results (column names: zone3a_max_density, ...)
    df_v3 = pd.read_csv(V3_SUMMARY)
    v3_col = {z: f"zone{z[1:]}_max_density" for z in ZONES}  # z3a -> zone3a_max_density
    df_v3_agg = df_v3.groupby(["p", "config"]).agg(
        **{f"{z}_max": (v3_col[z], "mean") for z in ZONES}
    ).reset_index()

    # Representative scenarios per user spec
    reps = [
        ("p=0", 0.0, None, baseline_row),
        ("p=0.3 cfg2", 0.3, 2, None),
        ("p=0.5 cfg3", 0.5, 3, None),
        ("p=0.8 cfg4", 0.8, 4, None),
    ]

    def _get_row(p, cfg):
        if cfg is None:
            return None
        sel = df_v3_agg[(df_v3_agg["p"] == p) & (df_v3_agg["config"] == cfg)]
        if sel.empty:
            return None
        return sel.iloc[0]

    # Build comparison table
    rows_out = [baseline_row]
    for label, p, cfg, precomputed in reps[1:]:
        r = _get_row(p, cfg)
        if r is None:
            continue
        row = {"scenario": label, "p": p, "config": cfg}
        for z in ZONES:
            d = float(r[f"{z}_max"])
            row[f"{z}_max"] = d
            row[f"{z}_max_std"] = 0.0
            row[f"{z}_los"] = density_to_los(d)
            ok, req = meets_standard(z, d)
            row[f"{z}_req"] = req
            row[f"{z}_pass"] = ok
        rows_out.append(row)

    df_out = pd.DataFrame(rows_out)
    df_out.to_csv(OUT_CSV, index=False, float_format="%.4f")
    print(f"\nWrote {OUT_CSV}")

    # Print comparison table
    print("\n=== Zone max density comparison ===")
    header = f"{'scenario':<15}" + "".join(f"{lbl:>7}" for lbl in ZONE_LABELS)
    print(header)
    for r in rows_out:
        line = f"{r['scenario']:<15}"
        for z in ZONES:
            d = r[f"{z}_max"]
            los = r[f"{z}_los"]
            line += f"{d:>5.2f}{los}"
        print(line)

    # LOS grade change vs baseline
    print("\n=== LOS grade change vs p=0 baseline ===")
    bl = rows_out[0]
    for r in rows_out[1:]:
        print(f"  {r['scenario']}:")
        for z, lbl in zip(ZONES, ZONE_LABELS):
            bl_los = bl[f"{z}_los"]
            new_los = r[f"{z}_los"]
            if bl_los == new_los:
                arrow = "→"
            else:
                arrow = "↓" if "ABCDEF".index(new_los) > "ABCDEF".index(bl_los) else "↑"
            print(f"    Zone {lbl}: {bl_los} {arrow} {new_los}")

    # Plot
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=100)
    x = np.arange(len(ZONES))
    width = 0.2
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
    for i, r in enumerate(rows_out):
        vals = [r[f"{z}_max"] for z in ZONES]
        stds = [r.get(f"{z}_max_std", 0.0) for z in ZONES]
        ax.bar(x + (i - 1.5) * width, vals, width, label=r["scenario"],
               yerr=stds if r["scenario"].startswith("p=0 (") else None,
               color=colors[i], alpha=0.85, capsize=3)

    ax.axhline(LOS_D_LIMIT, color="green", linestyle="--", lw=1.5,
               label=f"LOS D limit ({LOS_D_LIMIT})")
    ax.axhline(LOS_E_LIMIT, color="red", linestyle="--", lw=1.5,
               label=f"LOS E limit ({LOS_E_LIMIT})")

    ax.set_xticks(x)
    ax.set_xticklabels(ZONE_LABELS)
    ax.set_xlabel("Zone")
    ax.set_ylabel("Max density (ped/m²)")
    ax.set_title("Zone-wise max density by scenario (Fruin LOS)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG, dpi=100)
    print(f"\nWrote {FIG}")


if __name__ == "__main__":
    main()
