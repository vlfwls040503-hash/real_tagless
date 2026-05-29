"""
ROI 라인 후보를 첫 프레임 + 궤적 위에 표시.
"""
import cv2, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

VIDEO = r"C:\Users\aaron\tagless\개찰구 촬영 영상\1\GX010193_blurred.MP4"
CSV = r"C:\Users\aaron\tagless\영상데이터\tracks_60s.csv"
OUT = r"C:\Users\aaron\tagless\영상데이터\viz_with_lines.png"

# ROI 라인 후보 (수평선 2개) + 게이트 영역 cx 범위
LINE_IN_Y  = 245   # 진입선 (보행자 발끝 y가 이 값을 위→아래로? 아니다 아래→위로 통과)
LINE_OUT_Y = 130   # 이탈선
GATE_CX_MIN = 180
GATE_CX_MAX = 520

cap = cv2.VideoCapture(VIDEO)
cap.set(cv2.CAP_PROP_POS_FRAMES, 6487)  # q1 시점 (사람 많이 보이는)
ok, base = cap.read()
cap.release()

df = pd.read_csv(CSV)
counts = df.groupby("id").size()
df = df[df["id"].isin(counts[counts >= 8].index)]

fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
ax.imshow(cv2.cvtColor(base, cv2.COLOR_BGR2RGB))

cmap = plt.cm.tab20
for k, pid in enumerate(df["id"].unique()):
    g = df[df["id"] == pid].sort_values("frame")
    ax.plot(g["cx"], g["cy_foot"], color=cmap(k % 20), lw=1.0, alpha=0.6)

# ROI lines
ax.axhline(LINE_IN_Y,  color="red",   lw=2, label=f"L_in  y={LINE_IN_Y}")
ax.axhline(LINE_OUT_Y, color="lime",  lw=2, label=f"L_out y={LINE_OUT_Y}")
ax.axvline(GATE_CX_MIN, color="cyan", lw=1, ls="--")
ax.axvline(GATE_CX_MAX, color="cyan", lw=1, ls="--", label=f"cx in [{GATE_CX_MIN},{GATE_CX_MAX}]")

ax.set_xlim(0, base.shape[1]); ax.set_ylim(base.shape[0], 0)
ax.legend(loc="lower right", fontsize=8)
ax.set_title("ROI candidates over background (q1 frame) + 60s tracks")
fig.tight_layout(); fig.savefig(OUT)
print("saved:", OUT)
