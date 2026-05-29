"""
좌하단 점자블록 매트릭스만 분리해서 진짜 사다리꼴 4 corner로 호모그래피.
사선 카메라 효과를 호모그래피가 자동 인식하도록.
매트릭스 = 0.9m × 0.6m (사용자 확인).
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

VIDEO = r"C:\Users\aaron\tagless\개찰구 촬영 영상\1\GX010193.MP4"
DIR = r"C:\Users\aaron\tagless\영상데이터"
SCALE = 720.0/1920.0
MATRIX_W = 0.9
MATRIX_H = 0.6

# ─── 1. 1080p 노란 마스크 ───
cap = cv2.VideoCapture(VIDEO)
n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
acc = None; cnt = 0
for idx in [30, n_total//4, n_total//2, 3*n_total//4, n_total-100]:
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx); ok, f = cap.read()
    if not ok: continue
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (15, 100, 100), (35, 255, 255))
    acc = m.astype(np.int32) if acc is None else acc + m.astype(np.int32)
    cnt += 1
cap.set(cv2.CAP_PROP_POS_FRAMES, 30); ok, base = cap.read(); cap.release()
mask = (acc >= (cnt*255//2)).astype(np.uint8) * 255
mask[:600, :] = 0
mask[:, 720:] = 0   # ROI 좌측 하단
k = cv2.getStructuringElement(cv2.MORPH_RECT, (7,7))
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)

# ─── 2. distance transform 으로 매트릭스(가장 두꺼운 영역) 중심 ───
dt = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
max_val = dt.max()
print(f"distance transform max: {max_val:.1f}px (= 매트릭스 절반 두께)")
# threshold: max의 60% 이상인 픽셀 = 매트릭스 코어
core_thr = max_val * 0.55
core = (dt >= core_thr).astype(np.uint8) * 255

# core를 dilate해서 매트릭스 외곽까지 복원
core_dilated = cv2.dilate(core, k, iterations=int(max_val*0.8))
matrix_mask = cv2.bitwise_and(mask, core_dilated)

# core 컨투어 → 가장 큰 영역
contours, _ = cv2.findContours(matrix_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
contours = sorted(contours, key=cv2.contourArea, reverse=True)
print(f"매트릭스 candidate contours: {len(contours)}, top area: {cv2.contourArea(contours[0]):.0f}")
matrix_c = contours[0]

# ─── 3. 매트릭스 4 corner 사다리꼴 자동 추출 ───
peri = cv2.arcLength(matrix_c, True)
trapezoid = None
for eps in np.linspace(0.005, 0.08, 50):
    approx = cv2.approxPolyDP(matrix_c, eps*peri, True)
    if len(approx) == 4:
        trapezoid = approx.reshape(-1,2).astype(np.float32)
        print(f"4-corner approxPolyDP: eps={eps:.4f}")
        break

if trapezoid is None:
    print("[WARN] 4-corner fit 실패 → minAreaRect")
    rect = cv2.minAreaRect(matrix_c)
    trapezoid = cv2.boxPoints(rect)

def order_corners(p):
    p = np.array(p, dtype=np.float32)
    s = p.sum(axis=1); d = p[:,0] - p[:,1]
    return np.array([p[np.argmin(s)], p[np.argmax(d)],
                     p[np.argmax(s)], p[np.argmin(d)]], dtype=np.float32)
TL, TR, BR, BL = order_corners(trapezoid)
print(f"\n매트릭스 사다리꼴 4 corners (1080p):")
print(f"  TL={TL}, TR={TR}, BR={BR}, BL={BL}")
print(f"  위변 폭: {np.linalg.norm(TR-TL):.0f}px,  아래변 폭: {np.linalg.norm(BR-BL):.0f}px")
print(f"  → 사다리꼴 비율 (위/아래): {np.linalg.norm(TR-TL)/np.linalg.norm(BR-BL):.3f}  "
      f"(<1이면 위쪽이 좁음 = 사선 효과 ↑)")

# ─── 4. 호모그래피 ───
src_orig = np.array([TL, TR, BR, BL], dtype=np.float32)
dst = np.array([
    [0,         MATRIX_H],   # TL
    [MATRIX_W,  MATRIX_H],   # TR
    [MATRIX_W,  0       ],   # BR
    [0,         0       ],   # BL
], dtype=np.float32)
H_orig = cv2.getPerspectiveTransform(src_orig, dst)

src_blur = src_orig * SCALE
H_blur = cv2.getPerspectiveTransform(src_blur, dst)
np.save(os.path.join(DIR, "homography.npy"), H_blur)
np.save(os.path.join(DIR, "tactile_box.npy"), src_blur)
print(f"\nsaved homography.npy")

print(f"\n호모그래피 perspective 항 g={H_orig[2,0]:.3e}, h={H_orig[2,1]:.3e}")
print(f"  (이전 minAreaRect 호모그래피는 g≈0, h≈0 → 사선 효과 무시)")

# 화면 위치별 px/cm 검증
print("\n블러 좌표 화면 다른 y에서 10px 가로 = 몇 cm?")
for y in [400, 350, 300, 250, 200, 150, 100, 50]:
    p1 = H_blur @ np.array([200, y, 1.0]); p1 = p1[:2]/p1[2]
    p2 = H_blur @ np.array([210, y, 1.0]); p2 = p2[:2]/p2[2]
    d = np.hypot(p2[0]-p1[0], p2[1]-p1[1])
    print(f"  y={y}: 10px = {d*100:.2f} cm")

# ─── 5. 시각화 ───
small = cv2.resize(base, (1280, 720))
fig, axes = plt.subplots(1, 2, figsize=(13, 5), dpi=100)
axes[0].imshow(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
sd = src_orig * (1280/1920)
poly = np.vstack([sd, sd[:1]])
axes[0].plot(poly[:,0], poly[:,1], color="red", lw=2)
for (x,y), lab in zip(sd, ["TL","TR","BR","BL"]):
    axes[0].scatter(x, y, color="red", s=30)
    axes[0].annotate(lab, (x,y), color="red", fontsize=9, xytext=(5,5),
                     textcoords="offset points")
axes[0].set_title(f"매트릭스 자동 추출 사다리꼴 ({MATRIX_W}m x {MATRIX_H}m)\n"
                  f"위/아래 폭 비 = {np.linalg.norm(TR-TL)/np.linalg.norm(BR-BL):.3f}")

xs=src_orig[:,0]; ys=src_orig[:,1]
x0=max(0,int(xs.min()-50)); x1=min(1920,int(xs.max()+50))
y0=max(0,int(ys.min()-50)); y1=min(1080,int(ys.max()+50))
crop = base[y0:y1, x0:x1].copy()
sh = src_orig - np.array([x0,y0])
poly2 = np.vstack([sh, sh[:1]]).astype(np.int32)
cv2.polylines(crop, [poly2], True, (0,0,255), 3)
ch,cw = crop.shape[:2]
target = min(900, cw)
crop_s = cv2.resize(crop, (target, int(ch*target/cw)))
axes[1].imshow(cv2.cvtColor(crop_s, cv2.COLOR_BGR2RGB))
axes[1].set_title("매트릭스 zoom + 사다리꼴 4 corner")
fig.tight_layout(); fig.savefig(os.path.join(DIR, "trapezoid.png"))
print("\nsaved viz: trapezoid.png")
