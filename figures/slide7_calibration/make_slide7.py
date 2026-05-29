"""
졸업 작품 중간 발표 PPT - Slide 7 (방법론 - 데이터 캘리브레이션) 시각자료 3종
가로 스트립 배치를 위해 모두 1200×600px로 통일
"""
import os, sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

import numpy as np
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

OUT_DIR = r"C:\Users\aaron\tagless\figures\slide7_calibration"
os.makedirs(OUT_DIR, exist_ok=True)

# ─── 공통 출력 사양 ───
DPI = 300
FIGSIZE = (4.0, 2.25)  # 4×2.25 in × 300dpi = 1200×675 px (영상 720×404 비율 ≈ 1.78 일치)

# ─── 색상 팔레트 (학술 논문 스타일) ───
COLOR_TAG     = "#4A6FA5"   # 차분한 파랑
COLOR_TAGLESS = "#E76F51"   # 강조 주황
COLOR_BBOX    = "#2E86AB"
COLOR_GATE_RO = "#F18F01"
COLOR_WALL    = "#2D3142"
COLOR_AREA    = "#F5F5F5"
COLOR_GATE    = "#4A6FA5"
COLOR_ESC     = "#86BBD8"
COLOR_DIM     = "#888888"


# =====================================================================
# 1. 서비스 시간 분포 히스토그램 (태그 vs 태그리스)
# =====================================================================
def fig1_service_time(tag_data=None, tagless_data=None,
                      out_path=None,
                      tag_mean=2.4, tag_std=1.4,
                      tagless_mean=1.2, tagless_std=0.2,
                      n=200):
    """
    영상 분석으로 추출한 게이트 통과 서비스 시간 분포.
    tag_data, tagless_data: numpy 1D array. None이면 표 값 기반 가상 데이터.
      - 태그   : lognormal (μ=2.4s, σ=1.4s) — Gao 2019 형태
      - 태그리스: normal (μ=1.2s, σ=0.2s)
    """
    if tag_data is None:
        rng = np.random.default_rng(42)
        # lognormal 파라미터 변환: 표본 mean=tag_mean, std=tag_std에 맞춤
        mu_log = np.log(tag_mean**2 / np.sqrt(tag_std**2 + tag_mean**2))
        sigma_log = np.sqrt(np.log(1 + tag_std**2 / tag_mean**2))
        tag_data = rng.lognormal(mu_log, sigma_log, n)
    if tagless_data is None:
        rng = np.random.default_rng(7)
        tagless_data = rng.normal(tagless_mean, tagless_std, n).clip(0.1)

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    bins = np.linspace(0, 7, 36)   # 태그 lognormal 꼬리 수용
    ax.hist(tag_data, bins=bins, alpha=0.55, color=COLOR_TAG,
            edgecolor=COLOR_TAG, linewidth=0.6, density=True,
            label=f"태그 (n={len(tag_data)})")
    ax.hist(tagless_data, bins=bins, alpha=0.55, color=COLOR_TAGLESS,
            edgecolor=COLOR_TAGLESS, linewidth=0.6, density=True,
            label=f"태그리스 (n={len(tagless_data)})")

    # 평균 수직선 (표 값 기준)
    ax.axvline(tag_mean,     color=COLOR_TAG,     linestyle="--", linewidth=1.0)
    ax.axvline(tagless_mean, color=COLOR_TAGLESS, linestyle="--", linewidth=1.0)

    # 평균 라벨 (PPT 표 값 그대로)
    y_top = ax.get_ylim()[1]
    ax.text(tag_mean + 0.10, y_top * 0.78,
            f"태그 평균\n{tag_mean:.1f} s\n(σ={tag_std:.1f})",
            color=COLOR_TAG, fontsize=7, weight="bold", va="top")
    ax.text(tagless_mean - 1.10, y_top * 0.78,
            f"태그리스 평균\n{tagless_mean:.1f} s\n(σ={tagless_std:.1f})",
            color=COLOR_TAGLESS, fontsize=7, weight="bold", va="top")

    ax.set_xlabel("서비스 시간 (s)", fontsize=8)
    ax.set_ylabel("확률밀도", fontsize=8)
    ax.tick_params(axis="both", labelsize=7)
    ax.legend(loc="upper right", fontsize=7, frameon=False)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#bbb")
    ax.spines["bottom"].set_color("#bbb")
    ax.grid(False)

    fig.tight_layout(pad=0.5)
    out = out_path or os.path.join(OUT_DIR, "fig7_1_service_time.png")
    fig.savefig(out, dpi=DPI, transparent=True)
    plt.close(fig)
    print(f"[1] saved: {out}")
    return out


