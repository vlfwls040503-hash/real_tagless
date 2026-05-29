"""
영상 첫 프레임에서 노란 점자블록 영역을 자동 추출.
점자블록 한 변 30cm 가정 → 호모그래피 4점 매핑.
"""
import os, cv2, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

VIDEO = r"C:\Users\aaron\tagless\개찰구 촬영 영상\1\GX010193_blurred.MP4"
OUT_DIR = r"C:\Users\aaron\tagless\영상데이터"

# 여러 프레임에서 노란 마스크를 누적해 robust하게 잡기
cap = cv2.VideoCapture(VIDEO)
n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

mask_accum = None
frames_used = 0
for idx in [30, n_total//4, n_total//2, 3*n_total//4, n_total-100]:
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, frame = cap.read()
    if not ok:
        continue
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # 진한 노란색만 (점자블록 자체. 게이트 단말기/표시등 제외)
    m = cv2.inRange(hsv, (18, 140, 110), (32, 255, 255))
    if mask_accum is None:
        mask_accum = m.astype(np.int32)
    else:
        mask_accum += m.astype(np.int32)
    frames_used += 1
cap.release()
mask_accum = (mask_accum >= (frames_used * 255 // 2)).astype(np.uint8) * 255

# 화면 아래쪽 (점자블록만)
H, W = mask_accum.shape
roi = np.zeros_like(mask_accum)
roi[230:, :] = 255   # 게이트 단말기 위쪽 제외
mask_accum = cv2.bitwise_and(mask_accum, roi)

# morphology
kernel3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
kernel5 = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
mask = cv2.morphologyEx(mask_accum, cv2.MORPH_CLOSE, kernel5, iterations=2)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel3, iterations=1)

# 연결 구성
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
contours = sorted(contours, key=cv2.contourArea, reverse=True)
print(f"contours found: {len(contours)}")
for i, c in enumerate(contours[:5]):
    print(f"  #{i} area={cv2.contourArea(c):.0f}")

# 첫 프레임 가져와서 시각화
cap = cv2.VideoCapture(VIDEO)
cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
ok, base = cap.read()
cap.release()

fig, axes = plt.subplots(1, 2, figsize=(10, 4), dpi=100)
axes[0].imshow(cv2.cvtColor(base, cv2.COLOR_BGR2RGB))
axes[0].imshow(mask, alpha=0.4, cmap="autumn")
axes[0].set_title("노란색 마스크 (점자블록)")

axes[1].imshow(cv2.cvtColor(base, cv2.COLOR_BGR2RGB))
for i, c in enumerate(contours[:5]):
    rect = cv2.minAreaRect(c)
    box = cv2.boxPoints(rect)
    axes[1].plot(np.append(box[:,0], box[0,0]),
                 np.append(box[:,1], box[0,1]),
                 lw=1.5, label=f"#{i} area={cv2.contourArea(c):.0f}")
axes[1].legend(fontsize=7)
axes[1].set_title("minAreaRect (큰 영역 5개)")
fig.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "tactile_mask.png"))
print("saved:", os.path.join(OUT_DIR, "tactile_mask.png"))

# 가장 큰 컨투어의 minAreaRect 정보 저장
if contours:
    rect = cv2.minAreaRect(contours[0])
    box = cv2.boxPoints(rect)
    print("\nLargest yellow region (top contour):")
    print(f"  center : ({rect[0][0]:.1f}, {rect[0][1]:.1f})")
    print(f"  size   : {rect[1][0]:.1f} x {rect[1][1]:.1f} px")
    print(f"  angle  : {rect[2]:.1f} deg")
    print(f"  corners (px):")
    for p in box:
        print(f"    ({p[0]:.1f}, {p[1]:.1f})")
    np.save(os.path.join(OUT_DIR, "tactile_box.npy"), box)
    np.save(os.path.join(OUT_DIR, "tactile_rect.npy"),
            np.array([rect[0][0], rect[0][1], rect[1][0], rect[1][1], rect[2]]))
