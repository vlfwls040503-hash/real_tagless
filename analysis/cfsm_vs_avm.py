"""CFSM vs AVM 궤적 비교 분석."""
import pathlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = pathlib.Path(r"C:\Users\aaron\tagless")
FIG = ROOT / "output" / "cfsm_vs_avm_figures"
FIG.mkdir(parents=True, exist_ok=True)


def load(path):
    df = pd.read_csv(path)
    df = df.sort_values(["agent_id", "time"]).reset_index(drop=True)
    df["dx"] = df.groupby("agent_id").x.diff()
    df["dy"] = df.groupby("agent_id").y.diff()
    df["dt"] = df.groupby("agent_id").time.diff()
    df["v"] = np.sqrt(df.dx**2 + df.dy**2) / df.dt
    df["vx"] = df.dx / df.dt
    df["vy"] = df.dy / df.dt
    return df


def main():
    cfsm = load(ROOT / "output" / "trajectories_escalator.csv")
    avm = load(ROOT / "output" / "trajectories_avm_demo.csv")
    print(f"CFSM rows: {len(cfsm)}, agents: {cfsm.agent_id.nunique()}")
    print(f"AVM  rows: {len(avm)},  agents: {avm.agent_id.nunique()}")

    # ------------------------------------------------
    # 1. x별 평균 속도 프로파일 (게이트 통과 후)
    # ------------------------------------------------
    def profile(df, label):
        post = df[(df.state == "passed") & df.v.notna() &
                  (df.v > 0.01) & (df.x > 13.5) & (df.x < 35)]
        post = post.copy()
        post["x_bin"] = (post.x * 2).astype(int) / 2
        return post.groupby("x_bin").v.agg(["mean", "std", "count"]).reset_index()

    p_c = profile(cfsm, "CFSM")
    p_a = profile(avm, "AVM")

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(p_c.x_bin, p_c["mean"], "-o", color="#1976D2", linewidth=2,
            markersize=4, label="CFSM V2", alpha=0.9)
    ax.plot(p_a.x_bin, p_a["mean"], "-s", color="#C2185B", linewidth=2,
            markersize=4, label="AVM", alpha=0.9)
    ax.axvline(23, linestyle=":", color="gray", alpha=0.5)
    ax.axvline(25, linestyle=":", color="gray", alpha=0.5)
    ax.axvspan(23, 25, alpha=0.08, color="blue")
    ax.text(24, ax.get_ylim()[1] * 0.92, "corridor 입구", ha="center",
            fontsize=9, color="gray")
    ax.set_xlabel("x 좌표 (m)")
    ax.set_ylabel("평균 속도 (m/s)")
    ax.set_title("게이트 이후 x별 속도 프로파일 — CFSM vs AVM")
    ax.legend()
    ax.grid(True, alpha=0.3, linestyle=":")
    plt.tight_layout()
    fig.savefig(FIG / "velocity_profile.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    print("Saved velocity_profile.png")

    # ------------------------------------------------
    # 2. 정지 시간 분포 (v < 0.2 m/s 누적 시간 per agent)
    # ------------------------------------------------
    def stop_time_per_agent(df, dt=0.1):
        slow = df[(df.v.notna()) & (df.v < 0.2)]
        return slow.groupby("agent_id").size() * dt

    stop_c = stop_time_per_agent(cfsm)
    stop_a = stop_time_per_agent(avm)

    fig, ax = plt.subplots(figsize=(9, 5))
    bins = np.linspace(0, 30, 31)
    ax.hist(stop_c, bins=bins, alpha=0.6, color="#1976D2",
            label=f"CFSM (N={len(stop_c)}, mean={stop_c.mean():.1f}s)")
    ax.hist(stop_a, bins=bins, alpha=0.6, color="#C2185B",
            label=f"AVM (N={len(stop_a)}, mean={stop_a.mean():.1f}s)")
    ax.set_xlabel("정지 시간 (v<0.2 m/s 누적, 초)")
    ax.set_ylabel("agent 수")
    ax.set_title("agent별 정지 시간 분포")
    ax.legend()
    ax.grid(True, alpha=0.3, linestyle=":")
    plt.tight_layout()
    fig.savefig(FIG / "stop_time_dist.png", dpi=110)
    plt.close(fig)
    print("Saved stop_time_dist.png")

    # ------------------------------------------------
    # 3. y방향 이동량 (횡단 거리) per agent
    # ------------------------------------------------
    def y_travel(df):
        # agent별 y 좌표 변동 (std * 2 ≈ 횡단 범위)
        return df.groupby("agent_id").y.apply(lambda s: s.max() - s.min())

    y_c = y_travel(cfsm)
    y_a = y_travel(avm)

    fig, ax = plt.subplots(figsize=(9, 5))
    bins = np.linspace(0, 25, 26)
    ax.hist(y_c, bins=bins, alpha=0.6, color="#1976D2",
            label=f"CFSM (mean={y_c.mean():.1f}m)")
    ax.hist(y_a, bins=bins, alpha=0.6, color="#C2185B",
            label=f"AVM (mean={y_a.mean():.1f}m)")
    ax.set_xlabel("agent별 y range (max - min, m)")
    ax.set_ylabel("agent 수")
    ax.set_title("횡단 이동 범위 — 큰 값일수록 경로 꼬임")
    ax.legend()
    ax.grid(True, alpha=0.3, linestyle=":")
    plt.tight_layout()
    fig.savefig(FIG / "y_range_dist.png", dpi=110)
    plt.close(fig)
    print("Saved y_range_dist.png")

    # ------------------------------------------------
    # 4. 에스컬 앞 (x=20~28) 밀집 패턴 (시간 평균 density heatmap)
    # ------------------------------------------------
    def zone_density_grid(df, x_rng=(20, 28), y_rng=(-1, 26), dx=0.5, dy=0.5):
        sub = df[(df.x >= x_rng[0]) & (df.x <= x_rng[1]) &
                 (df.y >= y_rng[0]) & (df.y <= y_rng[1])]
        xbins = np.arange(x_rng[0], x_rng[1] + dx, dx)
        ybins = np.arange(y_rng[0], y_rng[1] + dy, dy)
        H, _, _ = np.histogram2d(sub.x, sub.y, bins=[xbins, ybins])
        # 시간 평균으로 정규화
        t_span = df.time.max() - df.time.min()
        H = H / (t_span * dx * dy) * 0.1  # sampling interval 0.1s
        return H, xbins, ybins

    H_c, xb, yb = zone_density_grid(cfsm)
    H_a, _, _ = zone_density_grid(avm)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    vmax = max(H_c.max(), H_a.max())
    for ax, H, title in [(axes[0], H_c, "CFSM"), (axes[1], H_a, "AVM")]:
        im = ax.imshow(H.T, origin="lower", aspect="auto",
                       extent=[xb[0], xb[-1], yb[0], yb[-1]],
                       cmap="YlOrRd", vmin=0, vmax=vmax)
        # corridor 경계 선
        ax.axhline(0, color="black", linewidth=1, linestyle="--", alpha=0.5)
        ax.axhline(25, color="black", linewidth=1, linestyle="--", alpha=0.5)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_title(f"{title} — 에스컬 앞 밀집 패턴")
        plt.colorbar(im, ax=ax, label="시간평균 밀도 (명/㎡)")
    plt.tight_layout()
    fig.savefig(FIG / "density_heatmap.png", dpi=110)
    plt.close(fig)
    print("Saved density_heatmap.png")

    # ------------------------------------------------
    # 5. 에스컬 capture 도착 시간 분포 (sink)
    # ------------------------------------------------
    def last_time_per_agent(df):
        return df.groupby("agent_id").time.max()

    lt_c = last_time_per_agent(cfsm)
    lt_a = last_time_per_agent(avm)

    # agent별 통행시간 = last - first
    def travel_per_agent(df):
        g = df.groupby("agent_id").time.agg(["min", "max"])
        return g["max"] - g["min"]

    tt_c = travel_per_agent(cfsm)
    tt_a = travel_per_agent(avm)

    fig, ax = plt.subplots(figsize=(9, 5))
    bins = np.linspace(0, 80, 41)
    ax.hist(tt_c, bins=bins, alpha=0.6, color="#1976D2",
            label=f"CFSM (mean={tt_c.mean():.1f}s, p95={tt_c.quantile(0.95):.1f})")
    ax.hist(tt_a, bins=bins, alpha=0.6, color="#C2185B",
            label=f"AVM (mean={tt_a.mean():.1f}s, p95={tt_a.quantile(0.95):.1f})")
    ax.set_xlabel("agent 총 체류 시간 (초)")
    ax.set_ylabel("agent 수")
    ax.set_title("agent별 체류 시간 분포 (trajectory 기준)")
    ax.legend()
    ax.grid(True, alpha=0.3, linestyle=":")
    plt.tight_layout()
    fig.savefig(FIG / "travel_time_dist.png", dpi=110)
    plt.close(fig)
    print("Saved travel_time_dist.png")

    # ------------------------------------------------
    # 6. 요약 통계
    # ------------------------------------------------
    print("\n=== 요약 비교 ===")

    def sum_stats(label, df, tt, st, yr):
        free = df[(df.v.notna()) & (df.v > 0.01) &
                  (df.state == "moving") & (df.x < 10)]
        return {
            "label": label,
            "agents": df.agent_id.nunique(),
            "free_walk_mean_v": free.v.mean(),
            "free_walk_std_v": free.v.std(),
            "travel_time_mean": tt.mean(),
            "travel_time_p95": tt.quantile(0.95),
            "stop_time_mean": st.mean(),
            "y_range_mean": yr.mean(),
            "y_range_p95": yr.quantile(0.95),
        }

    s_c = sum_stats("CFSM", cfsm, tt_c, stop_c, y_c)
    s_a = sum_stats("AVM", avm, tt_a, stop_a, y_a)

    print(f"{'지표':25s} {'CFSM':>10s} {'AVM':>10s} {'Δ (AVM-CFSM)':>15s}")
    for k in ["agents", "free_walk_mean_v", "free_walk_std_v",
              "travel_time_mean", "travel_time_p95",
              "stop_time_mean", "y_range_mean", "y_range_p95"]:
        v_c = s_c[k]; v_a = s_a[k]
        if isinstance(v_c, (int, float)) and not np.isnan(v_c):
            print(f"{k:25s} {v_c:>10.3f} {v_a:>10.3f} {v_a-v_c:>+15.3f}")

    return s_c, s_a


if __name__ == "__main__":
    main()
