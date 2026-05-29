"""
ㄴ자 점자블록 영역에서 좌하단 사각형 매트릭스(3×2칸)만 자동 분리.
강한 erosion으로 띠(폭 30cm)를 끊어 매트릭스(폭 60cm)만 살리기.
매트릭스 = 0.9m × 0.6m 가정 (사용자 확인).
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
SCALE = 720.0 / 1920.0   # 원본 → 블러 변환비

# ────── 1. 노란 점자블록 마스크 ──────
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
roi_mask = np.zeros_like(mask); roi_mask[600:, :720] = 255
mask = cv2.bitwise_and(mask, roi_mask)
k_clean = cv2.getStructuringElement(cv2.MORPH_RECT, (9,9))
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k_clean, iterations=1)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_clean, iterations=2)

# ────── 2. 강한 erosion으로 좁은 띠(30cm) 끊고 매트릭스(60cm)만 살리기 ──────
# 1080p에서 점자블록 1칸 ~110px 가정 → 띠 폭 ~110px, 매트릭스 짧은 변 ~220px
# erosion 50×50으로 띠 폭 절반(55px) 깎으면 띠는 거의 없어지고 매트릭스는 ~120×~280 남음
results = []
for ek in [30, 50, 70]:
    k_erode = cv2.getStructuringElement(cv2.MORPH_RECT, (ek, ek))
    mask_e = cv2.morphologyEx(mask, cv2.MORPH_ERODE, k_erode, iterations=1)
    sub_contours, _ = cv2.findContours(mask_e, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    sub_contours = sorted(sub_contours, key=cv2.contourArea, reverse=True)
    if sub_contours:
        c0 = sub_contours[0]
        rect = cv2.minAreaRect(c0)
        area = cv2.contourArea(c0)
        ratio = max(rect[1]) / max(min(rect[1]), 1)
        print(f"erosion {ek}px: {len(sub_contours)} sub-regions, top area={area:.0f} "
              f"size={rect[1][0]:.0f}x{rect[1][1]:.0f} ratio={ratio:.2f}")
        results.append((ek, sub_contours, c0, rect, area, ratio))

# 가장 정사각형에 가까운 가장 큰 영역 (매트릭스 3×2 비율 = 1.5)을 선택
# ratio 1.0~1.7 (정사각형~3:2) 범위에서 가장 큰 area
best = None
for ek, sc, c0, rect, area, ratio in results:
    if 1.0 <= ratio <= 1.8 and area > 5000:
        if best is None or area > best[4]:
            best = (ek, sc, c0, rect, area, ratio)

if best is None:
    print("[WARN] 매트릭스 영역 자동 분리 실패 → 기본 erosion 50px 결과 사용")
    best = results[1]

ek, sc, c0, rect, area, ratio = best
print(f"\n선택: erosion {ek}px, area={area:.0f}, "
      f"size={rect[1][0]:.0f}x{rect[1][1]:.0f}, ratio={ratio:.2f}")

# 매트릭스 erode 후 외곽 → 다시 dilate해서 원래 매트릭스 외곽 복원
k_erode = cv2.getStructuringElement(cv2.MORPH_RECT, (ek, ek))
sub_mask = np.zeros_like(mask)
cv2.drawContours(sub_mask, [c0], -1, 255, -1)
sub_mask = cv2.dilate(sub_mask, k_erode, iterations=1)
# 원본 mask와 AND
sub_mask = cv2.bitwise_and(mask, sub_mask)
sub_contours2, _ = cv2.findContours(sub_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
matrix_contour = max(sub_contours2, key=cv2.contourArea)
matrix_rect = cv2.minAreaRect(matrix_contour)
matrix_box = cv2.boxPoints(matrix_rect)
print(f"\n매트릭스 외곽 (1080p): center={matrix_rect[0]} size={matrix_rect[1]} angle={matrix_rect[2]:.1f}")
print("4 corners:")
for p in matrix_box:
    print(f"  ({p[0]:.0f}, {p[1]:.0f})")

def order_corners(p):
    p = np.array(p, dtype=np.float32)
    s = p.sum(axis=1); d = p[:,0] - p[:,1]
    return np.array([p[np.argmin(s)], p[np.argmax(d)],
                     p[np.argmax(s)], p[np.argmin(d)]], dtype=np.float32)
TL, TR, BR, BL = order_corners(matrix_box)
print(f"ordered TL={TL} TR={TR} BR={BR} BL={BL}")

# ────── 3. 호모그래피: 매트릭스 = 0.9m × 0.6m ──────
# 매트릭스 짧은 변 = 0.6m, 긴 변 = 0.9m. 어느 변이 가로/세로인지 자동 판정
W_px = np.linalg.norm(TR - TL)   # 가로 (TL→TR)
H_px = np.linalg.norm(BL - TL)   # 세로 (TL→BL)
print(f"matrix bbox px: W={W_px:.0f} H={H_px:.0f}  → ratio={W_px/H_px:.2f}")
if W_px > H_px:
    W_M, H_M = 0.9, 0.6   # 가로가 더 긴 경우
else:
    W_M, H_M = 0.6, 0.9
print(f"실제 매트릭스 크기: {W_M}m x {H_M}m (자동 판정)")

src_orig = np.array([TL, TR, BR, BL], dtype=np.float32)
dst = np.array([
    [0,    H_M],   # TL
    [W_M,  H_M],   # TR
    [W_M,  0  ],   # BR
    [0,    0  ],   # BL
], dtype=np.float32)
H_orig = cv2.getPerspectiveTransform(src_orig, dst)

# 블러 좌표계 호모그래피
src_blur = src_orig * SCALE
H_blur = cv2.getPerspectiveTransform(src_blur, dst)
np.save(os.path.join(DIR, "homography.npy"), H_blur)
np.save(os.path.join(DIR, "tactile_box.npy"), src_blur)
print("saved homography.npy")

# 검증: 매트릭스 4 corner가 정확히 dst로 매핑되는지
print("\nverify:")
for p, exp in zip(src_orig, dst):
    q = H_orig @ np.array([p[0], p[1], 1.0])
    got = q[:2]/q[2]
    print(f"  ({p[0]:.0f},{p[1]:.0f}) -> ({got[0]:.3f},{got[1]:.3f}) expected {tuple(exp)}")

# 사선 효과 추정 — 호모그래피 g, h 항
print(f"\n호모그래피 perspective 항 g={H_orig[2,0]:.2e} h={H_orig[2,1]:.2e}")
print("  |g|, |h| 클수록 사선 효과 잘 잡음 (영역 크기에 의존)")

# ────── 4. 시각화 ──────
small = cv2.resize(base, (1280, 720))
fig, axes = plt.subplots(1, 2, figsize=(13, 5), dpi=100)

axes[0].imshow(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
src_disp = src_orig * (1280/1920)
poly = np.vstack([src_disp, src_disp[:1]])
axes[0].plot(poly[:,0], poly[:,1], color="red", lw=2)
for (x,y), lab in zip(src_disp, ["TL","TR","BR","BL"]):
    axes[0].scatter(x, y, color="red", s=30)
    axes[0].annotate(lab, (x,y), color="red", fontsize=9, xytext=(5,5),
                     textcoords="offset points")
axes[0].set_title(f"자동 분리된 점자블록 매트릭스\n실제 크기 {W_M}m x {H_M}m")

# zoom in matrix area
xs = src_orig[:,0]; ys = src_orig[:,1]
x0, x1 = max(0, int(xs.min()-50)), min(1920, int(xs.max()+50))
y0, y1 = max(0, int(ys.min()-50)), min(1080, int(ys.max()+50))
crop = base[y0:y1, x0:x1].copy()
shifted = src_orig - np.array([x0, y0])
poly2 = np.vstack([shifted, shifted[:1]]).astype(np.int32)
cv2.polylines(crop, [poly2], True, (0,0,255), 3)
ch, cw = crop.shape[:2]
target_w = min(900, cw)
crop_small = cv2.resize(crop, (target_w, int(ch*target_w/cw)))
axes[1].imshow(cv2.cvtColor(crop_small, cv2.COLOR_BGR2RGB))
axes[1].set_title(f"매트릭스 zoom (이 사각형이 {W_M}m x {H_M}m 점자블록 영역)")

fig.tight_layout()
fig.savefig(os.path.join(DIR, "matrix_extracted.png"))
print("saved viz: matrix_extracted.png")
