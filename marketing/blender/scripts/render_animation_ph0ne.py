#!/usr/bin/env python3
"""Remote Production Animation & 4K Scrub-Detail Render Script for PH0NE (ai-worker) — Look-Dev v10.

Executes on PH0NE (RTX 3060 Laptop GPU, OptiX, Blender 5.2.2 LTS) inside isolated staging:
  C:\\AI-Station\\jobs\\slotted-liner-teaser-v10

Outputs:
1. 160-frame 1080p PNG sequence (frames/frame_0001.png .. frame_0160.png)
2. 4K UHD (3840x2160) Hero Stills for:
   - Beat 1a High Poise (f012)
   - Beat 1c Lowered Pause (f056)
   - Beat 2 Blue Laser Strike & Machine Silhouette Reveal (f070)
   - Beat 3 Post-Cut Cold Precision (f082)
3. Clean Master 16:9 Teaser MP4: laser_slotted_liner_teaser_v10_clean_1080p.mp4 (24 fps, 6.67 s)
4. Hook Master 16:9 Teaser MP4: laser_slotted_liner_teaser_v10_hook_1080p.mp4 (with minimalist end-card hook)
5. "Viewer Scrub Zoom-In" Center Detail MP4: laser_slotted_liner_center_zoom_v10.mp4
6. Deterministic Receipt JSON: render_receipt.json (SHA256 verified)
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

# Import the verified Look-Dev v10 scene builder from the same directory
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


def build_hook_vf_filter() -> str:
    """Build an FFmpeg filtergraph that fades in the minimalist end-card hook after the blue laser strike:
    - Line 1 (t = 3.85s .. 4.55s fade-in): '20 YEARS OF SAW DISCS.'
    - Line 2 (t = 4.55s .. 5.25s fade-in): 'OVER IN 0.3 SECONDS.' + thin electric-blue accent bar
    """
    font_reg = "C\\:/Windows/Fonts/bahnschrift.ttf"
    font_bold = "C\\:/Windows/Fonts/segoeuib.ttf"
    if not os.path.exists(r"C:\Windows\Fonts\segoeuib.ttf"):
        font_bold = "C\\:/Windows/Fonts/arialbd.ttf"
    if not os.path.exists(r"C:\Windows\Fonts\bahnschrift.ttf"):
        font_reg = "C\\:/Windows/Fonts/segoeui.ttf"

    alpha1 = "if(lt(t,3.85),0,if(lt(t,4.55),(t-3.85)/0.70,1))"
    alpha2 = "if(lt(t,4.55),0,if(lt(t,5.25),(t-4.55)/0.70,1))"

    dt1 = (
        f"drawtext=fontfile='{font_reg}':text='20 YEARS OF SAW DISCS.':fontsize=30:"
        f"fontcolor=0xB8C8D8:alpha='{alpha1}':shadowcolor=0x000000@0.75:shadowx=2:shadowy=2:"
        f"x=(w-text_w)/2:y=h*0.775"
    )
    dt2 = (
        f"drawtext=fontfile='{font_bold}':text='OVER IN 0.3 SECONDS.':fontsize=48:"
        f"fontcolor=0xF0FAFF:alpha='{alpha2}':shadowcolor=0x000000@0.85:shadowx=2:shadowy=2:"
        f"x=(w-text_w)/2:y=h*0.832"
    )
    dt3 = (
        "drawbox=x=(iw-160)/2:y=ih*0.902:w=160:h=3:"
        "color=0x2B8CFF@0.92:t=fill:enable='gte(t,4.85)'"
    )
    return f"{dt1},{dt2},{dt3}"


def main() -> None:
    t0 = time.time()
    job_dir = Path(os.environ.get("SLOTTED_JOB_DIR", r"C:\AI-Station\jobs\slotted-liner-teaser-v10"))
    frames_dir = job_dir / "frames"
    uhd_dir = job_dir / "uhd_4k"
    frames_dir.mkdir(parents=True, exist_ok=True)
    uhd_dir.mkdir(parents=True, exist_ok=True)

    # 1. Build verified Look-Dev v10b ("Horizontal 4.5-Inch Pipe — Z-Descent, Pause, Blue Laser & Machine Silhouette Reveal") scene
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
    scene.frame_set(56)
    audit = teaser.audit_scene_geometry(scene, cam, pipe_objs, head_objs)

    blend_path = job_dir / "laser_slotted_liner_teaser_v10_prod.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    # 3. Render 160-frame 1080p sequence:
    # - Frame 1: High-poise stillness reference frame (path-traced)
    # - Frames 2..17: High-poise stillness hold (exact hold of Frame 1)
    # - Frames 18..46: Motorized Z-axis descent (+62 mm -> 0 mm cutting standoff) (path-traced)
    # - Frames 47..64: Suspenseful tension pause at cutting standoff (exact hold of Frame 46)
    # - Frames 65..67: 0.12s pre-strike blue optical lock-on micro-cue (path-traced)
    # - Frames 68..72: 0.17s ultra-fast electric-blue laser strike & machine silhouette reveal (path-traced)
    # - Frames 73..96: Blue glow dissipation & post-cut settle (path-traced)
    # - Frames 97..160: Post-cut cold stillness hold (exact hold of Frame 96)
    frame_records = []
    pathtraced_count = 0
    for f in range(teaser.FRAME_START, teaser.FRAME_END + 1):
        f_path = frames_dir / f"frame_{f:04d}.png"
        is_hold_high = 2 <= f <= 17
        is_hold_pause = 47 <= f <= 64
        is_hold_late = 97 <= f <= 160
        if not (is_hold_high or is_hold_pause or is_hold_late):
            pathtraced_count += 1

        if not (f_path.exists() and f_path.stat().st_size > 10000):
            if is_hold_high:
                src_hold = frames_dir / "frame_0001.png"
                shutil.copy2(src_hold, f_path)
            elif is_hold_pause:
                src_hold = frames_dir / "frame_0046.png"
                shutil.copy2(src_hold, f_path)
            elif is_hold_late:
                src_hold = frames_dir / "frame_0096.png"
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
        if f in (1, 12, 18, 32, 46, 56, 65, 68, 70, 72, 75, 82, 96, 160):
            elapsed = time.time() - t0
            print(f"[SEQ] Frame {f:03d}/160 done ({elapsed:.1f}s elapsed) -> {digest[:10]}", flush=True)

    # Verify Gate 1b across the four story beats (f012, f056, f070, f082)
    beat_hashes = {
        "beat1a_high_poise": frame_records[11]["sha256"],
        "beat1c_lowered_pause": frame_records[55]["sha256"],
        "beat2_blue_laser_strike": frame_records[69]["sha256"],
        "beat3_afterglow": frame_records[81]["sha256"],
    }
    assert len(set(beat_hashes.values())) == 4, f"Gate 1b FAILED on beat hashes: {beat_hashes}"

    # 4. Render 4K UHD (3840x2160) Hero Stills for all 4 story beats (f012, f056, f070, f082)
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

    # 5. Encode all 3 MP4 deliverables with FFmpeg
    ffmpeg_bin = find_ffmpeg()

    # 5a. Clean Master 16:9 Teaser MP4 (no text)
    mp4_clean = job_dir / "laser_slotted_liner_teaser_v10_clean_1080p.mp4"
    cmd_clean = [
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
        str(mp4_clean),
    ]
    subprocess.run(cmd_clean, check=True)

    # 5b. Hook Master 16:9 Teaser MP4 (with minimalist end-card hook via FFmpeg drawtext)
    mp4_hook = job_dir / "laser_slotted_liner_teaser_v10_hook_1080p.mp4"
    hook_vf = build_hook_vf_filter()
    cmd_hook = [
        ffmpeg_bin,
        "-y",
        "-framerate",
        "24",
        "-i",
        str(frames_dir / "frame_%04d.png"),
        "-vf",
        hook_vf,
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
        str(mp4_hook),
    ]
    subprocess.run(cmd_hook, check=True)

    # 5c. 2.5x Center Scrub Zoom-In MP4 ("What the viewer sees when they scrub & zoom in on the Z-descent & blue laser")
    mp4_zoom = job_dir / "laser_slotted_liner_center_zoom_v10.mp4"
    cmd_zoom = [
        ffmpeg_bin,
        "-y",
        "-framerate",
        "24",
        "-i",
        str(frames_dir / "frame_%04d.png"),
        "-vf",
        "crop=768:432:576:220,scale=1920:1080:flags=lanczos",
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

    # 5d. Also crop a 16:9 1920x1080 center inspection still from the 4K Beat 2 render using FFmpeg
    uhd_beat2 = uhd_dir / "beat2_blue_laser_strike_4k_f070.png"
    zoom_still_4k = uhd_dir / "beat2_center_scrub_zoom_from_4k_f070.png"
    cmd_crop_4k = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(uhd_beat2),
        "-vf",
        "crop=1536:864:1152:440,scale=1920:1080:flags=lanczos",
        "-frames:v",
        "1",
        "-update",
        "1",
        str(zoom_still_4k),
    ]
    subprocess.run(cmd_crop_4k, check=True)

    # Extract Frame 150 (t=6.20s) from mp4_hook for quick visual inspection of the end-card hook
    hook_still_path = job_dir / "beat3_endcard_hook_f150.png"
    cmd_hook_still = [
        ffmpeg_bin,
        "-y",
        "-ss",
        "6.20",
        "-i",
        str(mp4_hook),
        "-frames:v",
        "1",
        "-update",
        "1",
        str(hook_still_path),
    ]
    subprocess.run(cmd_hook_still, check=True)

    total_sec = round(time.time() - t0, 2)
    receipt = {
        "job_dir": str(job_dir),
        "blender_version": bpy.app.version_string,
        "device": device_str,
        "total_render_seconds": total_sec,
        "frame_count": len(frame_records),
        "pathtraced_frames": pathtraced_count,
        "beat_hashes": beat_hashes,
        "mp4_clean": {
            "file": mp4_clean.name,
            "bytes": mp4_clean.stat().st_size,
            "sha256": sha256_file(mp4_clean),
        },
        "mp4_hook": {
            "file": mp4_hook.name,
            "bytes": mp4_hook.stat().st_size,
            "sha256": sha256_file(mp4_hook),
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
        "hook_still_f150": {
            "file": hook_still_path.name,
            "bytes": hook_still_path.stat().st_size,
            "sha256": sha256_file(hook_still_path),
        },
        "audit": audit,
    }
    receipt_path = job_dir / "render_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("PH0NE_PRODUCTION_DONE", json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
