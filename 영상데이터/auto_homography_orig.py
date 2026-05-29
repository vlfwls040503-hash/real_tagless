"""
원본 1080p 영상으로 점자블록 자동 호모그래피
- L자 영역을 두 개의 직사각형 영역(세로 막대 + 가로 막대)으로 분리
- 각 영역에서 점자블록 한 칸 30cm를 격자선/Edge로 자동 카운트
- 원본 좌표계의 호모그래피 → 블러 좌표계(트래킹 결과)로 다운스케일
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

VIDEO_ORIG = r"C:\Users\aaron\tagless\개찰구 촬영 영상\1\GX010193.MP4"
DIR = r"C:\Users\aaron\tagless\영상데이터"
SCALE = 720.0 / 1920.0   # 원본 → 블러 좌표 환산비

# ──────────────────────────────────────────────
# 1. 노란 점자블록 마스크 (원본)
# ──────────────────────────────────────────────
cap = cv2.VideoCapture(VIDEO_ORIG)
n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
acc = None; cnt = 0
for idx in [30, n_total//4, n_total//2, 3*n_total//4, n_total-100]:
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, f = cap.read()
    if not ok: continue
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (15, 100, 100), (35, 255, 255))
    acc = m.astype(np.int32) if acc is None else acc + m.astype(np.int32)
    cnt += 1
cap.set(cv2.CAP_PROP_POS_FRAMES, 30); ok, base = cap.read(); cap.release()

mask = (acc >= (cnt * 255 // 2)).astype(np.uint8) * 255
H_full, W_full = mask.shape
# 게이트 단말기/표시등 영역 제외 (원본 1080) — 화면 좌측 1/3 + 화면 하단만 사용
roi_mask = np.zeros_like(mask)
roi_mask[600:, :720] = 255  # 좌측 하단 점자블록 영역만
mask = cv2.bitwise_and(mask, roi_mask)
k = cv2.getStructuringElement(cv2.MORPH_RECT, (9,9))
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=3)

contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
contours = sorted(contours, key=cv2.contourArea, reverse=True)
print(f"largest contour area = {cv2.contourArea(contours[0]):.0f} px²  (1080p)")

# ㄴ자 영역을 두 직사각형으로 분리 (가로 막대 영역만 사용 - 더 큰 직사각형)
# erosion 강하게 → ㄴ자 코너 끊기 → 두 부분 분리
k_erode = cv2.getStructuringElement(cv2.MORPH_RECT, (15,15))
mask_eroded = cv2.morphologyEx(mask, cv2.MORPH_ERODE, k_erode, iterations=2)
sub_contours, _ = cv2.findContours(mask_eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
sub_contours = sorted(sub_contours, key=cv2.contourArea, reverse=True)
print(f"after erosion: {len(sub_contours)} sub-regions")
for i, sc in enumerate(sub_contours[:3]):
    rect = cv2.minAreaRect(sc)
    print(f"  sub#{i} area={cv2.contourArea(sc):.0f}  rect={rect[1][0]:.0f}x{rect[1][1]:.0f}")

# 가장 큰 sub-region의 minAreaRect 사용 (한 직사각형 영역만)
if len(sub_contours) >= 1:
    largest_sub = sub_contours[0]
    # 다시 dilate해서 원래 크기 복원
    sub_mask = np.zeros_like(mask)
    cv2.drawContours(sub_mask, [largest_sub], -1, 255, -1)
    sub_mask = cv2.dilate(sub_mask, k_erode, iterations=2)
    # 원본 mask와 AND
    sub_mask = cv2.bitwise_and(mask, sub_mask)
    sub_contours2, _ = cv2.findContours(sub_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if sub_contours2:
        c_use = max(sub_contours2, key=cv2.contourArea)
        print(f"using sub-region area={cv2.contourArea(c_use):.0f}")
    else:
        c_use = contours[0]
else:
    c_use = contours[0]
c = c_use
# minAreaRect로 직접 4 corner (ㄴ자에서도 안정적인 직사각형 fit)
rect_use = cv2.minAreaRect(c)
print(f"\nminAreaRect: center={rect_use[0]} size={rect_use[1]} angle={rect_use[2]:.1f}")
pts_rect = cv2.boxPoints(rect_use)
print(f"4 corners (1080p, minAreaRect):")
for p in pts_rect: print(f"  {p}")

# ──────────────────────────────────────────────
# 2. polygon fit — 1080p에서 더 정확
# ──────────────────────────────────────────────
c = contours[0]
peri = cv2.arcLength(c, True)
best_approx = None
for eps_ratio in np.linspace(0.005, 0.05, 30):
    approx = cv2.approxPolyDP(c, eps_ratio * peri, True)
    if len(approx) == 4:
        best_approx = approx; print(f"polygon fit -> 4 corners (eps_ratio={eps_ratio:.3f})")
        break
    if best_approx is None or abs(len(approx)-4) < abs(len(best_approx)-4):
        best_approx = approx
print(f"polygon fit final: {len(best_approx)} corners")

# 직사각형 외곽 사용 (ㄴ자라도 안정적)
pts = pts_rect.astype(np.float32)

def order_corners(p):
    p = np.array(p, dtype=np.float32)
    s = p.sum(axis=1); d = p[:,0] - p[:,1]
    return np.array([p[np.argmin(s)], p[np.argmax(d)],
                     p[np.argmax(s)], p[np.argmin(d)]], dtype=np.float32)
TL, TR, BR, BL = order_corners(pts)
print(f"4 corners (1080p): TL={TL} TR={TR} BR={BR} BL={BL}")

# ──────────────────────────────────────────────
# 3. 워프 + 1080p 격자 자동 카운트 (Edge + Hough)
# ──────────────────────────────────────────────
WARP = 1200
warp_dst = np.array([[0,0],[WARP,0],[WARP,WARP],[0,WARP]], dtype=np.float32)
H_warp = cv2.getPerspectiveTransform(np.array([TL,TR,BR,BL]), warp_dst)
warped = cv2.warpPerspective(base, H_warp, (WARP, WARP))

# 워프 영역 안에서 점자블록 색만
hsv_w = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)
mask_w = cv2.inRange(hsv_w, (10, 100, 100), (35, 255, 255))
mask_w = cv2.morphologyEx(mask_w, cv2.MORPH_CLOSE, k, iterations=2)

# 점자블록 color region의 bounding rect
ys, xs = np.where(mask_w > 0)
if len(xs):
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
else:
    x0, y0, x1, y1 = 0, 0, WARP-1, WARP-1
print(f"warped tactile bbox: x[{x0}:{x1}] y[{y0}:{y1}]")

# crop & edge
crop = warped[y0:y1, x0:x1]
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
gray_blur = cv2.bilateralFilter(gray, 9, 75, 75)
edges = cv2.Canny(gray_blur, 30, 100)
# 모폴로지로 라인 강조
ek = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
edges = cv2.dilate(edges, ek, iterations=1)

# Hough
lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80,
                        minLineLength=80, maxLineGap=20)
print(f"hough lines: {0 if lines is None else len(lines)}")

# 가로/세로 분류
hor, ver = [], []
if lines is not None:
    for x1l,y1l,x2l,y2l in lines.reshape(-1, 4):
        ang = abs(np.degrees(np.arctan2(y2l-y1l, x2l-x1l)))
        if ang < 20 or ang > 160: hor.append((x1l,y1l,x2l,y2l))
        elif 70 < ang < 110:      ver.append((x1l,y1l,x2l,y2l))

hy = np.array([(l[1]+l[3])/2 for l in hor])
vx = np.array([(l[0]+l[2])/2 for l in ver])
def cluster(arr, gap):
    if len(arr) == 0: return np.array([])
    arr = np.sort(arr); g = [[arr[0]]]
    for v in arr[1:]:
        if v - g[-1][-1] < gap: g[-1].append(v)
        else: g.append([v])
    return np.array([np.mean(x) for x in g])

hy_c = cluster(hy, gap=30)
vx_c = cluster(vx, gap=30)
print(f"clustered: h={len(hy_c)}  v={len(vx_c)}")

# 인접 격자선 사이 평균 거리 → 점자블록 1칸 픽셀
dy_arr = np.diff(hy_c) if len(hy_c) > 1 else []
dx_arr = np.diff(vx_c) if len(vx_c) > 1 else []
print(f"horizontal grid spacings: {dy_arr}")
print(f"vertical   grid spacings: {dx_arr}")

# 가장 흔한 간격 = 1 점자블록 (30cm)
def auto_cell(spacings):
    if len(spacings) == 0: return None
    s = np.array(spacings)
    # 너무 큰/작은 제외
    s = s[(s > 30) & (s < 400)]
    if len(s) == 0: return None
    return float(np.median(s))

cell_y = auto_cell(dy_arr)
cell_x = auto_cell(dx_arr)
print(f"auto cell px (= 30cm): cell_x={cell_x} cell_y={cell_y}")

if True:
    # 사용자가 답한 0.9×0.6은 박스 안 좌하단 매트릭스 (3×2칸).
    # distance transform으로 매트릭스 짧은 변 두께를 측정 → 1px 환산비 자동 산출
    # → 자동 검출 박스 외곽 실제 크기 자동 계산
    import cv2 as _cv2
    _dt = _cv2.distanceTransform(mask, _cv2.DIST_L2, 5)
    _half = _dt.max()                       # 매트릭스 절반 두께 (px)
    short_px = _half * 2                    # 매트릭스 짧은 변 (px) = 0.6m
    px_per_m = short_px / 0.6               # 1m = 몇 px (1080p)
    # 박스 외곽 자동 산출
    box_w_px = np.linalg.norm(np.array([713,600])-np.array([0,600]))   # 713
    box_h_px = np.linalg.norm(np.array([0,1079])-np.array([0,600]))    # 479
    W_full_m = box_w_px / px_per_m
    H_full_m = box_h_px / px_per_m
    N_W_BLOCKS = round(W_full_m / 0.3)
    N_H_BLOCKS = round(H_full_m / 0.3)
    # 30cm 단위 반올림
    W_full_m = N_W_BLOCKS * 0.3
    H_full_m = N_H_BLOCKS * 0.3
    print(f"distance transform: 매트릭스 짧은 변 {short_px:.0f}px = 0.6m → 1m={px_per_m:.0f}px")
    print(f"박스 외곽 자동 산출: {box_w_px:.0f}x{box_h_px:.0f}px → "
          f"{N_W_BLOCKS}x{N_H_BLOCKS}칸 = {W_full_m:.2f}m x {H_full_m:.2f}m")
    # src 4 corners 외곽 직사각형 실제 크기 (사용자 확인)
    W_full_m = N_W_BLOCKS * 0.30
    H_full_m = N_H_BLOCKS * 0.30
    print(f"src 4 corners 외곽 실제 크기: {W_full_m:.2f}m x {H_full_m:.2f}m")

    # 호모그래피: 원본 픽셀 4 corner → 실제 미터
    src_orig = np.array([TL, TR, BR, BL], dtype=np.float32)
    dst = np.array([
        [0,         H_full_m],   # TL
        [W_full_m,  H_full_m],   # TR
        [W_full_m,  0       ],   # BR
        [0,         0       ],   # BL
    ], dtype=np.float32)
    H_orig = cv2.getPerspectiveTransform(src_orig, dst)

    # 블러 좌표계로 변환
    src_blur = src_orig * SCALE
    H_blur = cv2.getPerspectiveTransform(src_blur, dst)
    np.save(os.path.join(DIR, "homography.npy"), H_blur)
    np.save(os.path.join(DIR, "tactile_box.npy"), src_blur)
    print(f"\nsaved homography.npy (블러 좌표계)")

    # ──────────────────────────────────────────────
    # 4. 시각화 (1280으로 축소)
    # ──────────────────────────────────────────────
    base_small = cv2.resize(base, (1280, 720))
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), dpi=100)

    axes[0,0].imshow(cv2.cvtColor(base_small, cv2.COLOR_BGR2RGB))
    src_disp = src_orig * (1280/1920)
    poly = np.vstack([src_disp, src_disp[:1]])
    axes[0,0].plot(poly[:,0], poly[:,1], color="red", lw=2)
    axes[0,0].set_title(f"원본(1080p) 자동 4-corner\n외곽 실제 크기 {W_full_m:.2f}m x {H_full_m:.2f}m")

    axes[0,1].imshow(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))
    axes[0,1].add_patch(plt.Rectangle((x0,y0), W_px, H_px, fill=False, ec="red", lw=2))
    axes[0,1].set_title(f"워프 ({WARP}x{WARP}) + 점자블록 bbox\n{W_m:.2f}m x {H_m:.2f}m")

    axes[1,0].imshow(edges, cmap="gray")
    for x1l,y1l,x2l,y2l in hor: axes[1,0].plot([x1l,x2l],[y1l,y2l], color="red", lw=0.5)
    for x1l,y1l,x2l,y2l in ver: axes[1,0].plot([x1l,x2l],[y1l,y2l], color="cyan", lw=0.5)
    axes[1,0].set_title(f"Hough h={len(hor)} v={len(ver)}\ncell_x={cell_x:.0f}px cell_y={cell_y:.0f}px (=30cm)")

    axes[1,1].imshow(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    for y in hy_c - y0: axes[1,1].axhline(y, color="red", lw=1, alpha=0.7)
    for x in vx_c - x0: axes[1,1].axvline(x, color="cyan", lw=1, alpha=0.7)
    axes[1,1].set_title(f"검출 격자선 (h={len(hy_c)} v={len(vx_c)})")

    fig.tight_layout()
    fig.savefig(os.path.join(DIR, "auto_homography_orig.png"))
    print("saved viz:", os.path.join(DIR, "auto_homography_orig.png"))
else:
    print("[ERROR] 자동 격자 검출 실패")
