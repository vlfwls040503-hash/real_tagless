"""
점자블록 4 코너 → 호모그래피 매트릭스 생성.
가정: 좌측 하단 노란 영역 = 정사각형 점자블록 매트릭스 1.2m × 1.2m (4x4 grid, 한 변 30cm).
다른 크기면 TILE_SIZE_M 만 바꾸면 됨.
"""
import os, sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import numpy as np
import cv2

DIR = r"C:\Users\aaron\tagless\영상데이터"
TILE_SIZE_M = 1.2   # 점자블록 매트릭스 한 변 길이 (m). 4x4 = 1.2m. 5x5 = 1.5m 등.

box = np.load(os.path.join(DIR, "tactile_box.npy"))   # 4 corners (px), boxPoints 순서
print("loaded corners (px):")
for p in box: print(f"  ({p[0]:.1f}, {p[1]:.1f})")

# boxPoints 순서: 회전 사각형, 시계 또는 반시계. 정렬해서 (좌상, 우상, 우하, 좌하)로.
def order_corners(pts):
    pts = np.array(pts, dtype=np.float32)
    # 좌상: x+y 최소, 우하: x+y 최대
    # 우상: x-y 최대, 좌하: x-y 최소
    s = pts.sum(axis=1)
    d = pts[:,0] - pts[:,1]
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmax(d)]
    bl = pts[np.argmin(d)]
    return np.array([tl, tr, br, bl], dtype=np.float32)

src = order_corners(box)
print("ordered (TL, TR, BR, BL):")
for p in src: print(f"  ({p[0]:.1f}, {p[1]:.1f})")

# 실제 좌표(미터). y는 카메라에서 멀어지는 방향(영상 위쪽 = y 큼)
# TL = (0, TILE_SIZE_M), TR = (TILE_SIZE_M, TILE_SIZE_M), BR = (TILE_SIZE_M, 0), BL = (0, 0)
dst = np.array([
    [0,            TILE_SIZE_M],  # TL
    [TILE_SIZE_M,  TILE_SIZE_M],  # TR
    [TILE_SIZE_M,  0          ],  # BR
    [0,            0          ],  # BL
], dtype=np.float32)

H = cv2.getPerspectiveTransform(src, dst)
print("\nHomography matrix H (px → m):")
print(H)
np.save(os.path.join(DIR, "homography.npy"), H)
print("saved:", os.path.join(DIR, "homography.npy"))

# 검증: 원본 점들을 H로 변환한 결과
def px2m(pt):
    p = np.array([pt[0], pt[1], 1.0])
    q = H @ p
    return q[:2] / q[2]
print("\nverify (each src corner → m):")
for p, expected in zip(src, dst):
    got = px2m(p)
    print(f"  ({p[0]:.1f},{p[1]:.1f}) -> ({got[0]:.3f},{got[1]:.3f}) expected ({expected[0]},{expected[1]})")

# 화면 다른 위치에서 px/m 비율 추정
print("\nm/px estimates at different screen y (using head/foot ranges):")
for y in [400, 350, 300, 250, 200, 150, 100]:
    p1 = px2m([300, y])
    p2 = px2m([300+10, y])
    dx_m = abs(p2[0] - p1[0])
    print(f"  y={y}: 10px (가로) ≈ {dx_m*100:.1f} cm")
