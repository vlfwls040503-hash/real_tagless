"""호모그래피 src 박스 + x/y 축을 영상 위에 그려서 사용자가 크기 확인."""
import os, cv2, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

VIDEO = r"C:\Users\aaron\tagless\개찰구 촬영 영상\1\GX010193_blurred.MP4"
DIR = r"C:\Users\aaron\tagless\영상데이터"

box = np.load(os.path.join(DIR, "tactile_box.npy"))   # boxPoints
# 이미 homography.py에서 정렬한 순서 (TL, TR, BR, BL) 다시 적용
def order_corners(pts):
    pts = np.array(pts, dtype=np.float32)
    s = pts.sum(axis=1); d = pts[:,0] - pts[:,1]
    return np.array([pts[np.argmin(s)], pts[np.argmax(d)],
                     pts[np.argmax(s)], pts[np.argmin(d)]], dtype=np.float32)
corners = order_corners(box)   # TL, TR, BR, BL
labels = ["TL", "TR", "BR", "BL"]

cap = cv2.VideoCapture(VIDEO)
cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
ok, base = cap.read()
cap.release()

fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
ax.imshow(cv2.cvtColor(base, cv2.COLOR_BGR2RGB))
poly = np.vstack([corners, corners[:1]])
ax.plot(poly[:,0], poly[:,1], color="red", lw=2)
for (x,y), lab in zip(corners, labels):
    ax.scatter(x, y, color="red", s=30, zorder=5)
    ax.annotate(f"{lab}\n({x:.0f},{y:.0f})", (x,y), color="red",
                fontsize=8, xytext=(5,5), textcoords="offset points")

# x, y 축 화살표 (TL/BL/TR 코너 활용)
TL, TR, BR, BL = corners
# x 축: TL → TR (가로 방향)
ax.annotate("", xy=(TR[0], TR[1]), xytext=(TL[0], TL[1]),
            arrowprops=dict(arrowstyle="->", color="cyan", lw=2))
ax.text((TL[0]+TR[0])/2, (TL[1]+TR[1])/2 - 6, "x (가로)", color="cyan",
        fontsize=10, ha="center", weight="bold")
# y 축: BL → TL (보행 방향, 카메라에서 멀어짐)
ax.annotate("", xy=(TL[0], TL[1]), xytext=(BL[0], BL[1]),
            arrowprops=dict(arrowstyle="->", color="lime", lw=2))
ax.text(BL[0] - 25, (BL[1]+TL[1])/2, "y\n(세로)", color="lime",
        fontsize=10, ha="center", weight="bold")

ax.set_xlim(0, base.shape[1]); ax.set_ylim(base.shape[0], 0)
ax.set_title("자동 검출된 점자블록 매트릭스 박스 + 호모그래피 x/y 축\n"
             "→ 이 박스가 가로 몇 개 × 세로 몇 개의 30cm 블록인가요?")
fig.tight_layout()
fig.savefig(os.path.join(DIR, "homography_box.png"))
print("saved:", os.path.join(DIR, "homography_box.png"))
