"""원본 1080p 영상의 점자블록 zoom + 자동 검출 박스 시각화"""
import os, cv2, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

VIDEO = r"C:\Users\aaron\tagless\개찰구 촬영 영상\1\GX010193.MP4"
DIR = r"C:\Users\aaron\tagless\영상데이터"

# 자동 검출된 4 corner (블러 좌표계) → 원본 좌표계로
src_blur = np.load(os.path.join(DIR, "tactile_box.npy"))
src_orig = src_blur * (1920.0/720.0)
print("자동 검출 4 corner (1080p):")
for p in src_orig: print(f"  ({p[0]:.0f}, {p[1]:.0f})")

cap = cv2.VideoCapture(VIDEO)
cap.set(cv2.CAP_PROP_POS_FRAMES, 30); ok, frame = cap.read(); cap.release()

# zoom 영역: 자동 박스 약간 여유 두고
xs = src_orig[:,0]; ys = src_orig[:,1]
x0, x1 = max(0, int(xs.min()-30)), min(frame.shape[1], int(xs.max()+30))
y0, y1 = max(0, int(ys.min()-30)), min(frame.shape[0], int(ys.max()+30))
crop = frame[y0:y1, x0:x1].copy()

# 박스 그리기
shifted = src_orig - np.array([x0, y0])
poly = np.vstack([shifted, shifted[:1]]).astype(np.int32)
cv2.polylines(crop, [poly], True, (0,0,255), 3)
labels = ["TL","TR","BR","BL"]
for (x,y), lab in zip(shifted, labels):
    cv2.circle(crop, (int(x), int(y)), 8, (0,0,255), -1)
    cv2.putText(crop, lab, (int(x)+12, int(y)-5), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (0,0,255), 2)

# 출력 시 800px 이하로 축소
ch, cw = crop.shape[:2]
target_w = min(900, cw)
crop_small = cv2.resize(crop, (target_w, int(ch*target_w/cw)))
cv2.imwrite(os.path.join(DIR, "tactile_with_box.jpg"), crop_small,
            [cv2.IMWRITE_JPEG_QUALITY, 90])
print(f"saved: {os.path.join(DIR, 'tactile_with_box.jpg')}  size {crop_small.shape}")
print(f"\n자동 검출된 외곽 직사각형 (1080p):")
print(f"  가로 (TL→TR) : {np.linalg.norm(src_orig[1]-src_orig[0]):.0f} px")
print(f"  세로 (TL→BL) : {np.linalg.norm(src_orig[3]-src_orig[0]):.0f} px")
