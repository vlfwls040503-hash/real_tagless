"""11:00-11:50 시점 트래킹 궤적 + ROI 라인 시각화"""
import os, sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import cv2, numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

VIDEO = r"C:\Users\aaron\tagless\개찰구 촬영 영상\1\GX010193_blurred.MP4"
DIR = r"C:\Users\aaron\tagless\영상데이터"
LINE_IN_Y, LINE_OUT_Y = 250, 180
GATE_CX_MIN, GATE_CX_MAX = 150, 560

df = pd.read_csv(os.path.join(DIR, "tracks_full.csv"))
df["cy_center"] = (df["y1"] + df["y2"]) / 2.0
w = df[(df.t_sec>=660)&(df.t_sec<=710)]
print(f"11:00-11:50: {len(w)} rows, {w.id.nunique()} ids")

cap = cv2.VideoCapture(VIDEO)
cap.set(cv2.CAP_PROP_POS_FRAMES, int(685*29.97))   # 11:25
ok, base = cap.read()
cap.release()

fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
ax.imshow(cv2.cvtColor(base, cv2.COLOR_BGR2RGB))
cmap = plt.cm.tab20
ids = w.id.unique()
print(f"plotting {len(ids)} tracks...")
for k, pid in enumerate(ids):
    g = w[w.id==pid].sort_values("frame")
    if len(g) < 5: continue
    color = cmap(k % 20)
    ax.plot(g.cx, g.cy_center, color=color, lw=0.8, alpha=0.6)
    # 시작 점
    ax.scatter(g.cx.iloc[0], g.cy_center.iloc[0], color=color, s=8, marker="o")
    # 끝 점
    ax.scatter(g.cx.iloc[-1], g.cy_center.iloc[-1], color=color, s=12, marker="x")

# ROI lines
ax.axhline(LINE_IN_Y,  color="red",   lw=2, label=f"L_in y={LINE_IN_Y}")
ax.axhline(LINE_OUT_Y, color="lime",  lw=2, label=f"L_out y={LINE_OUT_Y}")
ax.axvline(GATE_CX_MIN, color="cyan", lw=1, ls="--")
ax.axvline(GATE_CX_MAX, color="cyan", lw=1, ls="--", label=f"cx∈[{GATE_CX_MIN},{GATE_CX_MAX}]")

ax.set_xlim(0, base.shape[1]); ax.set_ylim(base.shape[0], 0)
ax.legend(loc="lower right", fontsize=7)
ax.set_title(f"11:00-11:50 모든 트래킹 ({len(ids)}명)\n○=시작 ×=끝 / ROI 라인 + 게이트 영역")
fig.tight_layout()
fig.savefig(os.path.join(DIR, "viz_11min.png"))
print("saved:", os.path.join(DIR, "viz_11min.png"))

# 통과 방향 통계
print("\n방향 통계 (cy_center 시작-끝 변화):")
spans = []
for pid in ids:
    g = w[w.id==pid].sort_values("frame")
    if len(g) < 6: continue
    dy = g.cy_center.iloc[-1] - g.cy_center.iloc[0]
    spans.append((pid, dy, g.cx.mean(), len(g)))
spans = pd.DataFrame(spans, columns=["id","dy","cx_avg","n"])
print(f"  down (dy<-10): {(spans.dy<-10).sum()}")
print(f"  up   (dy>+10): {(spans.dy>10).sum()}")
print(f"  stay (|dy|<10): {(spans.dy.abs()<=10).sum()}")
