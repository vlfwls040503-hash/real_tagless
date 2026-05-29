"""
개찰구 통과시간 + 보행속도 분석
1단계: YOLOv8 + ByteTrack 으로 사람 검출/추적 → CSV 저장
"""
import os
import sys
import csv
import time
import argparse
import cv2
from ultralytics import YOLO

DEFAULT_VIDEO = r"C:\Users\aaron\tagless\개찰구 촬영 영상\1\GX010193_blurred.MP4"
OUT_DIR = r"C:\Users\aaron\tagless\영상데이터"


def run_track(video_path, out_csv, max_seconds=None, conf=0.35, imgsz=640,
              model_name="yolov8n.pt", device=0, tracker="bytetrack.yaml"):
    model = YOLO(model_name)
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    n_max = n_total if max_seconds is None else min(n_total, int(max_seconds * fps))
    print(f"video : {video_path}")
    print(f"fps   : {fps:.3f}, total frames: {n_total}, processing: {n_max}")
    print(f"model : {model_name}, device: {device}, conf: {conf}, imgsz: {imgsz}")

    results = model.track(
        source=video_path,
        tracker=tracker,
        classes=[0],          # person only
        conf=conf,
        imgsz=imgsz,
        device=device,
        stream=True,
        persist=True,
        verbose=False,
    )

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    f = open(out_csv, "w", newline="", encoding="utf-8")
    w = csv.writer(f)
    w.writerow(["frame", "t_sec", "id", "x1", "y1", "x2", "y2", "cx", "cy_foot", "conf"])

    t0 = time.time()
    last_print = t0
    frame_idx = 0
    n_dets = 0
    for r in results:
        if frame_idx >= n_max:
            break
        boxes = r.boxes
        if boxes is None or boxes.id is None:
            frame_idx += 1
            continue
        xyxy = boxes.xyxy.cpu().numpy()
        ids = boxes.id.int().cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        t_sec = frame_idx / fps
        for (x1, y1, x2, y2), pid, c in zip(xyxy, ids, confs):
            cx = (x1 + x2) / 2.0
            cy_foot = y2  # bbox 하단 = 발끝 근사
            w.writerow([frame_idx, f"{t_sec:.3f}", int(pid),
                        f"{x1:.1f}", f"{y1:.1f}", f"{x2:.1f}", f"{y2:.1f}",
                        f"{cx:.1f}", f"{cy_foot:.1f}", f"{c:.3f}"])
            n_dets += 1
        frame_idx += 1
        if time.time() - last_print > 5.0:
            elapsed = time.time() - t0
            speed = frame_idx / max(elapsed, 1e-3)
            eta = (n_max - frame_idx) / max(speed, 1e-3)
            print(f"  frame {frame_idx}/{n_max}  ({100*frame_idx/n_max:5.1f}%)  "
                  f"{speed:.1f} fps  eta {eta:.0f}s  dets={n_dets}")
            last_print = time.time()

    f.close()
    elapsed = time.time() - t0
    print(f"done. frames={frame_idx} dets={n_dets} elapsed={elapsed:.1f}s -> {out_csv}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=DEFAULT_VIDEO)
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "tracks.csv"))
    ap.add_argument("--seconds", type=float, default=None,
                    help="처리할 최대 길이(초). 미지정 시 전체.")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--device", default=0)
    ap.add_argument("--tracker", default="bytetrack.yaml")
    args = ap.parse_args()
    run_track(args.video, args.out, args.seconds, args.conf, args.imgsz,
              args.model, args.device, args.tracker)
