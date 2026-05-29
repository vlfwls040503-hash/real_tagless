"""
밀도-속도 기본다이어그램 (Fundamental Diagram) 추출
- 호모그래피로 트랙 픽셀 → 미터 변환
- 게이트 앞 1m × 2m ROI에서 frame별 밀도/속도 측정
- Weidmann 1993 오버레이 + RMSE
"""
import os, sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

DATA_DIR = r"C:\Users\aaron\tagless\영상데이터"
OUT_FIG = r"C:\Users\aaron\tagless\figures\empirical_fundamental_diagram.png"
OUT_CSV = r"C:\Users\aaron\tagless\data\empirical_density_speed.csv"
OUT_MD = r"C:\Users\aaron\tagless\analysis\calibration_density_speed.md"

# ─── 1. 데이터 + 호모그래피 ───
H = np.load(os.path.join(DATA_DIR, "homography.npy"))
df = pd.read_csv(os.path.join(DATA_DIR, "tracks_full.csv"))
print(f"loaded: {len(df)} rows, {df.id.nunique()} ids")

# 발끝(cx, y2) → 미터 좌표
xy_px = df[["cx", "y2"]].values
n = len(xy_px)
hom = np.hstack([xy_px, np.ones((n, 1))])
proj = (H @ hom.T).T
df["mx"] = proj[:, 0] / proj[:, 2]
df["my"] = proj[:, 1] / proj[:, 2]
print(f"meter range: x [{df.mx.min():.2f}, {df.mx.max():.2f}], y [{df.my.min():.2f}, {df.my.max():.2f}]")

# ─── 2. ROI: 게이트 앞 1m × 2m ───
# 게이트 진입선(블러 y=250)이 미터 y≈1.03. ROI는 게이트 진입선에서 카메라 쪽 1m, 가로 2m.
ROI_X = (1.50, 3.50)   # 가로 2.0 m (게이트 영역 가운데)
ROI_Y = (0.00, 1.00)   # 세로 1.0 m (진입선~카메라 쪽)
ROI_AREA = (ROI_X[1] - ROI_X[0]) * (ROI_Y[1] - ROI_Y[0])
print(f"ROI: x∈{ROI_X} m, y∈{ROI_Y} m, 면적 {ROI_AREA:.2f} m²")

# ─── 3. frame-to-frame 보행자별 속도 ───
df = df.sort_values(["id", "frame"]).reset_index(drop=True)
df["dx"] = df.groupby("id")["mx"].diff()
df["dy"] = df.groupby("id")["my"].diff()
df["dt"] = df.groupby("id")["t_sec"].diff()
df["v_inst"] = np.hypot(df.dx, df.dy) / df.dt.replace(0, np.nan)

# ROI 안 행
in_roi = ((df.mx >= ROI_X[0]) & (df.mx <= ROI_X[1]) &
          (df.my >= ROI_Y[0]) & (df.my <= ROI_Y[1]))
df_in = df[in_roi].copy()
print(f"ROI 안 검출: {len(df_in)} 행 ({df_in.id.nunique()} unique IDs)")

# 트래킹 점프 outlier 필터 (보행자 물리적 한계 v < 3 m/s)
V_MAX = 3.0
n_before = len(df_in)
df_in = df_in[(df_in.v_inst.isna()) | (df_in.v_inst <= V_MAX)]
print(f"속도 outlier 필터(v ≤ {V_MAX} m/s): {n_before} → {len(df_in)} 행")

# ─── 4. frame별 밀도/속도 ───
fd = df_in.groupby("frame").agg(
    t_sec=("t_sec", "first"),
    n_agents=("id", "nunique"),
    v_mps=("v_inst", "mean"),
).reset_index()
fd["rho"] = fd.n_agents / ROI_AREA
fd_full = fd.copy()
fd = fd.dropna(subset=["v_mps"])
fd = fd[fd.v_mps > 0]   # 속도 0인 frame은 1프레임만 잡힌 ID라 dt=NaN
print(f"FD 시점 수: {len(fd)} (전체 frame 중 ROI에 사람 있고 속도 측정 가능한)")
print(f"밀도 범위: [{fd.rho.min():.2f}, {fd.rho.max():.2f}] ped/m²")
print(f"속도 범위: [{fd.v_mps.min():.2f}, {fd.v_mps.max():.2f}] m/s")
print(f"평균 밀도/속도: {fd.rho.mean():.3f} ped/m², {fd.v_mps.mean():.3f} m/s")

# ─── 5. Weidmann 1993 ───
def weidmann(rho, v0=1.34):
    rho = np.asarray(rho, dtype=float)
    out = v0 * (1 - np.exp(-1.913 * (1.0/rho - 1.0/5.4)))
    return np.clip(out, 0, v0)

