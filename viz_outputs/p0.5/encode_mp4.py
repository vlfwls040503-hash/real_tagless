"""
PNG 시퀀스를 H.264 MP4로 인코딩.
imageio-ffmpeg가 번들한 ffmpeg 바이너리 사용.
"""
import os
import sys
import subprocess
import pathlib
import time

import imageio_ffmpeg

WORK = pathlib.Path(__file__).resolve().parent
OUT = WORK / "outputs"
FRAMES = OUT / "frames_p0.5"
MP4 = OUT / "output_p0.5.mp4"

FPS = 30


def main():
    if not FRAMES.is_dir():
        print(f"[encode] ERROR: frames dir missing: {FRAMES}")
        return 1
    pngs = sorted(FRAMES.glob("f_*.png"))
    if not pngs:
        print(f"[encode] ERROR: no PNG frames in {FRAMES}")
        return 1
    print(f"[encode] {len(pngs)} frames -> {MP4}")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    pattern = str(FRAMES / "f_%04d.png")

    # 프레임 번호 디텍트 (Blender는 %04d 기본)
    first = pngs[0].name  # f_0001.png
    digits = len(first.split("_")[1].split(".")[0])
    pattern = str(FRAMES / f"f_%0{digits}d.png")

    cmd = [
        ffmpeg,
        "-y",
        "-framerate", str(FPS),
        "-i", pattern,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "20",
        "-preset", "medium",
        "-movflags", "+faststart",
        str(MP4),
    ]
    print("[encode] " + " ".join(cmd))
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - t0
    if proc.returncode != 0:
        print(f"[encode] FAILED ({elapsed:.1f}s)")
        print("STDOUT:", proc.stdout[-1000:])
        print("STDERR:", proc.stderr[-2000:])
        return proc.returncode
    print(f"[encode] OK in {elapsed:.1f}s, file: {MP4} ({MP4.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
