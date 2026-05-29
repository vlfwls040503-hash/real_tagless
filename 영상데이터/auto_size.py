"""
워프된 영역 안에서 점자블록(주황) 마스크를 다시 잡아 정확한 매트릭스 외곽 + 칸 수 자동 산출.
선형 점자블록의 막대 줄무늬를 morphology로 카운트.
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
# 여러 프레임 누적
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
mask = cv2.inRange(hsv, (10, 80, 80), (35, 255, 255))
k = cv2.getStructuringElement(cv2.MORPH_RECT, (7,7))
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)

# 점자블록 정확한 외곽 = 마스크의 boundingRect (워프 후이므로 직사각형)
ys, xs = np.where(mask > 0)
if len(xs) == 0:
    print("[ERROR] 워프 후 점자블록 색 검출 실패")
    sys.exit(1)
x0, x1 = xs.min(), xs.max()
y0, y1 = ys.min(), ys.max()
W_px = x1 - x0
H_px = y1 - y0
print(f"워프 후 점자블록 마스크 bbox: x=[{x0},{x1}] y=[{y0},{y1}]")
print(f"  실제 영역 크기: {W_px} x {H_px} px")

# 워프 영상은 src 4점이 (0,0)~(WARP,WARP)로 매핑됨.
# src 영역의 실제 미터 길이는 모름. 하지만 워프된 마스크의 비율로 가로:세로 비율은 정확.
# 점자블록은 30cm 정사각형 → 가로/세로 칸 수 = W_px / cell_px, H_px / cell_px (cell_px 동일)
# cell_px 자동 추정: 워프 영상에서 점자블록 막대 줄무늬를 검출

# 막대 검출 — 워프 영상의 점자블록 영역만 추출
crop = warped[y0:y1, x0:x1]
crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
# Sobel로 가로/세로 edge 강조
sx = cv2.Sobel(crop_gray, cv2.CV_32F, 1, 0, ksize=3)
sy = cv2.Sobel(crop_gray, cv2.CV_32F, 0, 1, ksize=3)
abs_sx = cv2.convertScaleAbs(sx)
abs_sy = cv2.convertScaleAbs(sy)

# 가로 edge 프로파일 (각 행의 가로 edge 합) — 막대가 가로면 행 사이에 강한 변화
prof_h = abs_sy.sum(axis=1).astype(np.float32)   # 행별 세로 edge 강도(가로 막대 사이 어두움)
prof_w = abs_sx.sum(axis=0).astype(np.float32)
# 정규화
prof_h = (prof_h - prof_h.min()) / (prof_h.max() - prof_h.min() + 1e-6)
prof_w = (prof_w - prof_w.min()) / (prof_w.max() - prof_w.min() + 1e-6)

# 자동 주기 검출 - FFT
def dominant_period(profile):
    p = profile - profile.mean()
    # 자기상관
    n = len(p)
    ac = np.correlate(p, p, mode="full")[n-1:]
    ac = ac / (ac[0] + 1e-9)
    # 첫 피크 (lag>5)
    for k in range(5, len(ac)-1):
        if ac[k] > ac[k-1] and ac[k] >= ac[k+1] and ac[k] > 0.1:
            return k, ac
    return None, ac

per_h, ac_h = dominant_period(prof_h)
per_w, ac_w = dominant_period(prof_w)
print(f"막대 줄무늬 자동 주기:")
print(f"  세로 방향(행): {per_h} px")
print(f"  가로 방향(열): {per_w} px")

# 점자블록 1칸 30cm 안에 막대 5개 → 막대 주기 ≈ 30/5 = 6cm
# 즉 px → cm 환산: 6cm / per_px
result = {}
if per_h is not None and per_h > 0:
    cm_per_px_h = 6.0 / per_h
    H_cm = H_px * cm_per_px_h
    nH = round(H_cm / 30)
    print(f"  → 세로 길이 {H_cm:.1f}cm = {H_cm/30:.2f} 점자블록 칸 (반올림 {nH})")
    result["H"] = nH
if per_w is not None and per_w > 0:
    cm_per_px_w = 6.0 / per_w
    W_cm = W_px * cm_per_px_w
    nW = round(W_cm / 30)
    print(f"  → 가로 길이 {W_cm:.1f}cm = {W_cm/30:.2f} 점자블록 칸 (반올림 {nW})")
    result["W"] = nW

# 시각화
fig, axes = plt.subplots(2, 2, figsize=(11, 8), dpi=100)
axes[0,0].imshow(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))
axes[0,0].add_patch(plt.Rectangle((x0,y0), W_px, H_px, fill=False, ec="red", lw=2))
axes[0,0].set_title(f"워프 후 점자블록 영역 bbox\n{W_px} x {H_px} px")

axes[0,1].imshow(crop_gray, cmap="gray")
axes[0,1].set_title("점자블록 crop (gray)")

axes[1,0].plot(prof_h, label=f"prof_h (period {per_h}px)")
axes[1,0].plot(prof_w, label=f"prof_w (period {per_w}px)")
axes[1,0].legend(fontsize=8); axes[1,0].set_title("막대 줄무늬 프로파일")

axes[1,1].plot(ac_h, label="ac_h", color="C0")
axes[1,1].plot(ac_w, label="ac_w", color="C1")
if per_h: axes[1,1].axvline(per_h, color="C0", ls="--")
if per_w: axes[1,1].axvline(per_w, color="C1", ls="--")
axes[1,1].legend(fontsize=8); axes[1,1].set_title("자기상관 (peak = 막대 주기)")
fig.tight_layout()
fig.savefig(os.path.join(DIR, "auto_size.png"))
print("saved:", os.path.join(DIR, "auto_size.png"))

# 결과 저장 (analyze.py에서 읽어가도록)
if "W" in result and "H" in result and result["W"] > 0 and result["H"] > 0:
    np.save(os.path.join(DIR, "tactile_blocks.npy"),
            np.array([result["W"], result["H"]]))
    print(f"\n점자블록 매트릭스 자동 산출: {result['W']} x {result['H']} 칸 "
          f"= {result['W']*0.3:.2f}m x {result['H']*0.3:.2f}m")