v_w_pred = weidmann(fd.rho.values)
rmse = float(np.sqrt(np.mean((fd.v_mps.values - v_w_pred)**2)))
mae = float(np.mean(np.abs(fd.v_mps.values - v_w_pred)))
print(f"Weidmann RMSE = {rmse:.3f} m/s, MAE = {mae:.3f} m/s")

# ─── 6. 산점도 + Weidmann 곡선 ───
os.makedirs(os.path.dirname(OUT_FIG), exist_ok=True)
fig, ax = plt.subplots(figsize=(8, 5), dpi=120)

# 약간의 jitter 추가 (산점도 가독성)
jitter = (np.random.default_rng(0).uniform(-0.06, 0.06, len(fd)))
ax.scatter(fd.rho + jitter, fd.v_mps, s=8, alpha=0.18, color="#3D6FA8",
           edgecolors="none", label=f"영상 측정 raw (n={len(fd)})")

# bin 평균 ± std
bin_stats = []
for rho_val in sorted(fd.rho.unique()):
    sub = fd[fd.rho == rho_val]
    bin_stats.append((rho_val, len(sub), sub.v_mps.mean(),
                      sub.v_mps.std(), sub.v_mps.median()))
bs = pd.DataFrame(bin_stats, columns=["rho","n","mean","std","median"])
ax.errorbar(bs["rho"], bs["mean"], yerr=bs["std"], fmt="o",
            color="#1F3A5F", markersize=8, capsize=4, capthick=1.5,
            elinewidth=1.5, label="영상 측정 평균±σ", zorder=5)

# Weidmann 1993
rho_curve = np.linspace(0.05, 5.5, 200)
ax.plot(rho_curve, weidmann(rho_curve), color="#C44536", lw=2.2,
        label="Weidmann 1993  (v0=1.34 m/s)")

ax.set_xlabel("밀도 ρ (ped/m²)", fontsize=11)
ax.set_ylabel("속도 v (m/s)", fontsize=11)
ax.set_title(f"밀도-속도 기본다이어그램 (ROI {ROI_AREA:.1f} m², n={len(fd)} 시점, "
             f"Weidmann RMSE={rmse:.3f} m/s)",
             fontsize=10.5)
ax.legend(loc="upper right", fontsize=9)
ax.grid(alpha=0.3, linestyle="--", linewidth=0.5)
ax.set_xlim(0, max(5.5, fd.rho.max() + 0.3))
ax.set_ylim(0, 1.7)
fig.tight_layout()
fig.savefig(OUT_FIG, dpi=120)
plt.close(fig)
print(f"saved: {OUT_FIG}")
print("\nbin 통계:")
print(bs.to_string(index=False))

# ─── 7. CSV 저장 ───
os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
fd_save = fd[["t_sec", "rho", "v_mps", "n_agents"]].copy()
fd_save.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"saved: {OUT_CSV}")

# ─── 8. Markdown 보고서 ───
os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)

# 밀도별 영상 vs Weidmann 비교
table = []
for rho_q in [0.5, 1.0, 1.5, 2.0]:
    sub = fd[(fd.rho >= rho_q - 0.25) & (fd.rho <= rho_q + 0.25)]
    if len(sub) >= 3:
        v_obs = float(sub.v_mps.mean())
        v_obs_std = float(sub.v_mps.std())
        v_w = float(weidmann(rho_q))
        table.append((rho_q, len(sub), v_obs, v_obs_std, v_w, v_obs - v_w))
    else:
        table.append((rho_q, len(sub), None, None, float(weidmann(rho_q)), None))

# 자유흐름 비율
n_free = int((fd.rho < 0.5).sum())
n_med  = int(((fd.rho >= 0.5) & (fd.rho < 1.5)).sum())
n_high = int((fd.rho >= 1.5).sum())
n_vh   = int((fd.rho > 2.5).sum())

# 호모그래피 정보
H_label = ("점자블록 매트릭스 0.9×0.6m 기반 (사용자 확인) → 박스 외곽 1.8×1.2m 자동 산출. "
           "perspective 항 g≈0, h≈0 으로 사실상 affine 변환 (영역 작아 사선 효과 추정 약함)")

md = []
md.append(f"# 밀도-속도 기본다이어그램 측정 결과")
md.append("")
md.append(f"- 작성일: 2026-05-09")
md.append(f"- 입력: `영상데이터/tracks_full.csv` ({len(df)} 행, {df.id.nunique()} unique IDs), `homography.npy`")
md.append(f"- 영상: GX010193_blurred.MP4 (14분 28초, 720×404)")
md.append("")

md.append("## 측정 영역 (ROI)")
md.append(f"- 미터 좌표: x ∈ [{ROI_X[0]:.2f}, {ROI_X[1]:.2f}] m, y ∈ [{ROI_Y[0]:.2f}, {ROI_Y[1]:.2f}] m")
md.append(f"- 면적: **{ROI_AREA:.2f} m²** (게이트 진입선에서 카메라 쪽 1 m × 가로 2 m)")
md.append(f"- 호모그래피: {H_label}")
md.append("")

