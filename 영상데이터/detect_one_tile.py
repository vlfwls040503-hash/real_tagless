"""
점자블록 1칸(30cm 정사각형)의 4 코너를 자동 검출.
- 워프된 영역 안에서 점자블록 영역만 추출
- 어두운 경계선(점자블록 사이) Hough Lines 검출
- 격자 교차점 → 한 칸 4 corner 추출
- 그 한 칸을 원본 영상 좌표로 역변환 → 30cm 정사각형으로 호모그래피
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

src = np.load(os.path.join(DIR, "tactile_box.npy")).astype(np.float32)

cap = cv2.VideoCapture(VIDEO)
n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
acc = None; cnt = 0
for idx in [30, n_total//4, n_total//2, 3*n_total//4, n_total-100]:
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, f = cap.read()
    if not ok: continue
    acc = f.astype(np.float32) if acc is None else acc + f.astype(np.float32)
    cnt += 1
cap.release()
base = (acc/cnt).astype(np.uint8)

# 큰 워프
WARP = 800
warp_dst = np.array([[0,0],[WARP,0],[WARP,WARP],[0,WARP]], dtype=np.float32)
H_warp = cv2.getPerspectiveTransform(src, warp_dst)
warped = cv2.warpPerspective(base, H_warp, (WARP, WARP))

# 워프 영상에서 점자블록 색(주황) 마스크
hsv = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)
mask = cv2.inRange(hsv, (10, 100, 100), (32, 255, 255))
k = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)

# 점자블록 영역만 grayscale
gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
gray_masked = cv2.bitwise_and(gray, gray, mask=mask)

# Edge 검출
edges = cv2.Canny(gray_masked, 30, 90)
# 점자블록 사이 경계는 가로/세로 라인 (마스크 안에서)
# HoughLinesP
lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=40,
                        minLineLength=40, maxLineGap=5)
print(f"detected lines: {0 if lines is None else len(lines)}")

# 라인 각도 분류 (수직 vs 수평)
horizontals = []   # angle near 0 or 180
verticals = []     # angle near 90
if lines is not None:
    for x1,y1,x2,y2 in lines.reshape(-1, 4):
        ang = np.degrees(np.arctan2(y2-y1, x2-x1))
        ang = abs(ang)
        if ang < 25 or ang > 155:
            horizontals.append((x1,y1,x2,y2))
        elif 65 < ang < 115:
            verticals.append((x1,y1,x2,y2))
print(f"  horizontal lines: {len(horizontals)}")
print(f"  vertical lines:   {len(verticals)}")

# 수평선의 y 좌표, 수직선의 x 좌표 → 격자 위치
hy = np.array([(l[1]+l[3])/2 for l in horizontals])
vx = np.array([(l[0]+l[2])/2 for l in verticals])

# 클러스터링 (인접한 라인 합침)
def cluster_1d(arr, min_gap):
    if len(arr) == 0: return np.array([])
    arr = np.sort(arr)
    groups = [[arr[0]]]
    for v in arr[1:]:
        if v - groups[-1][-1] < min_gap:
            groups[-1].append(v)
        else:
            groups.append([v])
    return np.array([np.mean(g) for g in groups])

hy_c = cluster_1d(hy, min_gap=20)
vx_c = cluster_1d(vx, min_gap=20)
print(f"  unique horizontal y: {len(hy_c)} -> {hy_c}")
print(f"  unique vertical x:   {len(vx_c)} -> {vx_c}")

# 인접 격자선 사이 픽셀 거리 → 점자블록 1칸 픽셀 추정
if len(hy_c) >= 2:
    dy = np.diff(hy_c)
    print(f"  cell height candidates (px): {dy}")
if len(vx_c) >= 2:
    dx = np.diff(vx_c)
    print(f"  cell width candidates (px):  {dx}")

# 시각화
fig, axes = plt.subplots(2, 2, figsize=(11, 8), dpi=100)
axes[0,0].imshow(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))
axes[0,0].set_title("워프된 영역")
axes[0,1].imshow(mask, cmap="gray")
axes[0,1].set_title("점자블록 색 마스크")
axes[1,0].imshow(edges, cmap="gray")
for x1,y1,x2,y2 in horizontals: axes[1,0].plot([x1,x2],[y1,y2], color="red", lw=0.5)
for x1,y1,x2,y2 in verticals:   axes[1,0].plot([x1,x2],[y1,y2], color="cyan", lw=0.5)
axes[1,0].set_title(f"Edge + Hough Lines\nh={len(horizontals)} v={len(verticals)}")
axes[1,1].imshow(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))
for y in hy_c: axes[1,1].axhline(y, color="red", lw=1, alpha=0.7)
for x in vx_c: axes[1,1].axvline(x, color="cyan", lw=1, alpha=0.7)
axes[1,1].set_title(f"클러스터 격자선 h={len(hy_c)} v={len(vx_c)}")
fig.tight_layout()
fig.savefig(os.path.join(DIR, "one_tile.png"))
print("saved:", os.path.join(DIR, "one_tile.png"))
