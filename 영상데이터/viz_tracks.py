"""
트래킹 CSV 위에 궤적을 그려 첫 프레임에 오버레이.
ROI 라인 위치 결정용 시각화.
"""
import os
import cv2
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

VIDEO = r"C:\Users\aaron\tagless\개찰구 촬영 영상\1\GX010193_blurred.MP4"
CSV = r"C:\Users\aaron\tagless\영상데이터\tracks_60s.csv"
OUT = r"C:\Users\aaron\tagless\영상데이터\viz_tracks_60s.png"

cap = cv2.VideoCapture(VIDEO)
cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
ok, base = cap.read()
cap.release()
H, W = base.shape[:2]
print("frame:", H, W)

df = pd.read_csv(CSV)
print("rows:", len(df), "uniq ids:", df["id"].nunique())

# 궤적 길이로 필터 (잠깐 검출된 잡음 제거)
counts = df.groupby("id").size()
keep_ids = counts[counts >= 8].index
df = df[df["id"].isin(keep_ids)]
print("after filter ids:", df["id"].nunique())

fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
ax.imshow(cv2.cvtColor(base, cv2.COLOR_BGR2RGB))

cmap = plt.cm.tab20
ids = df["id"].unique()
for k, pid in enumerate(ids):
    g = df[df["id"] == pid].sort_values("frame")
    color = cmap(k % 20)
    ax.plot(g["cx"], g["cy_foot"], color=color, lw=0.8, alpha=0.7)
    # 시작점
    ax.scatter(g["cx"].iloc[0], g["cy_foot"].iloc[0], color=color, s=8, marker="o")
    # 끝점
    ax.scatter(g["cx"].iloc[-1], g["cy_foot"].iloc[-1], color=color, s=10, marker="x")

ax.set_xlim(0, W)
ax.set_ylim(H, 0)
ax.set_title(f"Trajectories (60s, n_id={len(ids)})  ○=start  ×=end")
fig.tight_layout()
fig.savefig(OUT)
print("saved:", OUT)

# 발끝 y의 분포 + cx 분포 출력 (라인 위치 가늠)
print("\nfoot y stats:")
print(df["cy_foot"].describe())
print("\ncx stats:")
print(df["cx"].describe())