md.append("## 측정 결과")
md.append(f"- 시점 수 (속도 측정 가능 frame): **n = {len(fd)}**")
md.append(f"- 측정 시간 분해능: **frame 단위 ≈ 33 ms** (29.97 fps)")
md.append(f"- 밀도 범위: [{fd.rho.min():.2f}, {fd.rho.max():.2f}] ped/m²")
md.append(f"- 속도 범위: [{fd.v_mps.min():.2f}, {fd.v_mps.max():.2f}] m/s")
md.append(f"- 평균 밀도: **{fd.rho.mean():.3f} ped/m²**")
md.append(f"- 평균 속도: **{fd.v_mps.mean():.3f} m/s**")
md.append("")

md.append("### 밀도 구간별 빈도")
md.append("| 구간 | 시점 수 | 비율 |")
md.append("|---|---|---|")
md.append(f"| 자유흐름 (ρ < 0.5) | {n_free} | {n_free/len(fd)*100:.1f}% |")
md.append(f"| 중밀도 (0.5 ≤ ρ < 1.5) | {n_med} | {n_med/len(fd)*100:.1f}% |")
md.append(f"| 고밀도 (ρ ≥ 1.5) | {n_high} | {n_high/len(fd)*100:.1f}% |")
md.append(f"| 매우 고밀도 (ρ > 2.5) | {n_vh} | {n_vh/len(fd)*100:.1f}% |")
md.append("")

md.append("## 영상 측정 vs Weidmann 1993")
md.append("| ρ (ped/m²) | 시점 수 | 영상 v (m/s) | Weidmann v (m/s) | Δ (영상−Weidmann) |")
md.append("|---|---|---|---|---|")
for rho_q, n_sub, v_obs, v_std, v_w, diff in table:
    if v_obs is not None:
        md.append(f"| {rho_q:.1f} ± 0.25 | {n_sub} | {v_obs:.3f} ± {v_std:.3f} | {v_w:.3f} | {diff:+.3f} |")
    else:
        md.append(f"| {rho_q:.1f} ± 0.25 | {n_sub} | **측정 불가** (시점 < 3) | {v_w:.3f} | — |")
md.append("")

md.append("### Weidmann 적합도")
md.append(f"- **RMSE: {rmse:.3f} m/s**")
md.append(f"- MAE: {mae:.3f} m/s")
md.append("")

md.append("## 한계 / 주의사항")
md.append(f"- ROI 면적 {ROI_AREA:.1f} m²로 좁음. 영상 전체 화면 중 게이트 앞 일부만 분석.")
if n_high == 0:
    md.append(f"- **고밀도 (ρ ≥ 1.5) 시점 0개** — 자유흐름 dominant. Weidmann 곡선의 고밀도 영역 검증 불가.")
elif n_high < 20:
    md.append(f"- 고밀도 (ρ ≥ 1.5) 시점 {n_high}개로 부족. 통계적 신뢰성 제한.")
if n_vh == 0:
    md.append(f"- **매우 고밀도 (ρ > 2.5) 측정 데이터 없음** — 영상 ROI 안에서 그 정도 정체 발생 안 함.")
md.append(f"- 호모그래피의 perspective 항이 거의 0이라 사선 카메라 효과가 영역 외부에서 부정확. "
          f"게이트 영역(점자블록 영역 외부)으로 외삽 시 거리 환산 오차 가능.")
md.append(f"- frame-to-frame 속도는 트래킹 노이즈에 민감. v > {V_MAX} m/s outlier 제거 적용 (보행자 물리적 한계). smoothing 미적용.")
md.append(f"- 트래킹 ID가 짧게 끊기는 케이스(단말기 가림 등) 다수 → 일부 보행자 속도 0 또는 NaN로 측정 제외됨.")
md.append("")

md.append("## 출력 파일")
md.append(f"- 산점도: `figures/empirical_fundamental_diagram.png`")
md.append(f"- raw data: `data/empirical_density_speed.csv` ({len(fd_save)}행)")
md.append(f"- 본 보고서: `analysis/calibration_density_speed.md`")
md.append("")

md.append("## 후속 작업")
md.append("- 위 영상 측정 곡선을 시뮬 (CFSM `time_gap` 5개 값) 출력과 KS 비교")
md.append("- 고밀도 측정 부족 → 동일 역사 첨두 시간대 추가 영상 또는 다른 역사 영상 확보 필요")

with open(OUT_MD, "w", encoding="utf-8") as f:
    f.write("\n".join(md))
print(f"saved: {OUT_MD}")

print("\n완료.")
