"""
영상의 모든 노란 영역을 시각화 + 각 영역의 형상 분석.
점형(매트릭스) vs 선형(띠) 자동 분류.
"""
import os, sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import cv2, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

VIDEO = r"C:\Users\aaron\tagless\개찰구 촬영 영상\1\GX010193_blurred.MP4"
DIR = r"C:\Users\aaron\tagless\영상데이터"

cap = cv2.VideoCapture(VIDEO)
n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
mask_accum = None; cnt = 0
for idx in [30, n_total//4, n_total//2, 3*n_total//4, n_total-100]:
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, frame = cap.read()
    if not ok: continue
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (15, 100, 100), (35, 255, 255))   # 약간 관대하게
    mask_accum = m.astype(np.int32) if mask_accum is None else mask_accum + m.astype(np.int32)
    cnt += 1
cap.set(cv2.CAP_PROP_POS_FRAMES, 30); ok, base = cap.read(); cap.release()

mask = (mask_accum >= (cnt * 255 // 2)).astype(np.uint8) * 255
# 게이트 영역 (단말기 표시등 등) 제외 — y > 230
mask[:230, :] = 0
k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k3, iterations=2)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k3, iterations=1)

contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
contours = sorted(contours, key=cv2.contourArea, reverse=True)

print("== 노란 영역 후보 (면적순) ==")
print(f"{'#':>2} {'area':>6} {'w':>5} {'h':>5} {'ratio':>5} {'angle':>6} {'cx':>5} {'cy':>5} type")
fig, ax = plt.subplots(figsize=(11, 6.5), dpi=100)
ax.imshow(cv2.cvtColor(base, cv2.COLOR_BGR2RGB))
ax.imshow(mask, alpha=0.25, cmap="autumn")

cmap = plt.cm.tab10
infos = []
for i, c in enumerate(contours[:8]):
    area = cv2.contourArea(c)
    if area < 200: continue
    rect = cv2.minAreaRect(c)
    (cx, cy), (w, h), angle = rect
    short = min(w, h); long = max(w, h)
    ratio = long / short if short > 0 else 0
    box = cv2.boxPoints(rect)
    typ = "선형(띠)" if ratio >= 2.0 else "점형(매트릭스)" if ratio < 1.5 else "혼합"
    print(f"{i:>2} {area:>6.0f} {w:>5.0f} {h:>5.0f} {ratio:>5.1f} {angle:>6.1f} {cx:>5.0f} {cy:>5.0f} {typ}")
    color = cmap(i)
    poly = np.vstack([box, box[:1]])
    ax.plot(poly[:,0], poly[:,1], color=color, lw=2,
            label=f"#{i} a={area:.0f} {w:.0f}x{h:.0f} ratio={ratio:.1f} {typ}")
    ax.annotate(f"#{i}", (cx, cy), color=color, fontsize=11, weight="bold",
                ha="center", va="center")
    infos.append(dict(idx=i, area=area, w=w, h=h, ratio=ratio, cx=cx, cy=cy,
                      angle=angle, box=box, type=typ))

ax.legend(loc="upper right", fontsize=7)
ax.set_title("모든 노란 영역 분류 (선형=띠/점형=매트릭스/혼합)")
fig.tight_layout()
fig.savefig(os.path.join(DIR, "yellow_survey.png"))
print("saved:", os.path.join(DIR, "yellow_survey.png"))

np.save(os.path.join(DIR, "yellow_infos.npy"),
        np.array([(d['idx'],d['area'],d['w'],d['h'],d['ratio'],d['cx'],d['cy'],d['angle'])
                  for d in infos]))
np.save(os.path.join(DIR, "yellow_boxes.npy"),
        np.array([d['box'] for d in infos]))
