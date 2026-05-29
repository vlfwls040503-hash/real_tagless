"""Render AVM vs CFSM V2 side-by-side MP4 for Jülich 4D090 setup.

Uses:
  AVM:  data/julich/calibration_runs/validate_traj_A3.0_B0.3_C0.05.csv (seed 100)
  CFSM: data/julich/simulated_4D090_cfsm.csv (seed 42)
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import imageio_ffmpeg
import matplotlib as mpl
mpl.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
from matplotlib.animation import FFMpegWriter

ROOT = Path(__file__).resolve().parent.parent
AVM_CSV = ROOT / "data" / "julich" / "calibration_runs" / "validate_traj_A3.0_B0.3_C0.05.csv"
CFSM_CSV = ROOT / "data" / "julich" / "simulated_4D090_cfsm.csv"
OUT_MP4 = ROOT / "output" / "julich_AVM_vs_CFSM.mp4"
OUT_MP4.parent.mkdir(exist_ok=True)

# low-res per CLAUDE.md rule
plt.rcParams["figure.dpi"] = 80
plt.rcParams["savefig.dpi"] = 80

DURATION = 40.0  # both sims cover this
FPS_OUT = 12      # 12 fps playback, subsample every 2 frames from 25 fps source


def load_seed(csv: Path, seed: int) -> pd.DataFrame:
    df = pd.read_csv(csv)
    return df[df["seed"] == seed].reset_index(drop=True)


def draw_bottleneck(ax, title: str) -> None:
    # holding semicircle (3.3m radius)
    theta = np.linspace(np.pi / 2, 3 * np.pi / 2, 40)
    ax.plot(3.3 * np.cos(theta), 3.3 * np.sin(theta), "k-", lw=1)
    # bottleneck walls
    ax.plot([0, 0.2], [0.5, 0.5], "k-", lw=2)
    ax.plot([0, 0.2], [-0.5, -0.5], "k-", lw=2)
    ax.plot([0, 0], [0.5, 3.3], "k-", lw=1)
    ax.plot([0, 0], [-0.5, -3.3], "k-", lw=1)
    # post region walls
    ax.plot([0.2, 3.2], [2.0, 2.0], "k-", lw=1)
    ax.plot([0.2, 3.2], [-2.0, -2.0], "k-", lw=1)
    ax.plot([0.2, 0.2], [0.5, 2.0], "k-", lw=2)
    ax.plot([0.2, 0.2], [-0.5, -2.0], "k-", lw=2)
    ax.set_xlim(-3.6, 3.6)
    ax.set_ylim(-3.6, 3.6)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(title)
    ax.grid(alpha=0.2)


def main() -> None:
    print("Loading...")
    avm = load_seed(AVM_CSV, seed=100)
    cfsm = load_seed(CFSM_CSV, seed=42)
    print(f"  AVM rows: {len(avm):,}, CFSM rows: {len(cfsm):,}")

    # Frame snapshots at fixed time grid
    times = np.arange(0.04, DURATION + 1e-6, 0.08)  # every 2nd frame -> 12.5 fps source
    print(f"  {len(times)} frames")

    fig, axes = plt.subplots(1, 2, figsize=(9, 4.5))
    draw_bottleneck(axes[0], "AVM (calibrated A=3.0 B=0.3 C=0.05)")
    draw_bottleneck(axes[1], "CFSM V2 (project default)")
    sc_avm = axes[0].scatter([], [], s=20, c="crimson", edgecolors="black", linewidths=0.3)
    sc_cfsm = axes[1].scatter([], [], s=20, c="navy", edgecolors="black", linewidths=0.3)
    time_text = fig.suptitle("t = 0.00 s", fontsize=11)

    writer = FFMpegWriter(fps=FPS_OUT, bitrate=1500, codec="libx264")
    print(f"Rendering -> {OUT_MP4}")
    with writer.saving(fig, str(OUT_MP4), dpi=80):
        for i, t in enumerate(times):
            t_lo, t_hi = t - 0.02, t + 0.02
            a = avm[(avm["time"] > t_lo) & (avm["time"] < t_hi)]
            c = cfsm[(cfsm["time"] > t_lo) & (cfsm["time"] < t_hi)]
            sc_avm.set_offsets(a[["x", "y"]].values if len(a) else np.empty((0, 2)))
            sc_cfsm.set_offsets(c[["x", "y"]].values if len(c) else np.empty((0, 2)))
            time_text.set_text(f"t = {t:5.2f} s   |   AVM n={len(a)}   CFSM n={len(c)}")
            writer.grab_frame()
            if i % 100 == 0:
                print(f"  frame {i}/{len(times)}")
    plt.close(fig)
    print(f"Done. Output: {OUT_MP4}")


if __name__ == "__main__":
    main()
