"""
2단계: tracks CSV → 통과시간 + 보행속도 산출
- L_in / L_out 두 수평선 통과 시각으로 통과시간 계산
- 진입 직전 구간의 발끝 변위로 보행속도 (m/s) 추정
- 픽셀→미터 변환: 게이트 단말기 길이 ~1.5m 기준 단일 스케일

출력:
  passages.csv : ID별 통과시간/속도/방향
  summary.txt  : 분포 통계
  passages_overlay.png : 첫 프레임 위 통과 ID 궤적
  hist_passage.png / hist_speed.png : 분포 그래프
"""
import os, csv, math, sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import cv2
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

import argparse
VIDEO = r"C:\Users\aaron\tagless\개찰구 촬영 영상\1\GX010193_blurred.MP4"
DIR = r"C:\Users\aaron\tagless\영상데이터"
HOMOG_PATH = os.path.join(DIR, "homography.npy")
H = np.load(HOMOG_PATH) if os.path.exists(HOMOG_PATH) else None
print(f"homography: {'loaded' if H is not None else 'not found'}")

# ROI 라인 (bbox 중심 y 기준, 화면 좌표 — y 작을수록 게이트 통과 후)
LINE_IN_Y  = 250   # 진입선 (단말기 입구 직전)
LINE_OUT_Y = 180   # 이탈선 (단말기 출구 — 단말기 안 트랙 끊김 흡수)
GATE_CX_MIN = 150
GATE_CX_MAX = 560

# L_in ↔ L_out 사이 = 게이트 단말기 길이의 약 70% 가정 (실제 통과 거리 ~1.0m)
GATE_PASS_LENGTH_M = 1.0
PIX_VERT = abs(LINE_IN_Y - LINE_OUT_Y)  # 70
PIX2M = GATE_PASS_LENGTH_M / PIX_VERT

# 분석 파라미터
MIN_FRAMES = 6            # 너무 짧은 트랙 무시 (단말기 차폐 고려)
SPEED_WINDOW_S = 1.0      # 진입 전 1초 구간 보행속도
PERSON_H_M = 1.7          # 평균 보행자 신장 (위치별 m/px 환산용)
DIR_DY_MIN = 5            # 방향 판정 임계 (y 감소량, 픽셀)


def px2m(xp, yp, H_):
    """픽셀(xp, yp) → 미터 좌표 (지면 호모그래피)."""
    p = np.stack([xp, yp, np.ones_like(xp)], axis=0)
    q = H_ @ p
    return q[0]/q[2], q[1]/q[2]


def crossing_time(times, ys, line_y, direction="down"):
    """ys 배열이 line_y를 direction(down: y_foot 줄어드는 = 화면상 위로)으로 통과한
    첫 시각을 선형보간으로 반환. 통과 못했으면 None."""
    for i in range(1, len(ys)):
        y0, y1 = ys[i-1], ys[i]
        if direction == "down":
            if y0 >= line_y > y1:
                # 선형보간
                if y0 == y1:
                    return times[i]
                frac = (y0 - line_y) / (y0 - y1)
                return times[i-1] + frac * (times[i] - times[i-1])
        else:
            if y0 <= line_y < y1:
                if y0 == y1:
                    return times[i]
                frac = (line_y - y0) / (y1 - y0)
                return times[i-1] + frac * (times[i] - times[i-1])
    return None