# =====================================================================
# 2. (NEW) YOLOv8 + ByteTrack 트래킹 궤적 + ID/속도 라벨 시각화
# =====================================================================
def fig2_trajectories(
    video_path=r"C:\Users\aaron\tagless\개찰구 촬영 영상\1\GX010193_blurred.MP4",
    tracks_csv=r"C:\Users\aaron\tagless\영상데이터\tracks_full.csv",
    t_sec=675.0,                    # 11분 15초
    out_path=None,
):
    """11분 15초 경 프레임에 검출된 사람들의 bbox + 라벨만. 궤적 없음."""
    import cv2, pandas as pd

    out = out_path or os.path.join(OUT_DIR, "fig7_2_field_capture.png")

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_idx = int(t_sec * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    cap.release()
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    H, W = rgb.shape[:2]

    # 해당 프레임의 트래킹 검출들
    tracks = pd.read_csv(tracks_csv)
    tol = 0.05  # ±0.05초 안의 행
    detections = tracks[(tracks.t_sec >= t_sec - tol) & (tracks.t_sec <= t_sec + tol)]
    # 가장 가까운 단일 프레임만
    if len(detections):
        target_t = detections.t_sec.iloc[(detections.t_sec - t_sec).abs().argmin()]
        detections = detections[detections.t_sec == target_t]
    print(f"  t={t_sec}s (frame {frame_idx}) 검출 {len(detections)}명")

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    ax.imshow(rgb)

    BBOX_COLOR = "#3D6FA8"

    for i, (_, row) in enumerate(detections.iterrows(), start=1):
        x1, y1, x2, y2 = row["x1"], row["y1"], row["x2"], row["y2"]
        ax.add_patch(plt.Rectangle((x1, y1), x2-x1, y2-y1, fill=False,
                                    edgecolor=BBOX_COLOR, linewidth=1.2,
                                    zorder=3))
        # ID 라벨 (bbox 상단)
        ax.text(x1, y1-3, f"{i}", fontsize=7, color="white", weight="bold",
                ha="left", va="bottom",
                bbox=dict(boxstyle="round,pad=0.2", fc=BBOX_COLOR,
                          ec="none", alpha=0.95),
                zorder=4)

    ax.set_xlim(0, W); ax.set_ylim(H, 0)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    fig.tight_layout(pad=0)
    fig.savefig(out, dpi=DPI, transparent=False)
    plt.close(fig)
    print(f"[2] saved: {out}")
    return out


# =====================================================================
# 2-old. 현장 촬영 프레임 시각화 (사람 검출 + 얼굴 블러 + bbox + 게이트 ROI)
# =====================================================================
def fig2_field_capture(image_path=None, video_path=None, frame_idx=0,
                        gate_roi=None, out_path=None,
                        yolo_model="yolov8n.pt", conf=0.4):
    """
    현장 영상/이미지 → YOLOv8 사람 검출 → 얼굴 가우시안 블러
                  + bbox 표시 + 게이트 영역 어노테이션.

    image_path or video_path: 입력 (둘 중 하나)
    frame_idx: 영상에서 추출할 프레임 번호 (video_path 사용 시)
    gate_roi: (x, y, w, h) 게이트 통과 영역 박스 좌표 (px)
    """
    out = out_path or os.path.join(OUT_DIR, "fig7_2_field_capture.png")

    # 입력 없을 때 placeholder
    if image_path is None and video_path is None:
        fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
        canvas = np.full((600, 1200, 3), 0.92)
        ax.imshow(canvas, aspect="auto")
        ax.text(600, 280,
                "[현장 촬영 프레임]",
                ha="center", va="center", fontsize=14,
                color="#444", weight="bold")
        ax.text(600, 340,
                "image_path 또는 video_path 인자에 영상 경로 입력 시 활성화\n"
                "YOLOv8 사람 검출 → 얼굴 가우시안 블러 → bbox + 게이트 ROI",
                ha="center", va="center", fontsize=8, color="#666")
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values(): s.set_visible(False)
        fig.tight_layout(pad=0)
        fig.savefig(out, dpi=DPI, transparent=False)
        plt.close(fig)
        print(f"[2] saved (placeholder): {out}")
        return out

    # 실제 처리
    import cv2
    from ultralytics import YOLO

    if image_path:
        frame = cv2.imread(image_path)
        if frame is None:
            raise FileNotFoundError(image_path)
    else:
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError(f"frame {frame_idx} read failed")

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).copy()
    H, W = rgb.shape[:2]

    # YOLO 사람 검출
    model = YOLO(yolo_model)
    results = model(frame, classes=[0], conf=conf, verbose=False)[0]

    boxes = []
    if results.boxes is not None and len(results.boxes) > 0:
        boxes = results.boxes.xyxy.cpu().numpy().astype(int).tolist()

    # 얼굴(상단 1/3) 가우시안 블러
    for x1, y1, x2, y2 in boxes:
        head_h = max(1, (y2 - y1) // 3)
        face = rgb[y1:y1+head_h, x1:x2]
        if face.size > 0:
            k = max(11, (min(face.shape[0], face.shape[1]) // 2) | 1)
            blurred = cv2.GaussianBlur(face, (k, k), 0)
            rgb[y1:y1+head_h, x1:x2] = blurred

    # plot
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    ax.imshow(rgb)

    # bbox
    for x1, y1, x2, y2 in boxes:
        ax.add_patch(plt.Rectangle((x1, y1), x2-x1, y2-y1, fill=False,
                                    edgecolor=COLOR_BBOX, linewidth=0.8))

    # 게이트 ROI
    if gate_roi is not None:
        gx, gy, gw, gh = gate_roi
        ax.add_patch(plt.Rectangle((gx, gy), gw, gh, fill=False,
                                    edgecolor=COLOR_GATE_RO, linewidth=1.6,
                                    linestyle="--"))
        ax.text(gx + gw/2, max(0, gy - 8),
                "게이트 통과 영역",
                ha="center", color=COLOR_GATE_RO, fontsize=8, weight="bold")

    # 검출 결과 라벨
    ax.text(10, 20, f"YOLOv8 검출: {len(boxes)} 명",
            color="white", fontsize=8, weight="bold",
            bbox=dict(boxstyle="round,pad=0.3", fc=COLOR_BBOX, ec="none", alpha=0.85))

    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    fig.tight_layout(pad=0)
    fig.savefig(out, dpi=DPI, transparent=False)
    plt.close(fig)
    print(f"[2] saved: {out}  (boxes: {len(boxes)})")
    return out


# =====================================================================
# 3. 성수역 서쪽 대합실 평면도 (top-down)
# =====================================================================
def fig3_floorplan(layout=None, out_path=None):
    """
    성수역 서쪽 대합실 평면도.
    layout: dict (placeholder 값을 사용자 실측치로 덮어쓰기)
        - hall_w, hall_h            : 대합실 가로/세로 (m)
        - n_gates                   : 게이트 수 (기본 6)
        - gate_w, gate_d            : 게이트 폭/깊이 (m)
        - gate_y, gate_x_start, gate_x_gap
        - esc_x, esc_y, esc_w, esc_h: 에스컬레이터
    """
    L = dict(
        hall_w=50.0, hall_h=25.0,
        n_gates=6, gate_w=0.55, gate_d=1.5,
        gate_y=12.5, gate_x_start=8.0, gate_x_gap=2.0,
        esc_x=42.0, esc_y=10.0, esc_w=4.0, esc_h=5.0,
    )
    if layout: L.update(layout)

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)

    # 외곽 + 영역 음영
    ax.add_patch(plt.Rectangle((0, 0), L["hall_w"], L["hall_h"], fill=True,
                                facecolor=COLOR_AREA, edgecolor=COLOR_WALL,
                                linewidth=1.2, zorder=1))

    # 게이트
    for i in range(L["n_gates"]):
        gx = L["gate_x_start"] + i * (L["gate_w"] + L["gate_x_gap"])
        ax.add_patch(plt.Rectangle((gx, L["gate_y"] - L["gate_d"]/2),
                                    L["gate_w"], L["gate_d"],
                                    fill=True, facecolor=COLOR_GATE,
                                    edgecolor=COLOR_WALL, linewidth=0.4,
                                    zorder=3))
        ax.text(gx + L["gate_w"]/2, L["gate_y"], f"G{i+1}",
                ha="center", va="center", fontsize=4.5,
                color="white", weight="bold", zorder=4)

    # 에스컬레이터
    ex, ey, ew, eh = L["esc_x"], L["esc_y"], L["esc_w"], L["esc_h"]
    ax.add_patch(plt.Rectangle((ex, ey), ew, eh, fill=True,
                                facecolor=COLOR_ESC, edgecolor=COLOR_WALL,
                                linewidth=0.8, zorder=2))
    # 에스컬레이터 화살표 (위로 진입)
    ax.annotate("", xy=(ex + ew/2, ey + eh - 0.3),
                xytext=(ex + ew/2, ey + 0.3),
                arrowprops=dict(arrowstyle="->", color=COLOR_WALL, lw=0.8),
                zorder=4)
    ax.text(ex + ew/2, ey + eh + 0.5, "에스컬레이터",
            ha="center", fontsize=6, color=COLOR_WALL, zorder=4)

    # 출입구 화살표 (좌측 상하)
    ax.annotate("", xy=(2, L["hall_h"] - 0.5), xytext=(2, L["hall_h"] + 1.5),
                arrowprops=dict(arrowstyle="->", color=COLOR_DIM, lw=1.0))
    ax.text(2, L["hall_h"] + 2.0, "출구", ha="center", fontsize=6,
            color=COLOR_DIM)
    ax.annotate("", xy=(2, 0.5), xytext=(2, -1.5),
                arrowprops=dict(arrowstyle="->", color=COLOR_DIM, lw=1.0))
    ax.text(2, -2.0, "입구", ha="center", fontsize=6, color=COLOR_DIM,
            va="top")

    # 가로 치수
    ax.annotate("", xy=(0, -3.0), xytext=(L["hall_w"], -3.0),
                arrowprops=dict(arrowstyle="<->", color=COLOR_DIM, lw=0.7))
    ax.text(L["hall_w"]/2, -3.6, f"{L['hall_w']:.1f} m",
            ha="center", va="top", fontsize=6, color=COLOR_DIM)
    # 세로 치수
    ax.annotate("", xy=(L["hall_w"] + 1.5, 0),
                xytext=(L["hall_w"] + 1.5, L["hall_h"]),
                arrowprops=dict(arrowstyle="<->", color=COLOR_DIM, lw=0.7))
    ax.text(L["hall_w"] + 2.3, L["hall_h"]/2, f"{L['hall_h']:.1f} m",
            ha="left", va="center", fontsize=6, color=COLOR_DIM, rotation=90)
    # 게이트 폭 라벨
    ax.text(L["gate_x_start"] + 2, L["gate_y"] - L["gate_d"]/2 - 1.0,
            f"게이트 폭 {int(L['gate_w']*1000)} mm",
            fontsize=5.5, color=COLOR_DIM)
    # 게이트-에스컬레이터 거리
    last_gx = L["gate_x_start"] + (L["n_gates"]-1)*(L["gate_w"] + L["gate_x_gap"]) + L["gate_w"]
    ax.annotate("", xy=(last_gx, L["gate_y"] + L["gate_d"]/2 + 1.5),
                xytext=(ex, L["gate_y"] + L["gate_d"]/2 + 1.5),
                arrowprops=dict(arrowstyle="<->", color=COLOR_DIM, lw=0.7))
    ax.text((last_gx + ex)/2, L["gate_y"] + L["gate_d"]/2 + 2.2,
            f"{ex - last_gx:.1f} m", ha="center", fontsize=5.5, color=COLOR_DIM)

    ax.set_xlim(-3, L["hall_w"] + 5)
    ax.set_ylim(-5, L["hall_h"] + 4)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)

    fig.tight_layout(pad=0.3)
    out = out_path or os.path.join(OUT_DIR, "fig7_3_floorplan.png")
    fig.savefig(out, dpi=DPI, transparent=True)
    plt.close(fig)
    print(f"[3] saved: {out}")
    return out


# =====================================================================
# main
# =====================================================================
if __name__ == "__main__":
    fig1_service_time()
    fig2_trajectories()        # YOLOv8+ByteTrack 트래킹 궤적 + 라벨
    fig3_floorplan()           # placeholder 치수 (실측치로 layout 인자 덮어쓰기)
    print("\n모든 파일 출력 완료. 각 함수에 데이터/경로 인자 전달 시 재생성 가능.")
