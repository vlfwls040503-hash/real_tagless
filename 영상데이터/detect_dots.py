"""
워프된 점자블록 영역에서 둥근 돌기를 HoughCircles로 검출 → 돌기 격자 간격 → 점자블록 칸 수 자동.
점자블록 1칸(30cm)에 5x5 돌기 = 돌기 간격 6cm.
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

# 좌하단 점자블록 영역 (이미 검출된 4 corner)
src = np.load(os.path.join(DIR, "tactile_box.npy")).astype(np.float32)

cap = cv2.VideoCapture(VIDEO)
cap.set(cv2.CAP_PROP_POS_FRAMES, 30); ok, base = cap.read(); cap.release()

# 큰 워프 (해상도 충분히)
WARP = 800
warp_dst = np.array([[0,0],[WARP,0],[WARP,WARP],[0,WARP]], dtype=np.float32)
H_warp = cv2.getPerspectiveTransform(src, warp_dst)
warped = cv2.warpPerspective(base, H_warp, (WARP, WARP))
cv2.imwrite(os.path.join(DIR, "warped_zoom.png"), warped)

# Houghcircles
gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
blur = cv2.medianBlur(gray, 5)

# 다양한 반지름 시도
all_circles = []
for r_min, r_max in [(3,8), (4,10), (6,14), (8,18)]:
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.2,
                               minDist=r_max,
                               param1=80, param2=15,
                               minRadius=r_min, maxRadius=r_max)
    n = 0 if circles is None else circles.shape[1]
    print(f"  HoughCircles r=[{r_min},{r_max}]: {n} circles")
    if circles is not None:
        all_circles.append((r_min, r_max, circles[0]))

# 검출된 돌기 시각화
fig, axes = plt.subplots(1, 2, figsize=(11, 5), dpi=100)
axes[0].imshow(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))
axes[0].set_title(f"워프된 점자블록 영역 ({WARP}x{WARP})")

axes[1].imshow(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))
colors = ["red", "yellow", "lime", "cyan"]
for (rmin, rmax, circs), col in zip(all_circles, colors):
    for (cx, cy, r) in circs:
        c = plt.Circle((cx,cy), r, color=col, fill=False, lw=1)
        axes[1].add_patch(c)
axes[1].set_title("HoughCircles 검출 (돌기 후보)")
fig.tight_layout()
fig.savefig(os.path.join(DIR, "hough_dots.png"))
print("saved:", os.path.join(DIR, "hough_dots.png"))

# 돌기 좌표 모아서 격자 분석 (가장 일반적인 검출 결과 선택)
if all_circles:
    # 가장 많이 검출된 결과
    rmin, rmax, circs = max(all_circles, key=lambda t: len(t[2]))
    print(f"\nbest detection r=[{rmin},{rmax}]: {len(circs)} circles")
    if len(circs) >= 6:
        cxs = circs[:,0]
        cys = circs[:,1]
        # x좌표 정렬, 인접 x좌표 차이 분석 (최빈값 = 돌기 간격)
        cxs_sorted = np.sort(cxs)
        cys_sorted = np.sort(cys)
        dxs = np.diff(cxs_sorted)
        dys = np.diff(cys_sorted)
        # 너무 가까운 건 같은 돌기. 너무 먼 건 다른 점자블록 칸 사이.
        dxs = dxs[(dxs > 5) & (dxs < 100)]
        dys = dys[(dys > 5) & (dys < 100)]
        if len(dxs):
            print(f"  dot x-spacing median = {np.median(dxs):.1f} px")
            print(f"  dot y-spacing median = {np.median(dys):.1f} px")
            # 돌기 간격 = 6cm (점자블록 1칸 30cm 안 5x5 돌기)
            cm_per_px_x = 6.0 / np.median(dxs)
            cm_per_px_y = 6.0 / np.median(dys)
            block_size_x_cm = cm_per_px_x * WARP
            block_size_y_cm = cm_per_px_y * WARP
            print(f"  → 매트릭스 가로 = {block_size_x_cm:.1f} cm = {block_size_x_cm/30:.2f} 칸")
            print(f"  → 매트릭스 세로 = {block_size_y_cm:.1f} cm = {block_size_y_cm/30:.2f} 칸")
