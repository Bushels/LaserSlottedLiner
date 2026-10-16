---
name: blender-52-cycles-studio
description: Blender 5.2+ Cycles OptiX industrial product visualization, light-linking architecture, and 9-Gate verification workflow including Mandatory Adversarial Flash Critic (Model="flash").
---

# Blender 5.2+ Cycles Studio & Adversarial Verification Skill

Use this skill for all Blender 5.2+ industrial product visualization, dark-studio look-development, and remote `PH0NE` (`ai-worker`, RTX 3060 OptiX) animation rendering.

## 1. Blender 5.2+ API Invariants

1. **Headless Invocation**:
   - Always invoke Blender with `--background --factory-startup --python <script.py>` and clear the scene with `bpy.ops.wm.read_factory_settings(use_empty=True)`.
2. **Shader Node Lookup**:
   - Always look up nodes by `node.bl_idname` (e.g., `ShaderNodeBsdfPrincipled`, `ShaderNodeEmission`, `ShaderNodeMixShader`) — never by localized `.name`.
3. **Optical Glow & Halo Quads (`Principled BSDF` Alpha Gotcha)**:
   - In Cycles, `Principled BSDF` `Alpha` does **not** attenuate `Emission`.
   - Always build optical glow/plasma/ember quads using `ShaderNodeMixShader` (`ShaderNodeBsdfTransparent` + `ShaderNodeEmission`) driven by radial UV/Object distance, and set `scene.cycles.transparent_max_bounces = 16`.
4. **Blender 5.2 Light Linking (`lobj.light_linking.receiver_collection`)**:
   - Isolate pipe rim strips (`LL_Pipe_Receivers`) from overhead mechanism silhouette lights (`LL_Head_Receivers`).
   - Exclude stealth/recessed emitter components from Beat 1 rim light collections AND light-link kerf afterglow point lights (`Laser_Kerf_Warm_Glow`) strictly to `LL_Pipe_Receivers` so they never cast vertical specular streaks onto the nozzle stem.

---

## 2. Mandatory 9-Gate Verification Workflow

Before presenting **any** Blender render or animation to the user, every iteration must pass all 9 gates:

- **Gate 0 (Dimension & Scale Audit)**: Assert `obj.dimensions` in meters (`PIPE_OD_M = 0.1778 m`, `PIPE_LEN_M = 9.0 m`). Any overhead mechanism or laser head must be physically scaled to the `177.8 mm` pipe diameter (e.g., `34 mm` slim linear guide carriage height, `11–24 mm` stealth emitter collar)—never an oversized sci-fi structure.
- **Gate 1a / 1b (Render & Temporal Hash Gate)**: Verify non-empty PNG outputs and distinct SHA256 hashes across Beat 1 (`f045`), Beat 2 (`f076`), and Beat 3 (`f105`).
- **Gate 2 (Camera Framing & NDC Projection Audit)**: Verify `world_to_camera_view` NDC coordinates for left red coupling, center top spine, right red thread protector, and sleek linear carriage.
- **Gate 8 (Primary Visual Self-Critique)**: Inspect both full `16:9` frames and `4×` center scrub-zoom crops via `view_file`.
- **Gate 9 (Mandatory Adversarial Flash Critic — `Model="flash"`)**:
  - Define/invoke the `adversary-critic` subagent with `Model="flash"` (`invoke_subagent` / `send_message`) and pass it both the `16:9` wide renders and the `4×` center zoom crops across all 3 beats.
  - The Flash adversary must ruthlessly audit:
    1. **Proportional Honesty vs. `7"` (`177.8 mm`) Pipe**: Reject any bulky, gaudy, or sci-fi geometry.
    2. **Machined Industrial Detail at `4×` Zoom**: Ensure crisp Swiss-machined chamfers, linear guide grooves, and flat anodized end-plates (no generic rounded pill/lozenge shapes).
    3. **"Infer, Don't Show the Slot"**: Confirm `0°` dead-level side profile with zero visible open slot face on the pipe flank.
    4. **Lighting & Material Restraint**: Confirm silky longitudinal anisotropic steel sheen (`Anisotropic = 0.65`) and zero stray afterglow reflections on the stealth emitter stem.
  - **Never submit renders to the user until `adversary-critic` (`Model="flash"`) returns an unconditional `PASS`.**
