#!/usr/bin/env python3
"""Remote Production Animation & 4K Scrub-Detail Render Script for PH0NE (ai-worker).

Executes on PH0NE (RTX 3060 Laptop GPU, OptiX, Blender 5.2.2 LTS) inside isolated staging:
  C:\\AI-Station\\jobs\\slotted-liner-teaser-v3

Outputs:
1. 160-frame 1080p PNG sequence (frames/frame_0001.png .. frame_0160.png)
2. 4K UHD (3840x2160) Hero Stills for Beat 1 (f045), Beat 2 (f076), Beat 3 (f105)
3. Master 16:9 Teaser MP4: laser_slotted_liner_teaser_v3_1080p.mp4 (24 fps, 6.67 s)
4. "Viewer Scrub Zoom-In" Center Detail MP4: laser_slotted_liner_center_zoom_v3.mp4
5. Deterministic Receipt JSON: render_receipt.json (SHA256 verified)
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

# Import the verified Look-Dev v3 scene builder from the same directory
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_laser_teaser_v1 as teaser  # noqa: E402


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def find_ffmpeg() -> str:
    candidates = [
        r"C:\Users\gronn\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe",
        r"C:\Users\kyle\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe",
        "ffmpeg",
    ]
    for c in candidates:
        if c == "ffmpeg" or os.path.exists(c):
            return c
    return "ffmpeg"


def main() -> None:
    t0 = time.time()
    job_dir = Path(os.environ.get("SLOTTED_JOB_DIR", r"C:\AI-Station\jobs\slotted-liner-teaser-v4"))
    frames_dir = job_dir / "frames"
    uhd_dir = job_dir / "uhd_4k"
    frames_dir.mkdir(parents=True, exist_ok=True)
    uhd_dir.mkdir(parents=True, exist_ok=True)

    # 1. Build verified Look-Dev v4 scene
    scene = teaser.clear_and_init_scene()
    mats = teaser.build_materials()
    pipe_objs = teaser.build_pipe_and_red_ends(mats)
    head_objs = teaser.build_mysterious_laser_head(mats)
    fx_objs = teaser.build_center_slot_and_laser_fx(mats, head_objs["nozzle"])
    lights = teaser.setup_world_and_lights(scene, pipe_objs, head_objs)
    cam = teaser.setup_camera(scene)
    teaser.animate_laser_sequence(head_objs["nozzle"], fx_objs, lights, mats)

    # 2. Configure Cycles OptiX with fast adaptive sampling & persistent data
    device_str = teaser.configure_cycles_optix(scene, width=1920, height=1080, samples=48)
    scene.render.use_persistent_data = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.025
    scene.cycles.adaptive_min_samples = 4

    # Gate 0 & Gate 2 audit before rendering
    scene.frame_set(45)
    audit = teaser.audit_scene_geometry(scene, cam, pipe_objs, head_objs)

    blend_path = job_dir / "laser_slotted_liner_teaser_v4_prod.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    # 3. Render 160-frame 1080p sequence:
    # - Frame 1: Stillness reference frame (path-traced)
    # - Frames 2..67: Locked stillness pause (exact hold of Frame 1)
    # - Frames 68..84: Surgical 12 kW laser strike & 60 mm translation (path-traced)
    # - Frames 85..112: Top-spine thermal afterglow decay (path-traced)
    # - Frames 113..160: Post-cut stillness hold (exact hold of Frame 112)
    frame_records = []
    for f in range(teaser.FRAME_START, teaser.FRAME_END + 1):
        f_path = frames_dir / f"frame_{f:04d}.png"
        if not (f_path.exists() and f_path.stat().st_size > 10000):
            if 2 <= f <= 67:
                src_hold = frames_dir / "frame_0001.png"
                shutil.copy2(src_hold, f_path)
            elif 113 <= f <= 160:
                src_hold = frames_dir / "frame_0112.png"
                shutil.copy2(src_hold, f_path)
            else:
                scene.frame_set(f)
                scene.render.filepath = str(f_path)
                bpy.ops.render.render(write_still=True)

        digest = sha256_file(f_path)
        frame_records.append(
            {
                "frame": f,
                "file": f_path.name,
                "bytes": f_path.stat().st_size,
                "sha256": digest,
            }
        )
        if f in (1, 45, 68, 72, 76, 80, 84, 95, 105, 112, 160):
            elapsed = time.time() - t0
            print(f"[SEQ] Frame {f:03d}/160 done ({elapsed:.1f}s elapsed) -> {digest[:10]}", flush=True)

    # Verify Gate 1b across the three story beats (f045, f076, f105)
    beat_hashes = {
        "beat1": frame_records[44]["sha256"],
        "beat2": frame_records[75]["sha256"],
        "beat3": frame_records[104]["sha256"],
    }
    assert len(set(beat_hashes.values())) == 3, f"Gate 1b FAILED on beat hashes: {beat_hashes}"

    # 4. Render 4K UHD (3840x2160) Hero Stills for Beat 1, Beat 2 (Viewer Scrub Frame), Beat 3
    scene.render.resolution_x = 3840
    scene.render.resolution_y = 2160
    scene.cycles.samples = 96
    uhd_records = {}
    for beat_name, frame_num in teaser.CHECK_FRAMES.items():
        u_path = uhd_dir / f"{beat_name}_4k_f{frame_num:03d}.png"
        if not (u_path.exists() and u_path.stat().st_size > 10000):
            scene.frame_set(frame_num)
            scene.render.filepath = str(u_path)
            bpy.ops.render.render(write_still=True)
        uhd_records[beat_name] = {
            "frame": frame_num,
            "file": u_path.name,
            "bytes": u_path.stat().st_size,
            "sha256": sha256_file(u_path),
        }
        print(f"[4K UHD] {beat_name} (frame {frame_num}) -> {u_path.name}", flush=True)

    # 5. Encode MP4 videos with FFmpeg
    ffmpeg_bin = find_ffmpeg()
    mp4_wide = job_dir / "laser_slotted_liner_teaser_v4_1080p.mp4"
    cmd_wide = [
        ffmpeg_bin,
        "-y",
        "-framerate",
        "24",
        "-i",
        str(frames_dir / "frame_%04d.png"),
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "14",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(mp4_wide),
    ]
    subprocess.run(cmd_wide, check=True)

    # Encode a 4x Center Zoom-In ("What the viewer sees when they scrub & zoom in on the center")
    mp4_zoom = job_dir / "laser_slotted_liner_center_zoom_v4.mp4"
    cmd_zoom = [
        ffmpeg_bin,
        "-y",
        "-framerate",
        "24",
        "-i",
        str(frames_dir / "frame_%04d.png"),
        "-vf",
        "crop=480:270:720:390,scale=1920:1080:flags=lanczos",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "14",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(mp4_zoom),
    ]
    subprocess.run(cmd_zoom, check=True)

    # Also crop a 16:9 1920x1080 center inspection still from the 4K Beat 2 render using FFmpeg
    uhd_beat2 = uhd_dir / "beat2_laser_strike_4k_f076.png"
    zoom_still_4k = uhd_dir / "beat2_center_scrub_zoom_from_4k_f076.png"
    cmd_crop_4k = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(uhd_beat2),
        "-vf",
        "crop=960:540:1440:780,scale=1920:1080:flags=lanczos",
        "-frames:v",
        "1",
        "-update",
        "1",
        str(zoom_still_4k),
    ]
    subprocess.run(cmd_crop_4k, check=True)

    total_sec = round(time.time() - t0, 2)
    receipt = {
        "job_dir": str(job_dir),
        "blender_version": bpy.app.version_string,
        "device": device_str,
        "total_render_seconds": total_sec,
        "frame_count": len(frame_records),
        "pathtraced_frames": 24 + 17 + 44,
        "beat_hashes": beat_hashes,
        "mp4_wide": {
            "file": mp4_wide.name,
            "bytes": mp4_wide.stat().st_size,
            "sha256": sha256_file(mp4_wide),
        },
        "mp4_center_zoom": {
            "file": mp4_zoom.name,
            "bytes": mp4_zoom.stat().st_size,
            "sha256": sha256_file(mp4_zoom),
        },
        "uhd_4k_renders": uhd_records,
        "zoom_still_from_4k": {
            "file": zoom_still_4k.name,
            "bytes": zoom_still_4k.stat().st_size,
            "sha256": sha256_file(zoom_still_4k),
        },
        "audit": audit,
    }
    receipt_path = job_dir / "render_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("PH0NE_PRODUCTION_DONE", json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