def main(tracks_csv, out_passages, out_summary, tag="", t_min=None, t_max=None):
    df = pd.read_csv(tracks_csv)
    df["cy_center"] = (df["y1"] + df["y2"]) / 2.0
    print(f"loaded: {len(df)} rows, {df['id'].nunique()} ids   ({tracks_csv})")
    if t_min is not None or t_max is not None:
        lo = t_min if t_min is not None else df["t_sec"].min()
        hi = t_max if t_max is not None else df["t_sec"].max()
        # 진입 직전 1초 + 통과 시간 여유 → 윈도우 ±3초 데이터 확보 후 t_in로 필터
        df = df[(df["t_sec"] >= lo - 3) & (df["t_sec"] <= hi + 3)]
        print(f"time window applied: track t∈[{lo-3:.1f}, {hi+3:.1f}], "
              f"counting passages with t_in∈[{lo:.1f}, {hi:.1f}] → "
              f"{len(df)} rows, {df['id'].nunique()} ids")

    # 너무 짧은 트랙 제거
    counts = df.groupby("id").size()
    keep = counts[counts >= MIN_FRAMES].index
    df = df[df["id"].isin(keep)].sort_values(["id", "frame"])
    print(f"after MIN_FRAMES filter: {df['id'].nunique()} ids")

    rows = []
    for pid, g in df.groupby("id"):
        ts = g["t_sec"].values
        ys = g["cy_center"].values   # bbox 중심 y (ROI 라인 통과 판정용)
        xs = g["cx"].values
        ys_foot = g["y2"].values     # 발끝 y (호모그래피 변환용 - 지면 좌표)
        bbox_h = (g["y2"] - g["y1"]).values  # 각 프레임 bbox 높이

        # 게이트 영역 통과 여부 (한 번이라도 GATE_CX 안에 들어왔는지)
        in_gate_cx = ((xs >= GATE_CX_MIN) & (xs <= GATE_CX_MAX))
        if not in_gate_cx.any():
            continue

        # 통과 방향 자동 판정 (y 시작-끝 변화) — 양방향 모두 인정
        dy = ys[-1] - ys[0]
        if abs(dy) < DIR_DY_MIN:
            continue  # 거의 안 움직임 (멈춰있음)

        if dy < 0:
            # down: y 감소 (화면 위로) — 영상 sample_q1 패턴
            direction = "down"
            t_in  = crossing_time(ts, ys, LINE_IN_Y,  "down")
            t_out = crossing_time(ts, ys, LINE_OUT_Y, "down")
        else:
            # up: y 증가 (화면 아래로) — 영상 11:25 패턴 (게이트 출구 측 카메라)
            direction = "up"
            t_in  = crossing_time(ts, ys, LINE_OUT_Y, "up")
            t_out = crossing_time(ts, ys, LINE_IN_Y,  "up")

        if t_in is None or t_out is None or t_out <= t_in:
            continue

        passage_time = t_out - t_in

        # 진입 직전 보행속도
        # 우선 호모그래피(점자블록 30cm 기준) 사용 → fallback: bbox 높이 환산
        mask_pre = (ts >= t_in - SPEED_WINDOW_S) & (ts < t_in)
        if mask_pre.sum() >= 3:
            tx = ts[mask_pre]
            xx = xs[mask_pre]
            yfoot = ys_foot[mask_pre]
            dts = np.diff(tx)
            if H is not None:
                xm, ym = px2m(xx.astype(np.float64), yfoot.astype(np.float64), H)
                dxs = np.diff(xm)
                dys = np.diff(ym)
                d_m = np.hypot(dxs, dys)
            else:
                bh = np.clip(bbox_h[mask_pre], 30, None)
                mpp = PERSON_H_M / bh
                mpp_mid = (mpp[:-1] + mpp[1:]) / 2.0
                d_m = np.hypot(np.diff(xx), np.diff(ys[mask_pre])) * mpp_mid
            v_arr = d_m / np.where(dts > 0, dts, 1)
            v = float(np.median(v_arr))
        else:
            v = np.nan

        # 게이트 통과 평균속도 (L_in ~ L_out 사이)
        v_gate = GATE_PASS_LENGTH_M / passage_time

        # 진입 시 어느 cx 위치인지 (게이트 ID 추정용 cx 평균)
        mask_gate = (ts >= t_in) & (ts <= t_out)
        cx_gate = xs[mask_gate].mean() if mask_gate.any() else np.nan

        # t_in이 사용자 지정 윈도우 안에 있는지 확인
        if t_min is not None and t_in < t_min: continue
        if t_max is not None and t_in > t_max: continue
        rows.append({
            "id": int(pid),
            "direction": direction,
            "t_in": round(t_in, 3),
            "t_out": round(t_out, 3),
            "passage_time_s": round(passage_time, 3),
            "v_gate_mps": round(v_gate, 3),
            "v_pre_mps": round(v, 3) if not np.isnan(v) else np.nan,
            "cx_gate": round(cx_gate, 1) if not np.isnan(cx_gate) else np.nan,
            "n_frames": int(len(ts)),
        })

    pa = pd.DataFrame(rows, columns=["id","direction","t_in","t_out","passage_time_s",
                                     "v_gate_mps","v_pre_mps","cx_gate","n_frames"])
    pa.to_csv(out_passages, index=False, encoding="utf-8-sig")
    print(f"saved {len(pa)} passages -> {out_passages}")
    if len(pa) == 0:
        print("[WARN] no passages detected. check ROI lines / direction assumption.")
        return

    # ---- 요약 통계 ----
    def stat(s):
        s = s.dropna()
        return dict(
            n=len(s), mean=s.mean(), std=s.std(),
            p15=s.quantile(0.15), p50=s.quantile(0.5),
            p85=s.quantile(0.85), min=s.min(), max=s.max())

    pt_stat = stat(pa["passage_time_s"])
    vg_stat = stat(pa["v_gate_mps"])
    vp_stat = stat(pa["v_pre_mps"])

    lines = []
    lines.append("=" * 60)
    lines.append("개찰구 통과시간 + 보행속도 분석 결과")
    lines.append("=" * 60)
    lines.append(f"영상: {os.path.basename(VIDEO)}")
    lines.append(f"트랙 ID 수 (게이트 통과): {len(pa)}")
    lines.append(f"ROI: L_in y={LINE_IN_Y}, L_out y={LINE_OUT_Y}, "
                 f"GATE_CX=[{GATE_CX_MIN},{GATE_CX_MAX}]")
    lines.append(f"점자블록 30cm 정사각형 기반 호모그래피 사용 ({'OK' if H is not None else 'NONE'})")
    lines.append(f"ROI 두 라인 사이 게이트 단말기 약 {GATE_PASS_LENGTH_M:.1f}m 통과 구간으로 가정")
    lines.append("")
    def fmt(d, unit):
        return (f"  n={d['n']:3d}  mean={d['mean']:6.2f}{unit}  std={d['std']:5.2f}  "
                f"p15={d['p15']:5.2f}  p50={d['p50']:5.2f}  p85={d['p85']:5.2f}  "
                f"min={d['min']:5.2f}  max={d['max']:5.2f}")
    lines.append(f"[통과시간 (L_in→L_out, ROI 약 {GATE_PASS_LENGTH_M:.1f}m 구간)]")
    lines.append(fmt(pt_stat, "s"))
    lines.append("")
    lines.append(f"[ROI 평균 통과속도 = {GATE_PASS_LENGTH_M:.1f}m / 통과시간]")
    lines.append(fmt(vg_stat, "m/s"))
    lines.append("")
    lines.append("[진입 직전 1초 보행속도 (호모그래피 환산, 자유보행 비교)]")
    lines.append(fmt(vp_stat, "m/s"))
    lines.append("")
    lines.append("[비교 기준 (CLAUDE.md / 선행연구)]")
    lines.append("  - 태그리스 통과시간 가정: 1.2 s (게이트 1.5m / 1.3 m/s)")
    lines.append("  - 태그 통과시간 가정 : 2.0 s lognormal (Gao 2019)")
    lines.append("  - 자유보행 v0       : 1.34 m/s (Weidmann 1993, Fruin 1971)")
    # 1.5m 단말기 전체 환산 (참고용)
    pt_full = pa["passage_time_s"] * (1.5 / GATE_PASS_LENGTH_M)
    lines.append("")
    lines.append("[참고: 단말기 전체 1.5m 비례 환산 통과시간]")
    lines.append(fmt(stat(pt_full), "s"))
    out = "\n".join(lines)
    with open(out_summary, "w", encoding="utf-8") as f:
        f.write(out + "\n")
    print(out)

    # ---- 시각화 ----
    # (a) 첫 프레임 + 통과 ID 궤적 + ROI lines
    cap = cv2.VideoCapture(VIDEO)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 6487)
    ok, base = cap.read()
    cap.release()

    fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
    ax.imshow(cv2.cvtColor(base, cv2.COLOR_BGR2RGB))
    cmap = plt.cm.tab20
    for k, pid in enumerate(pa["id"].values):
        g = df[df["id"] == pid].sort_values("frame")
        ax.plot(g["cx"], g["cy_center"], color=cmap(k % 20), lw=0.7, alpha=0.6)
    ax.axhline(LINE_IN_Y,  color="red",  lw=2, label=f"L_in y={LINE_IN_Y}")
    ax.axhline(LINE_OUT_Y, color="lime", lw=2, label=f"L_out y={LINE_OUT_Y}")
    ax.axvline(GATE_CX_MIN, color="cyan", lw=1, ls="--")
    ax.axvline(GATE_CX_MAX, color="cyan", lw=1, ls="--")
    ax.set_xlim(0, base.shape[1]); ax.set_ylim(base.shape[0], 0)
    ax.legend(loc="lower right", fontsize=8)
    ax.set_title(f"통과 ID 궤적 (n={len(pa)}) {tag}")
    fig.tight_layout(); fig.savefig(os.path.join(DIR, f"passages_overlay{tag}.png"))
    plt.close(fig)

    # (b) 통과시간 히스토그램
    fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
    ax.hist(pa["passage_time_s"].clip(upper=10), bins=40, color="#4682B4", edgecolor="white")
    ax.axvline(1.2, color="red", ls="--", label="가정: 태그리스 1.2s")
    ax.axvline(2.0, color="orange", ls="--", label="가정: 태그 2.0s")
    ax.axvline(pa["passage_time_s"].median(), color="black", ls="-", lw=1.5,
               label=f"실측 중앙값 {pa['passage_time_s'].median():.2f}s")
    ax.set_xlabel("통과시간 (s)  L_in → L_out")
    ax.set_ylabel("count")
    ax.set_title(f"개찰구 통과시간 분포  n={len(pa)} {tag}")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(DIR, f"hist_passage{tag}.png"))
    plt.close(fig)

    # (c) 보행속도 히스토그램 (진입 전)
    vp = pa["v_pre_mps"].dropna()
    fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
    ax.hist(vp.clip(0, 3), bins=30, color="#3CB371", edgecolor="white")
    ax.axvline(1.34, color="red", ls="--", label="자유보행 v0=1.34 m/s")
    if len(vp):
        ax.axvline(vp.median(), color="black", ls="-", lw=1.5,
                   label=f"실측 중앙값 {vp.median():.2f} m/s")
    ax.set_xlabel("진입 직전 1초 보행속도 (m/s)")
    ax.set_ylabel("count")
    ax.set_title(f"보행속도 분포  n={len(vp)} {tag}")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(DIR, f"hist_speed{tag}.png"))
    plt.close(fig)
    print("plots saved.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracks", default=os.path.join(DIR, "tracks_full.csv"))
    ap.add_argument("--out", default=os.path.join(DIR, "passages.csv"))
    ap.add_argument("--summary", default=os.path.join(DIR, "summary.txt"))
    ap.add_argument("--tag", default="")
    ap.add_argument("--tmin", type=float, default=None)
    ap.add_argument("--tmax", type=float, default=None)
    a = ap.parse_args()
    main(a.tracks, a.out, a.summary, a.tag, a.tmin, a.tmax)
