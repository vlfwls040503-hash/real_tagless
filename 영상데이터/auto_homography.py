"""
완전 자동 호모그래피
- 점자블록 영역(노란색)을 영상 객체로 검출
- polygon fit (4-corner 사다리꼴) → 사선 카메라 정확 반영
- 영역 내부 격자(점자블록 30cm 경계) Hough/morphology 검출 → 매트릭스 가로/세로 칸 수 자동 카운트
- 호모그래피 생성

전제: 점자블록 1칸 = 30cm 정사각형
"""
import os, sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

VIDEO = r"C:\Users\aaron\tagless\개찰구 촬영 영상\1\GX010193_blurred.MP4"
DIR = r"C:\Users\aaron\tagless\영상데이터"
TILE_M = 0.30   # 점자블록 한 칸 30cm

# ──────────────────────────────────────────────
# 1. 여러 프레임 누적해 노란 점자블록 마스크
# ──────────────────────────────────────────────
cap = cv2.VideoCapture(VIDEO)
n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
mask_accum = None; cnt = 0
sample_idx = [30, n_total//4, n_total//2, 3*n_total//4, n_total-100]
for idx in sample_idx:
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, frame = cap.read()
    if not ok: continue
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (18, 140, 110), (32, 255, 255))
    mask_accum = m.astype(np.int32) if mask_accum is None else mask_accum + m.astype(np.int32)
    cnt += 1
cap.set(cv2.CAP_PROP_POS_FRAMES, 30); ok, base = cap.read(); cap.release()

# majority vote (사람 등 일시적 노이즈 제거)
mask = (mask_accum >= (cnt * 255 // 2)).astype(np.uint8) * 255
roi = np.zeros_like(mask); roi[230:, :] = 255  # 게이트 단말기 영역 제외
mask = cv2.bitwise_and(mask, roi)
k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
k5 = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k5, iterations=2)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k3, iterations=1)

# ──────────────────────────────────────────────
# 2. 가장 큰 점자블록 영역 → polygon fit (사다리꼴)
# ──────────────────────────────────────────────
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
contours = sorted(contours, key=cv2.contourArea, reverse=True)
assert len(contours) > 0, "노란 점자블록 영역 없음"
c = contours[0]
print(f"largest contour area = {cv2.contourArea(c):.0f} px²")

# approxPolyDP로 4점 다각형 fit (사다리꼴 자동)
peri = cv2.arcLength(c, True)
for eps_ratio in np.linspace(0.005, 0.05, 30):
    approx = cv2.approxPolyDP(c, eps_ratio * peri, True)
    if len(approx) == 4:
        break
print(f"polygon fit: {len(approx)} corners (eps_ratio={eps_ratio:.3f})")

if len(approx) != 4:
    print("[WARN] 4-corner fit 실패 → minAreaRect로 fallback")
    rect = cv2.minAreaRect(c)
    pts = cv2.boxPoints(rect)
else:
    pts = approx.reshape(-1, 2).astype(np.float32)

# 4 corner를 TL, TR, BR, BL 순서로 정렬
def order_corners(p):
    p = np.array(p, dtype=np.float32)
    s = p.sum(axis=1); d = p[:,0] - p[:,1]
    return np.array([p[np.argmin(s)], p[np.argmax(d)],
                     p[np.argmax(s)], p[np.argmin(d)]], dtype=np.float32)
TL, TR, BR, BL = order_corners(pts)
print(f"corners (px):")
print(f"  TL={TL}, TR={TR}, BR={BR}, BL={BL}")

# ──────────────────────────────────────────────
# 3. 영역 내부 격자 자동 검출 → 점자블록 칸 수
# 방법: 영역을 직사각형으로 perspective-warp → 워프된 영역에서 가로/세로 라인 카운트
# ──────────────────────────────────────────────
# 워프 대상 크기 — 짧은 변 기준 충분히 크게
WARP_W = 400
WARP_H = 400
warp_dst = np.array([[0,0], [WARP_W,0], [WARP_W,WARP_H], [0,WARP_H]], dtype=np.float32)
H_warp = cv2.getPerspectiveTransform(np.array([TL,TR,BR,BL]), warp_dst)

# 영역 컬러 워프
warped = cv2.warpPerspective(base, H_warp, (WARP_W, WARP_H))
warped_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
# 점자블록 격자 경계는 어두운 라인 → 약간 dilate된 어두운 영역 추출
warped_blur = cv2.GaussianBlur(warped_gray, (3,3), 0)
# 적응형 thresh → 어두운 격자선 강조
adapt = cv2.adaptiveThreshold(warped_blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                              cv2.THRESH_BINARY_INV, 11, 5)

# 가로/세로 방향 1D 프로파일
profile_x = adapt.sum(axis=0)   # 각 컬럼의 어두움 합 (수직 라인 검출)
profile_y = adapt.sum(axis=1)   # 각 행의 어두움 합 (수평 라인 검출)

def find_peaks_simple(arr, min_dist):
    """단순 1D peak 검출 (지역 최대 + 최소 거리)"""
    arr = arr.astype(np.float32)
    arr_smooth = cv2.GaussianBlur(arr.reshape(-1,1), (1,11), 0).flatten()
    peaks = []
    for i in range(1, len(arr_smooth)-1):
        if arr_smooth[i] > arr_smooth[i-1] and arr_smooth[i] >= arr_smooth[i+1]:
            if not peaks or i - peaks[-1] >= min_dist:
                peaks.append(i)
            elif arr_smooth[i] > arr_smooth[peaks[-1]]:
                peaks[-1] = i
    # 임계값 (전체 평균 1.2배 이상만)
    thr = arr_smooth.mean() * 1.1
    peaks = [p for p in peaks if arr_smooth[p] > thr]
    return np.array(peaks)

# 점자블록 1칸의 픽셀(워프 후 추정) — 영역 짧은 변 기준 1/4~1/8 사이로 가정해 검색
# 실제 격자 간격 자동 추출
def estimate_grid_count(profile, label):
    L = len(profile)
    best_n = None
    best_score = -1
    # 후보 칸 수 2~10 (1칸 ≥ 30px)
    for n in range(2, 11):
        cell = L / n
        if cell < 25: break
        # n+1개의 라인 위치 (양 끝 + 격자선)
        line_positions = np.array([int(round(i*cell)) for i in range(n+1)])
        # 각 라인 위치의 +-3px 영역 어두움 합
        score = 0.0
        for lp in line_positions:
            lo = max(0, lp-3); hi = min(L, lp+4)
            score += profile[lo:hi].max()
        score /= (n+1)
        if score > best_score:
            best_score = score; best_n = n
    print(f"  {label} estimated grid count: {best_n} (score={best_score:.1f})")
    return best_n

print("\nGrid count estimation in warped region (line-projection):")
n_x = estimate_grid_count(profile_x, "horizontal direction (x)")
n_y = estimate_grid_count(profile_y, "vertical direction (y)")

# ──────────────────────────────────────────────
# 4. 호모그래피 (자동 산출 크기 적용)
# ──────────────────────────────────────────────
W_M = n_x * TILE_M   # x 가로 길이 (m)
H_M = n_y * TILE_M   # y 세로 길이 (m)
print(f"\nauto-detected matrix size: {n_x} x {n_y} blocks = {W_M:.2f} m x {H_M:.2f} m")

src = np.array([TL, TR, BR, BL], dtype=np.float32)
dst = np.array([
    [0,    H_M],   # TL
    [W_M,  H_M],   # TR
    [W_M,  0  ],   # BR
    [0,    0  ],   # BL
], dtype=np.float32)
H = cv2.getPerspectiveTransform(src, dst)
np.save(os.path.join(DIR, "homography.npy"), H)
np.save(os.path.join(DIR, "tactile_box.npy"), src)
print("\nhomography (px → m):")
print(H)

# 검증
def px2m(x, y):
    p = H @ np.array([x, y, 1.0])
    return p[:2]/p[2]
for p, exp in zip(src, dst):
    got = px2m(p[0], p[1])
    print(f"  {tuple(p)} -> ({got[0]:.3f},{got[1]:.3f}) expected {tuple(exp)}")

# ──────────────────────────────────────────────
# 5. 시각화 (검증용)
# ──────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(13, 4), dpi=100)

axes[0].imshow(cv2.cvtColor(base, cv2.COLOR_BGR2RGB))
poly = np.vstack([src, src[:1]])
axes[0].plot(poly[:,0], poly[:,1], color="red", lw=2)
for (x,y), lab in zip(src, ["TL","TR","BR","BL"]):
    axes[0].scatter(x, y, color="red", s=30)
    axes[0].annotate(lab, (x,y), color="red", fontsize=9, xytext=(4,4),
                     textcoords="offset points")
axes[0].set_title(f"점자블록 영역 polygon-fit 4 corner")

axes[1].imshow(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))
# 격자선 표시
for i in range(n_x + 1):
    axes[1].axvline(i * WARP_W / n_x, color="cyan", lw=1, alpha=0.7)
for i in range(n_y + 1):
    axes[1].axhline(i * WARP_H / n_y, color="lime", lw=1, alpha=0.7)
axes[1].set_title(f"워프된 영역 + 자동 격자\n{n_x} x {n_y} = {W_M:.2f}m x {H_M:.2f}m")

axes[2].plot(profile_x, label=f"profile_x (n_x={n_x})", color="cyan")
axes[2].plot(profile_y, label=f"profile_y (n_y={n_y})", color="lime")
axes[2].legend(fontsize=8); axes[2].set_title("워프 후 가로/세로 어두움 프로파일")

fig.tight_layout()
fig.savefig(os.path.join(DIR, "auto_homography.png"))
print("\nsaved viz:", os.path.join(DIR, "auto_homography.png"))
