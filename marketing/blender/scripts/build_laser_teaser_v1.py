#!/usr/bin/env python3
"""Build and render Look-Dev v10 ("Horizontal 4.5-Inch Joint — Z-Descent, Pause, Blue Laser & Machine Silhouette Reveal")
for the Laser Slotted Liner Teaser Campaign.

Look-Dev v10 Specification (Kyle's director brief, 2026-10-19):
1. TRUE HORIZONTAL ELEVATION WITH SHORTENED 4.5" API 5CT PIPE (`PIPE_OD_M = 0.1143 m`, `PIPE_LEN_M = 3.200 m`):
   - Using a shortened 4.5" (`114.3 mm` OD) API 5CT liner joint (`x = -1.600 m` to `+1.600 m`) with the red API
     box coupling on the left and red pin thread protector on the right allows the ENTIRE joint (coupling-to-protector)
     to fit cleanly inside the 16:9 frame from a true horizontal perspective (`CAM_LOCATION = (0.000, -4.150, 0.036)`),
     close enough (`4.15 m`) that the pipe, laser head, and blue laser beam read with crisp macro clarity.
   - Camera elevation (`z = +0.036 m`) sits below the `12 o'clock` top spine (`z = +0.05715 m`) so the open slot hole
     is 100% hidden ("Infer, Don't Show the Slot").

2. FOUR-BEAT DIRECTOR CHOREOGRAPHY:
   - Beat 1a — Initial Stillness (`Frames 1..18`, `0.00s..0.75s`):
     The laser head starts poised high (`+62 mm` above cutting standoff) in near-darkness above the horizontal 4.5" pipe.
   - Beat 1b — Motorized Z-Axis Descent ("The First Animation" — `Frames 19..46`, `0.79s..1.92s`):
     The laser head smoothly lowers `62 mm` down toward the `12 o'clock` spine (`z_offset: +0.062 m -> 0.000 m`)
     and locks into cutting standoff (`65 mm` above the pipe crown). Viewers immediately look at the center and
     wonder what is about to happen.
   - Beat 1c — The Tension Pause (`Frames 47..67`, `1.96s..2.79s`, `0.88s` dead-still hold):
     Complete mechanical stillness after the head locks into position (`Frames 64..67` add a tiny cyan optical lock-on glint).
   - Beat 2 — Electric-Blue Laser Strike & Overhead Machine Silhouette Reveal (`Frames 68..72`, `2.83s..3.00s`, `0.17s` / 4 frames):
     - A razor-sharp electric-blue/cyan laser beam fires and zips `110 mm` (`x = -0.055 m` to `+0.055 m`) in `0.17s`.
     - As the blue laser fires, a brief electric-blue atmospheric glow radiates upward onto the overhead Z-axis
       column collar, dark industrial bellows, and sleek overhead gantry bridge silhouette — proving the laser head is
       mounted inside a substantial piece of equipment (never a "floating laser head") without revealing proprietary internals.
     - Strictly ZERO bottom burn-through (`6 o'clock` keel 100% clean) and ZERO thermal hot-spot on the pipe wall.
   - Beat 3 — Post-Cut Cold Precision & End-Card Hook (`Frames 73..160`, `3.04s..6.67s`):
     Instant cold blackout of the beam; the blue machine-silhouette glow decays smoothly over `~0.35s`, leaving a
     razor-thin cold silver-blue machined kerf hairline on the `12 o'clock` spine before the end-card hook:
     `20 YEARS OF SAW DISCS.` / `OVER IN 0.3 SECONDS.`
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector


# ==============================================================================
# ENGINEERING & SCENE PARAMETERS (METRES) — 4.5" API 5CT SHORTENED HORIZONTAL JOINT
# ==============================================================================
PIPE_OD_M = 0.1143          # 4.500 in API 5CT casing/liner OD (114.3 mm)
PIPE_ID_M = 0.1005          # 3.958 in ID (11.6 lb/ft wall = 6.88 mm)
PIPE_LEN_M = 3.200          # 3.20 m (~10.5 ft) shortened display joint so full horizontal span fits closely in 16:9!

PIPE_X_START = -0.5 * PIPE_LEN_M  # -1.600 m
PIPE_X_END = +0.5 * PIPE_LEN_M    # +1.600 m
PIPE_X_MID = 0.000

COUPLING_OD_M = 0.1270      # 5.000 in API 4.5" Box Coupling OD
COUPLING_LEN_M = 0.195      # API 4.5" coupling length on left (-X) end

PROTECTOR_OD_M = 0.1245     # 4.900 in closed-end pin thread protector OD
PROTECTOR_LEN_M = 0.155     # Pin protector length on right (+X) end

SLOT_LEN_M = 0.110          # 110 mm high-speed axial stroke along top spine (x = -0.055 .. +0.055 m)
STANDOFF_GAP_M = 0.0680     # 68.0 mm cutting standoff gap (z = 0.05715 m pipe top spine to z = 0.12515 m nozzle tip)
HEAD_Z_LIFT_M = 0.0620      # +62.0 mm raised Z-height at start of Beat 1 before the head lowers into position!

# True Horizontal Elevation Camera Parameters (4.15 m straight in front, full 3.2 m 4.5" pipe spans ~84% of 16:9 width)
CAM_LOCATION = Vector((0.000, -4.150, 0.036))
CAM_TARGET = Vector((0.000, 0.000, 0.112))
CAM_LENS_MM = 39.0

# Keyframes for the 4-beat teaser (24 fps, 160 frames = 6.67 s)
FRAME_START = 1
FRAME_DESCEND_START = 18    # 0.75 s: laser head begins lowering from +62 mm
FRAME_DESCEND_END = 46      # 1.92 s: laser head locks smoothly into cutting standoff (0.0 mm offset)
# Frames 47..67 (1.96s..2.79s = 0.88s): "A brief pause" while viewers watch the lowered head in suspense
FRAME_PRE_PULSE = 65        # 2.71 s: 3-frame (0.12 s) blue optical lock-on micro-cue at end of pause
FRAME_FIRE_START = 68       # 2.83 s: ultra-fast 12 kW electric-blue laser strike & machine silhouette glow begins
FRAME_FIRE_END = 72         # 3.00 s: 4 frames (0.17 s) ultra-fast axial zip (-55 mm -> +55 mm)
FRAME_END = 160             # 6.67 s: cold blackout & end-card hook reveal

CHECK_FRAMES = {
    "beat1a_high_poise": 12,
    "beat1c_lowered_pause": 56,
    "beat2_blue_laser_strike": 70,
    "beat3_afterglow": 82,
}


# ==============================================================================
# NODE HELPERS (BLENDER 5.2 VERIFIED API — LOOKUP BY bl_idname ONLY)
# ==============================================================================
def get_node_by_type(node_tree: bpy.types.NodeTree, bl_idname: str) -> bpy.types.Node:
    for node in node_tree.nodes:
        if node.bl_idname == bl_idname:
            return node
    return node_tree.nodes.new(bl_idname)


def clear_and_init_scene() -> bpy.types.Scene:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = 24
    return scene


# ==============================================================================
# MATERIALS
# ==============================================================================
def build_materials() -> dict[str, bpy.types.Material]:
    mats: dict[str, bpy.types.Material] = {}

    # 1. Deep Black-Oxide Satin Pipe (true dark black body with sleek metallic sheen)
    mat_pipe = bpy.data.materials.new("Pipe_Black_Oxide_Sheen")
    nt = mat_pipe.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = get_node_by_type(nt, "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.012, 0.014, 0.018, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.86
    bsdf.inputs["Roughness"].default_value = 0.24
    bsdf.inputs["Anisotropic"].default_value = 0.65
    bsdf.inputs["Coat Weight"].default_value = 0.32
    bsdf.inputs["Coat Roughness"].default_value = 0.11

    tangent = nodes.new("ShaderNodeTangent")
    tangent.direction_type = "RADIAL"
    tangent.axis = "X"
    links.new(tangent.outputs["Tangent"], bsdf.inputs["Tangent"])

    tex_coord = nodes.new("ShaderNodeTexCoord")
    vec_mult = nodes.new("ShaderNodeVectorMath")
    vec_mult.operation = "MULTIPLY"
    vec_mult.inputs[1].default_value = (2.5, 220.0, 220.0)
    links.new(tex_coord.outputs["Object"], vec_mult.inputs[0])

    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.5
    noise.inputs["Detail"].default_value = 3.0
    links.new(vec_mult.outputs["Vector"], noise.inputs["Vector"])

    remap = nodes.new("ShaderNodeMapRange")
    remap.inputs["From Min"].default_value = 0.25
    remap.inputs["From Max"].default_value = 0.75
    remap.inputs["To Min"].default_value = 0.225
    remap.inputs["To Max"].default_value = 0.255
    links.new(noise.outputs["Fac"], remap.inputs["Value"])
    links.new(remap.outputs["Result"], bsdf.inputs["Roughness"])

    bevel = nodes.new("ShaderNodeBevel")
    bevel.inputs["Radius"].default_value = 0.0004
    bevel.samples = 4
    links.new(bevel.outputs["Normal"], bsdf.inputs["Normal"])
    mats["pipe"] = mat_pipe

    # 2. Machined Thread Standoff Ring
    mat_machined = bpy.data.materials.new("Machined_Steel_Accent")
    nt_m = mat_machined.node_tree
    bsdf_m = get_node_by_type(nt_m, "ShaderNodeBsdfPrincipled")
    bsdf_m.inputs["Base Color"].default_value = (0.14, 0.16, 0.19, 1.0)
    bsdf_m.inputs["Metallic"].default_value = 0.92
    bsdf_m.inputs["Roughness"].default_value = 0.26
    bevel_m = nt_m.nodes.new("ShaderNodeBevel")
    bevel_m.inputs["Radius"].default_value = 0.0003
    bevel_m.samples = 4
    nt_m.links.new(bevel_m.outputs["Normal"], bsdf_m.inputs["Normal"])
    mats["machined"] = mat_machined

    # 3. Red Coupling & Thread Protector (Rich Oilfield Crimson Satin)
    mat_red = bpy.data.materials.new("Red_Coupling_Protector")
    nt_r = mat_red.node_tree
    bsdf_r = get_node_by_type(nt_r, "ShaderNodeBsdfPrincipled")
    bsdf_r.inputs["Base Color"].default_value = (0.46, 0.014, 0.014, 1.0)
    bsdf_r.inputs["Metallic"].default_value = 0.25
    bsdf_r.inputs["Roughness"].default_value = 0.28
    bsdf_r.inputs["Coat Weight"].default_value = 0.40
    bsdf_r.inputs["Coat Roughness"].default_value = 0.12
    bevel_r = nt_r.nodes.new("ShaderNodeBevel")
    bevel_r.inputs["Radius"].default_value = 0.0006
    bevel_r.samples = 4
    nt_r.links.new(bevel_r.outputs["Normal"], bsdf_r.inputs["Normal"])
    mats["red"] = mat_red

    # 4. Overhead Machine Gantry & Z-Axis Saddle Structure (Stealth dark anodized & ground steel)
    mat_rail = bpy.data.materials.new("Linear_Rail_Steel")
    nt_rl = mat_rail.node_tree
    bsdf_rl = get_node_by_type(nt_rl, "ShaderNodeBsdfPrincipled")
    bsdf_rl.inputs["Base Color"].default_value = (0.014, 0.017, 0.022, 1.0)
    bsdf_rl.inputs["Metallic"].default_value = 0.88
    bsdf_rl.inputs["Roughness"].default_value = 0.34
    bsdf_rl.inputs["Anisotropic"].default_value = 0.65
    bsdf_rl.inputs["Anisotropic Rotation"].default_value = 0.0
    bevel_rl = nt_rl.nodes.new("ShaderNodeBevel")
    bevel_rl.inputs["Radius"].default_value = 0.0008
    bevel_rl.samples = 4
    nt_rl.links.new(bevel_rl.outputs["Normal"], bsdf_rl.inputs["Normal"])
    mats["rail"] = mat_rail

    # 4b. Optical Laser Barrel Housing (Deep satin hard-anodized obsidian aluminum)
    mat_carriage = bpy.data.materials.new("Laser_Carriage_Billet")
    nt_c = mat_carriage.node_tree
    bsdf_c = get_node_by_type(nt_c, "ShaderNodeBsdfPrincipled")
    bsdf_c.inputs["Base Color"].default_value = (0.014, 0.017, 0.022, 1.0)
    bsdf_c.inputs["Metallic"].default_value = 0.88
    bsdf_c.inputs["Roughness"].default_value = 0.32
    bsdf_c.inputs["Anisotropic"].default_value = 0.55
    bsdf_c.inputs["Anisotropic Rotation"].default_value = 0.25
    bevel_c = nt_c.nodes.new("ShaderNodeBevel")
    bevel_c.inputs["Radius"].default_value = 0.0005
    bevel_c.samples = 4
    nt_c.links.new(bevel_c.outputs["Normal"], bsdf_c.inputs["Normal"])
    mats["carriage"] = mat_carriage
    mats["shroud"] = mat_carriage

    # 4c. Dark Gunmetal / Oxide Steel Saddle & Collar
    mat_steel = bpy.data.materials.new("Linear_Runner_Steel")
    nt_st = mat_steel.node_tree
    bsdf_st = get_node_by_type(nt_st, "ShaderNodeBsdfPrincipled")
    bsdf_st.inputs["Base Color"].default_value = (0.020, 0.024, 0.030, 1.0)
    bsdf_st.inputs["Metallic"].default_value = 0.90
    bsdf_st.inputs["Roughness"].default_value = 0.30
    bevel_st = nt_st.nodes.new("ShaderNodeBevel")
    bevel_st.inputs["Radius"].default_value = 0.0005
    bevel_st.samples = 4
    nt_st.links.new(bevel_st.outputs["Normal"], bsdf_st.inputs["Normal"])
    mats["steel"] = mat_steel

    # 4d. Brushed Titanium-Stainless Fin Rims, Guide Rods & Conical Nozzle Body
    mat_stainless = bpy.data.materials.new("Stainless_Hardware_Fittings")
    nt_ss = mat_stainless.node_tree
    bsdf_ss = get_node_by_type(nt_ss, "ShaderNodeBsdfPrincipled")
    bsdf_ss.inputs["Base Color"].default_value = (0.050, 0.056, 0.066, 1.0)
    bsdf_ss.inputs["Metallic"].default_value = 0.92
    bsdf_ss.inputs["Roughness"].default_value = 0.24
    bevel_ss = nt_ss.nodes.new("ShaderNodeBevel")
    bevel_ss.inputs["Radius"].default_value = 0.0004
    bevel_ss.samples = 4
    nt_ss.links.new(bevel_ss.outputs["Normal"], bsdf_ss.inputs["Normal"])
    mats["stainless"] = mat_stainless

    # 4e. Matte Black Fin Valleys, Accordion Bellows & Wiper Seals
    mat_wiper = bpy.data.materials.new("Runner_Wiper_Seal")
    bsdf_wp = get_node_by_type(mat_wiper.node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_wp.inputs["Base Color"].default_value = (0.006, 0.007, 0.010, 1.0)
    bsdf_wp.inputs["Metallic"].default_value = 0.25
    bsdf_wp.inputs["Roughness"].default_value = 0.55
    mats["wiper"] = mat_wiper

    # 4f. Technical Dark Ceramic Capacitive Isolator Ring
    mat_ceramic = bpy.data.materials.new("Sensor_Ceramic_Isolator")
    bsdf_cer = get_node_by_type(mat_ceramic.node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_cer.inputs["Base Color"].default_value = (0.022, 0.022, 0.024, 1.0)
    bsdf_cer.inputs["Metallic"].default_value = 0.10
    bsdf_cer.inputs["Roughness"].default_value = 0.45
    mats["ceramic"] = mat_ceramic

    # 4g. Smoked Bronze / Warm Titanium Optical Locking Ring
    mat_brass = bpy.data.materials.new("Knurled_Brass_Collar")
    nt_br = mat_brass.node_tree
    bsdf_br = get_node_by_type(nt_br, "ShaderNodeBsdfPrincipled")
    bsdf_br.inputs["Base Color"].default_value = (0.065, 0.044, 0.028, 1.0)
    bsdf_br.inputs["Metallic"].default_value = 0.92
    bsdf_br.inputs["Roughness"].default_value = 0.26
    bevel_br = nt_br.nodes.new("ShaderNodeBevel")
    bevel_br.inputs["Radius"].default_value = 0.0004
    bevel_br.samples = 4
    nt_br.links.new(bevel_br.outputs["Normal"], bsdf_br.inputs["Normal"])
    mats["brass"] = mat_brass

    # 5. Conical Coaxial Laser Nozzle Tip
    mat_nozzle = bpy.data.materials.new("Laser_Stealth_Aperture")
    nt_n = mat_nozzle.node_tree
    bsdf_n = get_node_by_type(nt_n, "ShaderNodeBsdfPrincipled")
    bsdf_n.inputs["Base Color"].default_value = (0.026, 0.030, 0.038, 1.0)
    bsdf_n.inputs["Metallic"].default_value = 0.90
    bsdf_n.inputs["Roughness"].default_value = 0.26
    bevel_n = nt_n.nodes.new("ShaderNodeBevel")
    bevel_n.inputs["Radius"].default_value = 0.0004
    bevel_n.samples = 4
    nt_n.links.new(bevel_n.outputs["Normal"], bsdf_n.inputs["Normal"])
    mats["nozzle"] = mat_nozzle

    # 6. Blue Laser Beam Needle Core (Blinding Electric Sapphire-White 12 kW Coherent Core)
    mat_beam = bpy.data.materials.new("Laser_Beam_Core")
    bsdf_b = get_node_by_type(mat_beam.node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_b.inputs["Base Color"].default_value = (0.85, 0.95, 1.0, 1.0)
    bsdf_b.inputs["Emission Color"].default_value = (0.55, 0.85, 1.0, 1.0)
    bsdf_b.inputs["Emission Strength"].default_value = 0.0
    mats["beam"] = mat_beam

    # 6b. Coaxial Electric-Blue Laser Sheath (3D cylindrical Layer-Weight Facing falloff)
    mat_sheath = bpy.data.materials.new("Laser_Beam_Sheath")
    nt_sh = mat_sheath.node_tree
    n_sh, l_sh = nt_sh.nodes, nt_sh.links
    n_sh.clear()
    out_sh = n_sh.new("ShaderNodeOutputMaterial")
    mix_sh = n_sh.new("ShaderNodeMixShader")
    transp_sh = n_sh.new("ShaderNodeBsdfTransparent")
    emit_sh = n_sh.new("ShaderNodeEmission")
    emit_sh.inputs["Color"].default_value = (0.05, 0.46, 1.0, 1.0)
    emit_sh.inputs["Strength"].default_value = 0.0
    lw_sh = n_sh.new("ShaderNodeLayerWeight")
    lw_sh.inputs["Blend"].default_value = 0.5
    sub_sh = n_sh.new("ShaderNodeMath")
    sub_sh.operation = "SUBTRACT"
    sub_sh.inputs[0].default_value = 1.0
    sub_sh.use_clamp = True
    l_sh.new(lw_sh.outputs["Facing"], sub_sh.inputs[1])
    pow_sh = n_sh.new("ShaderNodeMath")
    pow_sh.operation = "POWER"
    pow_sh.inputs[1].default_value = 2.8
    l_sh.new(sub_sh.outputs["Value"], pow_sh.inputs[0])
    l_sh.new(pow_sh.outputs["Value"], mix_sh.inputs["Fac"])
    l_sh.new(transp_sh.outputs["BSDF"], mix_sh.inputs[1])
    l_sh.new(emit_sh.outputs["Emission"], mix_sh.inputs[2])
    l_sh.new(mix_sh.outputs["Shader"], out_sh.inputs["Surface"])
    mats["beam_sheath"] = mat_sheath

    # 7. Procedural Optical Plasma Halo, Atmospheric Blue Glow & Anamorphic Glint Shader
    def make_radial_glow_mat(name: str, color: tuple[float, float, float], exponent: float = 3.5) -> bpy.types.Material:
        mat = bpy.data.materials.new(name)
        nt_g = mat.node_tree
        n_g, l_g = nt_g.nodes, nt_g.links
        n_g.clear()

        out_g = n_g.new("ShaderNodeOutputMaterial")
        mix_g = n_g.new("ShaderNodeMixShader")
        transp_g = n_g.new("ShaderNodeBsdfTransparent")
        emit_g = n_g.new("ShaderNodeEmission")
        emit_g.inputs["Color"].default_value = (*color, 1.0)
        emit_g.inputs["Strength"].default_value = 0.0

        tc = n_g.new("ShaderNodeTexCoord")
        vec_len = n_g.new("ShaderNodeVectorMath")
        vec_len.operation = "LENGTH"
        l_g.new(tc.outputs["Object"], vec_len.inputs[0])

        map_r = n_g.new("ShaderNodeMapRange")
        map_r.inputs["From Min"].default_value = 0.0
        map_r.inputs["From Max"].default_value = 0.48
        map_r.inputs["To Min"].default_value = 1.0
        map_r.inputs["To Max"].default_value = 0.0
        map_r.clamp = True
        l_g.new(vec_len.outputs["Value"], map_r.inputs["Value"])

        pow_node = n_g.new("ShaderNodeMath")
        pow_node.operation = "POWER"
        pow_node.inputs[1].default_value = exponent
        l_g.new(map_r.outputs["Result"], pow_node.inputs[0])

        l_g.new(pow_node.outputs["Value"], mix_g.inputs["Fac"])
        l_g.new(transp_g.outputs["BSDF"], mix_g.inputs[1])
        l_g.new(emit_g.outputs["Emission"], mix_g.inputs[2])
        l_g.new(mix_g.outputs["Shader"], out_g.inputs["Surface"])
        return mat

    # Rich Electric-Blue / Sapphire-Cyan optical palettes
    mats["plasma_halo"] = make_radial_glow_mat("Laser_Plasma_Halo", (0.22, 0.65, 1.0), exponent=4.2)
    mats["molten_contact"] = make_radial_glow_mat("Laser_Molten_Contact_Mat", (0.38, 0.78, 1.0), exponent=4.4)
    mats["ember_halo"] = make_radial_glow_mat("Laser_Ember_Halo", (0.18, 0.56, 0.98), exponent=4.0)
    mats["blue_atmo_glow"] = make_radial_glow_mat("Laser_Blue_Atmo_Glow", (0.08, 0.44, 1.0), exponent=3.2)
    mats["under_pierce_halo"] = make_radial_glow_mat("Under_Pierce_Halo", (0.0, 0.0, 0.0), exponent=4.0)

    # 8. Top-Spine 3D Cold-Precision Machined Kerf Horizon Line (zero orange/red hot-spot!)
    mat_slot = bpy.data.materials.new("Top_Spine_Thermal_Horizon")
    bsdf_sl = get_node_by_type(mat_slot.node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_sl.inputs["Base Color"].default_value = (0.015, 0.018, 0.022, 1.0)
    bsdf_sl.inputs["Emission Color"].default_value = (0.36, 0.74, 1.0, 1.0)
    bsdf_sl.inputs["Emission Strength"].default_value = 0.0
    mats["slot"] = mat_slot

    # 9. Fine Top-Crown Cold-Precision Plasma Micro-Sparks (Actinic Ice-Blue / Sapphire-White — zero orange slag)
    mat_spark = bpy.data.materials.new("Laser_Plasma_Sparks")
    bsdf_sp = get_node_by_type(mat_spark.node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_sp.inputs["Base Color"].default_value = (0.80, 0.92, 1.0, 1.0)
    bsdf_sp.inputs["Emission Color"].default_value = (0.45, 0.80, 1.0, 1.0)
    bsdf_sp.inputs["Emission Strength"].default_value = 0.0
    mats["spark"] = mat_spark

    return mats


# ==============================================================================
# GEOMETRY BUILDERS (BMESH DATA API — NO UI OPERATORS)
# ==============================================================================
def create_lathed_profile(
    name: str,
    profile_xr: list[tuple[float, float]],
    segments: int = 96,
    material: bpy.types.Material | None = None,
) -> bpy.types.Object:
    """Revolve an (x, radius) profile around the X axis to create a precision cylindrical part."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    rings: list[list[bmesh.types.BMVert]] = []
    for x_val, r_val in profile_xr:
        ring: list[bmesh.types.BMVert] = []
        for i in range(segments):
            angle = (2.0 * math.pi * i) / segments
            y_val = r_val * math.cos(angle)
            z_val = r_val * math.sin(angle)
            ring.append(bm.verts.new((x_val, y_val, z_val)))
        rings.append(ring)

    for r_idx in range(len(rings) - 1):
        r0 = rings[r_idx]
        r1 = rings[r_idx + 1]
        for i in range(segments):
            i_next = (i + 1) % segments
            bm.faces.new((r0[i], r0[i_next], r1[i_next], r1[i]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for face in bm.faces:
        nx = abs(face.normal.x)
        face.smooth = nx < 0.65

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def build_pipe_and_red_ends(mats: dict[str, bpy.types.Material]) -> dict[str, bpy.types.Object]:
    objs: dict[str, bpy.types.Object] = {}
    r_out = PIPE_OD_M / 2.0   # 0.05715 m (4.5" OD)
    r_in = PIPE_ID_M / 2.0    # 0.05025 m
    x_start = PIPE_X_START    # -1.600 m
    x_end = PIPE_X_END        # +1.600 m (3.200 m total length)
    chamfer = 0.0025

    # 1. 3.20 m 4.5" OD Hollow Liner Pipe (x = -1.600 m to +1.600 m)
    pipe_profile = [
        (x_start, r_in),
        (x_start, r_out - chamfer),
        (x_start + chamfer, r_out),
        (0.0, r_out),
        (x_end - chamfer, r_out),
        (x_end, r_out - chamfer),
        (x_end, r_in),
        (x_start, r_in),
    ]
    objs["pipe"] = create_lathed_profile("Liner_Pipe_4_5in_3_2m", pipe_profile, segments=128, material=mats["pipe"])

    # 1b. Deep Matte-Black Internal Pipe Bore Liner
    bore_profile = [
        (x_start + 0.012, 0.0),
        (x_start + 0.012, r_in - 0.0005),
        (x_start + 0.250, r_in - 0.0005),
        (x_start + 0.250, 0.0),
    ]
    objs["bore_plug"] = create_lathed_profile("Pipe_Internal_Bore_Shadow", bore_profile, segments=64, material=mats["wiper"])

    # 2. Machined thread-standoff bands adjacent to the red coupling and thread protector
    x_left_shoulder = x_start + 0.140
    standoff_left = [
        (x_left_shoulder - 0.002, r_out + 0.0002),
        (x_left_shoulder + 0.008, r_out + 0.0002),
        (x_left_shoulder + 0.008, r_out - 0.001),
    ]
    objs["standoff_left"] = create_lathed_profile("Thread_Standoff_Left", standoff_left, segments=96, material=mats["machined"])

    x_right_shoulder = x_end - 0.120
    standoff_right = [
        (x_right_shoulder - 0.008, r_out - 0.001),
        (x_right_shoulder - 0.008, r_out + 0.0002),
        (x_right_shoulder + 0.002, r_out + 0.0002),
    ]
    objs["standoff_right"] = create_lathed_profile("Thread_Standoff_Right", standoff_right, segments=96, material=mats["machined"])

    # 3. Red API 4.5" Box Coupling on Left End
    r_coup = COUPLING_OD_M / 2.0
    x_c0 = x_start - 0.055
    x_c1 = x_c0 + COUPLING_LEN_M
    x_cmid = 0.5 * (x_c0 + x_c1)
    bev = 0.0045
    coupling_profile = [
        (x_c0 + 0.006, r_out - 0.0015),
        (x_c0, r_out + 0.0015),
        (x_c0, r_coup - bev),
        (x_c0 + bev, r_coup),
        (x_cmid - 0.005, r_coup),
        (x_cmid - 0.003, r_coup - 0.0014),
        (x_cmid + 0.003, r_coup - 0.0014),
        (x_cmid + 0.005, r_coup),
        (x_c1 - bev, r_coup),
        (x_c1, r_coup - bev),
        (x_c1, r_out + 0.0001),
        (x_c0 + 0.006, r_out + 0.0001),
    ]
    objs["coupling"] = create_lathed_profile("Red_Coupling_Box_Left", coupling_profile, segments=96, material=mats["red"])

    # 3b. Machined Internal Buttress Thread Sleeve inside the left coupling
    thread_profile: list[tuple[float, float]] = [(x_c0 + 0.005, r_out + 0.0012)]
    n_threads = 8
    t_pitch = 0.0055
    for t_i in range(n_threads):
        tx = x_c0 + 0.006 + t_i * t_pitch
        thread_profile.append((tx, r_out - 0.0012))
        thread_profile.append((tx + t_pitch * 0.55, r_out - 0.0026))
    thread_profile.append((x_start + 0.002, r_in))
    objs["coupling_threads"] = create_lathed_profile(
        "Coupling_Internal_Threads_Left", thread_profile, segments=96, material=mats["machined"]
    )

    # 4. Red Pin-End Thread Protector on Right End
    r_prot = PROTECTOR_OD_M / 2.0
    x_p0 = x_end - 0.120
    x_p1 = x_p0 + PROTECTOR_LEN_M
    p_bev = 0.0040
    protector_profile = [
        (x_p0, r_out + 0.0001),
        (x_p0, r_prot - p_bev),
        (x_p0 + p_bev, r_prot),
        (x_p0 + 0.035, r_prot),
        (x_p0 + 0.040, r_prot - 0.0022),
        (x_p0 + 0.058, r_prot - 0.0022),
        (x_p0 + 0.062, r_prot + 0.0016),
        (x_p1 - 0.020, r_prot + 0.0016),
        (x_p1 - p_bev, r_prot),
        (x_p1, r_prot - p_bev),
        (x_p1, r_in * 0.65),
        (x_p1 - 0.014, r_in * 0.65),
        (x_p1 - 0.014, 0.0),
    ]
    objs["protector"] = create_lathed_profile("Red_Thread_Protector_Right", protector_profile, segments=96, material=mats["red"])

    return objs


def build_mysterious_laser_head(mats: dict[str, bpy.types.Material]) -> dict[str, bpy.types.Object]:
    """Look-Dev v10b:
    1. Overhead Equipment Structure (`Linear_Rail_Track`):
       - A sleek horizontal CNC gantry bridge beam (`z = 0.365..0.440 m`, `x = -1.75..+1.75 m`) with precision
         sculpted rail ways.
       - Nearly invisible in Beat 1 darkness (`top_rim = 0.14 W`), then illuminated into a recognizable equipment
         silhouette when the blue laser glow fires in Beat 2 (so the laser head never looks like it is floating!).
    2. X-Axis Gantry Saddle & Z-Column Clamping Collar (`Laser_X_Saddle`):
       - Rides horizontally along the overhead gantry beam (`x = -0.055 m -> +0.055 m`) directly centered above
         the vertical laser head!
    3. Moving Vertical Optical Laser Head (`Laser_Machined_Carriage`, parented to `Laser_X_Saddle`):
       - Proportionate to the 4.5" (`114.3 mm`) pipe (`48 mm` barrel OD), with an upper Z-axis guide column and
         accordion bellows extending up into `Laser_X_Saddle` so as it lowers `62 mm` in Z during Beat 1b, it stays
         100% coaxially connected to the overhead saddle and gantry!
    """
    objs: dict[str, bpy.types.Object] = {}
    r_pipe = PIPE_OD_M / 2.0  # 0.05715 m
    aperture_tip_z = r_pipe + STANDOFF_GAP_M  # 0.12515 m at cutting standoff (0.18715 m when raised +62 mm!)

    # 1. Overhead Horizontal Gantry Bridge Beam (`Linear_Rail_Track`)
    mesh_rail = bpy.data.meshes.new("Linear_Rail_Track")
    bm_r = bmesh.new()

    rail_yz = [
        (-0.0420, 0.3680),
        (+0.0420, 0.3680),
        (+0.0480, 0.3730),
        (+0.0480, 0.3880),
        (+0.0360, 0.3940),
        (+0.0360, 0.4080),
        (+0.0520, 0.4150),
        (+0.0520, 0.4380),
        (+0.0440, 0.4450),
        (-0.0440, 0.4450),
        (-0.0520, 0.4380),
        (-0.0520, 0.4150),
        (-0.0360, 0.4080),
        (-0.0360, 0.3940),
        (-0.0480, 0.3880),
        (-0.0480, 0.3730),
    ]

    x_left = -1.750
    x_right = +1.750
    ring_left = [bm_r.verts.new((x_left, y, z)) for y, z in rail_yz]
    ring_right = [bm_r.verts.new((x_right, y, z)) for y, z in rail_yz]

    n_pts = len(rail_yz)
    for i in range(n_pts):
        inext = (i + 1) % n_pts
        f = bm_r.faces.new((ring_left[i], ring_right[i], ring_right[inext], ring_left[inext]))
        f.smooth = False
        f.material_index = 0

    f_l = bm_r.faces.new(ring_left)
    f_l.smooth = False
    f_l.material_index = 0
    f_r = bm_r.faces.new(reversed(ring_right))
    f_r.smooth = False
    f_r.material_index = 0

    bmesh.ops.recalc_face_normals(bm_r, faces=bm_r.faces)
    bm_r.to_mesh(mesh_rail)
    bm_r.free()

    obj_rail = bpy.data.objects.new("Linear_Rail_Track", mesh_rail)
    bpy.context.scene.collection.objects.link(obj_rail)
    obj_rail.data.materials.append(mats["rail"])
    obj_rail.data.materials.append(mats["steel"])
    obj_rail.data.materials.append(mats["stainless"])
    objs["rail"] = obj_rail
    objs["head_shroud"] = obj_rail

    # 2. X-Axis Gantry Saddle & Coaxial Z-Column Clamping Collar (`Laser_X_Saddle`)
    # Moves horizontally (`x_shuttle`) along the gantry rail so the collar is ALWAYS coaxial with the laser head!
    mesh_sad = bpy.data.meshes.new("Laser_X_Saddle")
    bm_sad = bmesh.new()

    saddle_yz = [
        (-0.0460, 0.3420),
        (+0.0460, 0.3420),
        (+0.0540, 0.3500),
        (+0.0540, 0.3720),
        (-0.0540, 0.3720),
        (-0.0540, 0.3500),
    ]
    sx0, sx1 = -0.185, +0.185
    s_left = [bm_sad.verts.new((sx0, y, z)) for y, z in saddle_yz]
    s_right = [bm_sad.verts.new((sx1, y, z)) for y, z in saddle_yz]
    for i in range(len(saddle_yz)):
        inext = (i + 1) % len(saddle_yz)
        f = bm_sad.faces.new((s_left[i], s_right[i], s_right[inext], s_left[inext]))
        f.smooth = False
        f.material_index = 1
    bm_sad.faces.new(s_left).material_index = 1
    bm_sad.faces.new(reversed(s_right)).material_index = 1

    collar_segs = [
        (0.3040, 0.0310, 0.3075, 0.0365, 2),
        (0.3075, 0.0365, 0.3260, 0.0365, 1),
        (0.3260, 0.0365, 0.3290, 0.0410, 2),
        (0.3290, 0.0410, 0.3440, 0.0410, 1),
    ]
    n_c = 64
    for z0, r0, z1, r1, mat_idx in collar_segs:
        c_r0 = []
        c_r1 = []
        for i in range(n_c):
            a = (2.0 * math.pi * i) / n_c
            ca, sa = math.cos(a), math.sin(a)
            c_r0.append(bm_sad.verts.new((r0 * ca, r0 * sa, z0)))
            c_r1.append(bm_sad.verts.new((r1 * ca, r1 * sa, z1)))
        for i in range(n_c):
            inext = (i + 1) % n_c
            f = bm_sad.faces.new((c_r0[i], c_r0[inext], c_r1[inext], c_r1[i]))
            f.smooth = True
            f.material_index = mat_idx

    bmesh.ops.recalc_face_normals(bm_sad, faces=bm_sad.faces)
    bm_sad.to_mesh(mesh_sad)
    bm_sad.free()

    obj_saddle = bpy.data.objects.new("Laser_X_Saddle", mesh_sad)
    bpy.context.scene.collection.objects.link(obj_saddle)
    obj_saddle.data.materials.append(mats["rail"])
    obj_saddle.data.materials.append(mats["steel"])
    obj_saddle.data.materials.append(mats["stainless"])
    objs["x_saddle"] = obj_saddle

    # 3. Moving Vertical Optical Laser Head (`Laser_Machined_Carriage`, parented to `obj_saddle`)
    # Built in cutting-standoff coordinates (`tip_z = 0.12515 m`), with an upper Z-spindle & bellows extending to `z = 0.365 m`
    # so whether it is at `z_offset = +0.062 m` (Beat 1a) or `z_offset = 0.000 m` (Beat 1c/2/3), it is seamlessly held inside `obj_saddle`!
    mesh_c = bpy.data.meshes.new("Laser_Machined_Carriage")
    bm = bmesh.new()

    lathe_segments: list[tuple[float, float, float, float, int, bool]] = []

    def add_lathe_seg(z0: float, r0: float, z1: float, r1: float, mat_i: int, is_smooth: bool = True) -> None:
        lathe_segments.append((z0, r0, z1, r1, mat_i, is_smooth))

    tip_z = aperture_tip_z  # 0.12515 m

    # --- Section 1: Internal Optical Bore & Steep Coaxial Conical Laser Nozzle (z = 0.12515 .. 0.1580 m) ---
    add_lathe_seg(tip_z + 0.0050, 0.0014, tip_z, 0.0016, 3, False)
    add_lathe_seg(tip_z, 0.0016, tip_z, 0.0028, 6, False)
    add_lathe_seg(tip_z, 0.0028, 0.1350, 0.0052, 6, True)
    add_lathe_seg(0.1350, 0.0052, 0.1545, 0.0118, 6, True)
    add_lathe_seg(0.1545, 0.0118, 0.1560, 0.0102, 3, False)
    add_lathe_seg(0.1560, 0.0102, 0.1580, 0.0102, 3, True)

    # --- Section 2: Warm Smoked-Bronze Optical Sensor Collar (z = 0.1580 .. 0.1730 m) ---
    add_lathe_seg(0.1580, 0.0102, 0.1592, 0.0138, 5, False)
    add_lathe_seg(0.1592, 0.0138, 0.1682, 0.0138, 5, True)
    add_lathe_seg(0.1682, 0.0138, 0.1695, 0.0116, 5, False)
    add_lathe_seg(0.1695, 0.0116, 0.1718, 0.0116, 3, True)
    add_lathe_seg(0.1718, 0.0116, 0.1730, 0.0138, 2, False)

    # --- Section 3: Tapered Focusing Optic Housing (z = 0.1730 .. 0.2120 m) ---
    add_lathe_seg(0.1730, 0.0138, 0.2090, 0.0245, 0, True)
    add_lathe_seg(0.2090, 0.0245, 0.2110, 0.0252, 2, True)
    add_lathe_seg(0.2110, 0.0252, 0.2120, 0.0245, 2, False)

    # --- Section 4: Cylindrical Collimator Barrel with 3 Architectural Cooling Channels (z = 0.2120 .. 0.2680 m) ---
    cur_z = 0.2120
    for land_idx in range(4):
        add_lathe_seg(cur_z, 0.0245, cur_z + 0.0100, 0.0245, 0, True)
        cur_z += 0.0100
        if land_idx < 3:
            add_lathe_seg(cur_z, 0.0245, cur_z + 0.0008, 0.0185, 2, False)
            add_lathe_seg(cur_z + 0.0008, 0.0185, cur_z + 0.0044, 0.0185, 3, True)
            add_lathe_seg(cur_z + 0.0044, 0.0185, cur_z + 0.0052, 0.0245, 2, False)
            cur_z += 0.0052

    # --- Section 5: Upper Z-Axis Telescope Column & Accordion Bellows into the Overhead Machine Collar (z = 0.2676 .. 0.3650 m) ---
    add_lathe_seg(cur_z, 0.0245, cur_z + 0.0020, 0.0275, 2, False)
    add_lathe_seg(cur_z + 0.0020, 0.0275, cur_z + 0.0120, 0.0275, 1, True)
    add_lathe_seg(cur_z + 0.0120, 0.0275, cur_z + 0.0135, 0.0220, 2, False)
    cur_z += 0.0135
    for _rib in range(7):
        add_lathe_seg(cur_z, 0.0220, cur_z + 0.0055, 0.0265, 3, False)
        add_lathe_seg(cur_z + 0.0055, 0.0265, cur_z + 0.0110, 0.0220, 3, False)
        cur_z += 0.0110
    add_lathe_seg(cur_z, 0.0220, 0.3680, 0.0220, 2, True)

    n_lathe = 96
    for z0, r0, z1, r1, mat_i, is_smooth in lathe_segments:
        ring0 = []
        ring1 = []
        for i in range(n_lathe):
            a = (2.0 * math.pi * i) / n_lathe
            ca, sa = math.cos(a), math.sin(a)
            ring0.append(bm.verts.new((r0 * ca, r0 * sa, z0)))
            ring1.append(bm.verts.new((r1 * ca, r1 * sa, z1)))
        for i in range(n_lathe):
            inext = (i + 1) % n_lathe
            f = bm.faces.new((ring0[i], ring0[inext], ring1[inext], ring1[i]))
            f.smooth = is_smooth
            f.material_index = mat_i

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh_c)
    bm.free()

    obj_carriage = bpy.data.objects.new("Laser_Machined_Carriage", mesh_c)
    bpy.context.scene.collection.objects.link(obj_carriage)
    obj_carriage.data.materials.append(mats["carriage"])   # Slot 0
    obj_carriage.data.materials.append(mats["steel"])      # Slot 1
    obj_carriage.data.materials.append(mats["stainless"])  # Slot 2
    obj_carriage.data.materials.append(mats["wiper"])      # Slot 3
    obj_carriage.data.materials.append(mats["ceramic"])    # Slot 4
    obj_carriage.data.materials.append(mats["brass"])      # Slot 5
    obj_carriage.data.materials.append(mats["nozzle"])     # Slot 6
    obj_carriage.parent = obj_saddle

    objs["carriage"] = obj_carriage
    objs["nozzle"] = obj_carriage

    return objs


def build_center_slot_and_laser_fx(
    mats: dict[str, bpy.types.Material],
    shuttle_obj: bpy.types.Object,
) -> dict[str, bpy.types.Object]:
    """Look-Dev v10b ("Horizontal 4.5-Inch Pipe — Z-Descent, Pause, Blue Laser & Machine Silhouette Reveal"):
    - Above Pipe (`z = 0.05715 .. 0.12515 m`): Needle-thin sapphire-white core + coaxial electric-blue sheath +
      subtle vertical blue atmospheric bloom around the beam and nozzle.
    - Below Pipe: Strictly ZERO sparks and ZERO glow beneath the pipe.
    - Pipe Wall: Strictly ZERO thermal hot-spot or glossy white blob on the pipe surface.
    """
    objs: dict[str, bpy.types.Object] = {}
    r_pipe = PIPE_OD_M / 2.0  # 0.05715 m
    standoff_gap_m = STANDOFF_GAP_M  # 0.0680 m vertical beam length
    beam_mid_z = r_pipe + 0.5 * standoff_gap_m  # 0.09115 m

    to_cam_xy = Vector((CAM_LOCATION.x, CAM_LOCATION.y, 0.0)).normalized()
    quad_yaw_z = math.atan2(to_cam_xy.x, -to_cam_xy.y)

    # 1. 3D Top-Spine Cold-Precision Machined Kerf Hairline (anchored at x = -0.055 m, grows to +0.055 m behind beam!)
    mesh_slot = bpy.data.meshes.new("Top_Spine_Thermal_Edge")
    bm_s = bmesh.new()
    bmesh.ops.create_cone(
        bm_s,
        cap_ends=True,
        cap_tris=True,
        segments=24,
        radius1=0.00042,
        radius2=0.00042,
        depth=SLOT_LEN_M,
    )
    bmesh.ops.rotate(bm_s, verts=bm_s.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90.0), 3, "Y"))
    for v in bm_s.verts:
        v.co.x += 0.5 * SLOT_LEN_M
        v.co.z = r_pipe + 0.00022 + v.co.z * 0.35
    for f in bm_s.faces:
        f.smooth = True
    bm_s.to_mesh(mesh_slot)
    bm_s.free()

    obj_slot = bpy.data.objects.new("Top_Spine_Thermal_Edge", mesh_slot)
    bpy.context.scene.collection.objects.link(obj_slot)
    obj_slot.location = Vector((-0.5 * SLOT_LEN_M, 0.0, 0.0))
    obj_slot.data.materials.append(mats["slot"])
    obj_slot.visible_shadow = False
    obj_slot.visible_diffuse = False
    obj_slot.visible_glossy = False
    objs["slot"] = obj_slot

    # 2a. Layer 1 — Surgical Needle-Thin Electric Blue-White Core (1.2 mm waist at pipe -> 1.7 mm at nozzle tip)
    mesh_beam = bpy.data.meshes.new("Laser_Beam_Jet")
    bm_b = bmesh.new()
    bmesh.ops.create_cone(
        bm_b,
        cap_ends=True,
        cap_tris=False,
        segments=32,
        radius1=0.00060,
        radius2=0.00085,
        depth=standoff_gap_m + 0.0030,
    )
    for v in bm_b.verts:
        v.co.z += beam_mid_z + 0.0010
        v.co.y = 0.0
    bm_b.to_mesh(mesh_beam)
    bm_b.free()

    obj_beam = bpy.data.objects.new("Laser_Beam_Jet", mesh_beam)
    bpy.context.scene.collection.objects.link(obj_beam)
    obj_beam.data.materials.append(mats["beam"])
    obj_beam.visible_shadow = False
    obj_beam.visible_diffuse = False
    obj_beam.visible_glossy = False
    obj_beam.parent = shuttle_obj
    objs["beam"] = obj_beam

    # 2b. Layer 2 — Coaxial Electric-Blue Optical Sheath Cylinder (3.6 mm -> 4.6 mm diameter)
    mesh_sheath = bpy.data.meshes.new("Laser_Beam_Sheath_Cyl")
    bm_sh = bmesh.new()
    bmesh.ops.create_cone(
        bm_sh,
        cap_ends=False,
        cap_tris=False,
        segments=32,
        radius1=0.0018,
        radius2=0.0023,
        depth=standoff_gap_m + 0.0020,
    )
    for v in bm_sh.verts:
        v.co.z += beam_mid_z + 0.0005
        v.co.y = 0.0
    for f in bm_sh.faces:
        f.smooth = True
    bm_sh.to_mesh(mesh_sheath)
    bm_sh.free()

    obj_sheath = bpy.data.objects.new("Laser_Beam_Sheath_Cyl", mesh_sheath)
    bpy.context.scene.collection.objects.link(obj_sheath)
    obj_sheath.data.materials.append(mats["beam_sheath"])
    obj_sheath.visible_shadow = False
    obj_sheath.visible_diffuse = False
    obj_sheath.visible_glossy = False
    obj_sheath.parent = shuttle_obj
    objs["beam_sheath"] = obj_sheath

    # 3. Camera-facing Optical Glow Quads (visible_diffuse=False, visible_glossy=False so ZERO pipe reflection hotspot!)
    def make_glow_quad(
        name: str,
        scale_x: float,
        scale_z: float,
        z_pos: float,
        mat: bpy.types.Material,
        parent: bpy.types.Object | None = None,
        face_camera: bool = True,
    ) -> bpy.types.Object:
        m_q = bpy.data.meshes.new(name)
        bm_q = bmesh.new()
        bmesh.ops.create_grid(bm_q, x_segments=16, y_segments=16, size=1.0)
        bmesh.ops.rotate(bm_q, verts=bm_q.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90.0), 3, "X"))
        bm_q.to_mesh(m_q)
        bm_q.free()
        o_q = bpy.data.objects.new(name, m_q)
        bpy.context.scene.collection.objects.link(o_q)
        offset_xy = to_cam_xy * 0.006 if face_camera else Vector((0.0, -0.005, 0.0))
        o_q.location = Vector((offset_xy.x, offset_xy.y, z_pos))
        if face_camera:
            o_q.rotation_euler = (0.0, 0.0, quad_yaw_z)
        o_q.scale = Vector((scale_x, 1.0, scale_z))
        o_q.data.materials.append(mat)
        o_q.visible_shadow = False
        o_q.visible_diffuse = False
        o_q.visible_glossy = False
        if parent is not None:
            o_q.parent = parent
        return o_q

    # 3a. Surgical 6.5 mm x 4.0 mm sapphire-blue keyhole pinpoint right where the needle beam touches the 12 o'clock crown
    objs["plasma_bloom"] = make_glow_quad("Laser_Plasma_Bloom", 0.0065, 0.0040, r_pipe + 0.0009, mats["plasma_halo"], shuttle_obj)
    # 3b. Tight 10 mm x 3.2 mm cool electric-blue ionization cushion hugging the 12 o'clock crown (zero hot-spot!)
    objs["molten_contact"] = make_glow_quad("Laser_Molten_Contact_Pool", 0.0100, 0.0032, r_pipe + 0.0008, mats["molten_contact"], shuttle_obj)
    # 3c. Crisp blue optical exit glint right at the conical nozzle orifice (z = 0.12515 m)
    objs["nozzle_glint"] = make_glow_quad("Laser_Nozzle_Exit_Glint", 0.011, 0.011, r_pipe + standoff_gap_m, mats["plasma_halo"], shuttle_obj)
    # 3d. Razor-thin horizontal blue anamorphic optical lens streak at the pierce point
    objs["anamorphic_streak"] = make_glow_quad("Laser_Anamorphic_Streak", 0.120, 0.0018, r_pipe + 0.0011, mats["plasma_halo"], shuttle_obj)
    # 3e. Subtle Elliptical Electric-Blue Beam Aura centered along the vertical laser shaft (`z = beam_mid_z + 0.010 m`)
    # Softly wraps the blue laser beam & nozzle tip without looking like a cartoon round ball!
    objs["blue_atmo_glow"] = make_glow_quad("Laser_Blue_Atmo_Glow_Quad", 0.055, 0.095, beam_mid_z + 0.008, mats["blue_atmo_glow"], shuttle_obj)
    # 3f. Whisper-faint cool silver-blue assist-gas vapor wisp above the 110 mm top spine
    objs["ember_shimmer"] = make_glow_quad("Top_Spine_Ember_Shimmer", 0.075, 0.0050, r_pipe + 0.0022, mats["ember_halo"], None, face_camera=False)
    # 3g. Dummy hidden under-exit quad (permanently hidden & 0 emission)
    objs["under_exit_glow"] = make_glow_quad("Under_Pipe_Exit_Glow", 0.001, 0.001, -r_pipe - 0.0025, mats["under_pierce_halo"], shuttle_obj)

    # 4. Fine Top-Crown Low-Angle Cold Blue Plasma Micro-Sparks ONLY (Strictly ZERO bottom-side sparks!)
    mesh_sparks = bpy.data.meshes.new("Laser_Micro_Sparks")
    bm_sp = bmesh.new()

    top_origin = Vector((0.0, 0.0, r_pipe + 0.0008))
    top_spark_vectors = [
        (-0.016, -0.003, 0.0058, 0.00025),
        (-0.025, -0.004, 0.0034, 0.00022),
        (0.015, -0.003, 0.0055, 0.00025),
        (0.023, 0.003, 0.0030, 0.00022),
        (-0.009, -0.003, 0.0078, 0.00022),
        (0.008, 0.003, 0.0074, 0.00022),
        (-0.004, -0.002, 0.0095, 0.00020),
        (0.004, 0.002, 0.0090, 0.00020),
    ]
    for dx, dy, dz, rad in top_spark_vectors:
        tip = top_origin + Vector((dx, dy, dz))
        mid = top_origin.lerp(tip, 0.5)
        vec = tip - top_origin
        ret = bmesh.ops.create_cone(
            bm_sp, cap_ends=True, cap_tris=True, segments=8, radius1=rad, radius2=rad * 0.18, depth=vec.length
        )
        rot_mat = vec.normalized().to_track_quat("Z", "X").to_matrix().to_4x4()
        bmesh.ops.transform(bm_sp, matrix=Matrix.Translation(mid) @ rot_mat, verts=ret["verts"])

    bm_sp.to_mesh(mesh_sparks)
    bm_sp.free()
    obj_sparks = bpy.data.objects.new("Laser_Micro_Sparks", mesh_sparks)
    bpy.context.scene.collection.objects.link(obj_sparks)
    obj_sparks.data.materials.append(mats["spark"])
    obj_sparks.visible_shadow = False
    obj_sparks.visible_diffuse = False
    obj_sparks.visible_glossy = False
    obj_sparks.parent = shuttle_obj
    objs["sparks"] = obj_sparks

    return objs


# ==============================================================================
# LIGHTING, WORLD & CAMERA (HORIZONTAL 4.5" HERO + MACHINE SILHOUETTE REVEAL)
# ==============================================================================
def setup_world_and_lights(
    scene: bpy.types.Scene,
    pipe_objs: dict[str, bpy.types.Object],
    head_objs: dict[str, bpy.types.Object],
) -> dict[str, bpy.types.Object]:
    lights: dict[str, bpy.types.Object] = {}
    shuttle_obj = head_objs["nozzle"]

    col_pipe_recv = bpy.data.collections.new("LL_Pipe_Receivers")
    for k, obj in pipe_objs.items():
        if k != "bore_plug":
            col_pipe_recv.objects.link(obj)

    col_head_recv = bpy.data.collections.new("LL_Head_Receivers")
    if "carriage" in head_objs:
        col_head_recv.objects.link(head_objs["carriage"])

    col_rail_recv = bpy.data.collections.new("LL_Rail_Receivers")
    if "rail" in head_objs:
        col_rail_recv.objects.link(head_objs["rail"])
    if "x_saddle" in head_objs:
        col_rail_recv.objects.link(head_objs["x_saddle"])

    col_machine_recv = bpy.data.collections.new("LL_Machine_All_Receivers")
    if "carriage" in head_objs:
        col_machine_recv.objects.link(head_objs["carriage"])
    if "rail" in head_objs:
        col_machine_recv.objects.link(head_objs["rail"])
    if "x_saddle" in head_objs:
        col_machine_recv.objects.link(head_objs["x_saddle"])

    # 1. World Shader: Deep studio black (#000000) for camera rays; ultra-subtle studio reflection for dark steel
    world = bpy.data.worlds.new("Dark_Studio_World")
    scene.world = world
    nodes, links = world.node_tree.nodes, world.node_tree.links
    nodes.clear()

    env = nodes.new("ShaderNodeTexEnvironment")
    hdri_path = Path(bpy.utils.resource_path("LOCAL")) / "datafiles/studiolights/world/studio.exr"
    env.image = bpy.data.images.load(str(hdri_path), check_existing=True)

    hsv = nodes.new("ShaderNodeHueSaturation")
    hsv.inputs["Saturation"].default_value = 0.10
    links.new(env.outputs["Color"], hsv.inputs["Color"])

    bg_refl = nodes.new("ShaderNodeBackground")
    bg_refl.inputs["Strength"].default_value = 0.006
    links.new(hsv.outputs["Color"], bg_refl.inputs["Color"])

    bg_cam = nodes.new("ShaderNodeBackground")
    bg_cam.inputs["Color"].default_value = (0.0003, 0.0004, 0.0006, 1.0)
    bg_cam.inputs["Strength"].default_value = 1.0

    light_path = nodes.new("ShaderNodeLightPath")
    mix = nodes.new("ShaderNodeMixShader")
    links.new(light_path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    links.new(bg_refl.outputs["Background"], mix.inputs[1])
    links.new(bg_cam.outputs["Background"], mix.inputs[2])

    out = nodes.new("ShaderNodeOutputWorld")
    links.new(mix.outputs["Shader"], out.inputs["Surface"])

    def add_strip_light(
        name: str,
        location: tuple[float, float, float],
        target: tuple[float, float, float],
        energy: float,
        size_x_long: float,
        size_y_narrow: float,
        color: tuple[float, float, float] = (1.0, 1.0, 1.0),
        spread_deg: float = 180.0,
        receiver_col: bpy.types.Collection | None = None,
    ) -> bpy.types.Object:
        ldata = bpy.data.lights.new(name, "AREA")
        ldata.energy = energy
        ldata.shape = "RECTANGLE"
        ldata.size = size_x_long
        ldata.size_y = size_y_narrow
        ldata.color = color
        ldata.spread = math.radians(spread_deg)
        lobj = bpy.data.objects.new(name, ldata)
        scene.collection.objects.link(lobj)
        lobj.location = Vector(location)
        lobj.visible_camera = False
        if receiver_col is not None:
            lobj.light_linking.receiver_collection = receiver_col

        direction = (Vector(target) - Vector(location)).normalized()
        axis_x = Vector((1.0, 0.0, 0.0))
        long_side = (axis_x - direction * axis_x.dot(direction)).normalized()
        normal = -direction
        short_side = normal.cross(long_side).normalized()
        rot_mat = Matrix((long_side, short_side, normal)).transposed()
        lobj.rotation_euler = rot_mat.to_euler()
        return lobj

    # 2. Primary Pipe Upper-Shoulder Sheen Strip (spans the full 3.20 m horizontal 4.5" joint)
    lights["pipe_key_strip"] = add_strip_light(
        name="Pipe_Sheen_Key_Strip",
        location=(0.0, -1.45, 1.25),
        target=(0.0, 0.0, 0.038),
        energy=125.0,
        size_x_long=4.60,
        size_y_narrow=0.11,
        color=(0.90, 0.94, 1.0),
        spread_deg=145.0,
        receiver_col=col_pipe_recv,
    )

    # 3. Lower Edge Separation Strip (continuous lower grazing rim on the 4.5" pipe)
    lights["pipe_bottom_rim"] = add_strip_light(
        name="Pipe_Bottom_Rim_Strip",
        location=(0.0, -1.45, -1.15),
        target=(0.0, 0.0, -0.042),
        energy=65.0,
        size_x_long=4.60,
        size_y_narrow=0.09,
        color=(0.76, 0.84, 1.0),
        spread_deg=145.0,
        receiver_col=col_pipe_recv,
    )

    # 4. Left Coupling Kicker & Right Protector Kicker (symmetric for horizontal elevation)
    lights["left_coupling_kicker"] = add_strip_light(
        name="Left_Coupling_Kicker",
        location=(PIPE_X_START - 0.10, -1.25, 0.35),
        target=(PIPE_X_START + 0.04, 0.0, 0.0),
        energy=14.0,
        size_x_long=0.42,
        size_y_narrow=0.22,
        color=(1.0, 0.94, 0.90),
        spread_deg=42.0,
        receiver_col=col_pipe_recv,
    )
    lights["right_protector_kicker"] = add_strip_light(
        name="Right_Protector_Kicker",
        location=(PIPE_X_END + 0.10, -1.25, 0.35),
        target=(PIPE_X_END - 0.04, 0.0, 0.0),
        energy=14.0,
        size_x_long=0.42,
        size_y_narrow=0.22,
        color=(1.0, 0.94, 0.90),
        spread_deg=42.0,
        receiver_col=col_pipe_recv,
    )

    # 5a. Silky Studio Vertical Grazing Rim Strips on the Vertical Optical Laser Head (`col_head_recv` ONLY)
    # Ensures the laser head is clearly visible as it lowers in Beat 1b!
    lights["mystery_head_rim_left"] = add_strip_light(
        name="Mystery_Head_Rim_Left",
        location=(-0.95, -0.75, 0.245),
        target=(0.0, 0.0, 0.235),
        energy=7.2,
        size_x_long=0.26,
        size_y_narrow=0.52,
        color=(0.80, 0.88, 1.0),
        spread_deg=40.0,
        receiver_col=col_head_recv,
    )
    lights["mystery_head_rim_right"] = add_strip_light(
        name="Mystery_Head_Rim_Right",
        location=(+0.95, -0.75, 0.245),
        target=(0.0, 0.0, 0.235),
        energy=5.8,
        size_x_long=0.26,
        size_y_narrow=0.52,
        color=(0.80, 0.88, 1.0),
        spread_deg=40.0,
        receiver_col=col_head_recv,
    )

    # 5b. Whisper-Faint Static Baseline Rim on the Overhead Gantry Bridge (`col_rail_recv` ONLY)
    # Kept very low (0.14 W) so the overhead equipment is nearly hidden in the shadows during Beat 1,
    # and then dramatically revealed in silhouette when the blue laser glow fires in Beat 2!
    lights["mystery_head_top_rim"] = add_strip_light(
        name="Mystery_Head_Top_Rim",
        location=(0.0, -0.95, 0.48),
        target=(0.0, 0.0, 0.385),
        energy=0.14,
        size_x_long=2.20,
        size_y_narrow=0.06,
        color=(0.70, 0.82, 1.0),
        spread_deg=38.0,
        receiver_col=col_rail_recv,
    )

    # 6. Dynamic Laser Strike Lights (Light-linked to `col_machine_recv` ONLY so the blue glow reveals
    #    the laser head + overhead equipment silhouette without creating any hot-spot on the pipe!)
    # 6a. Dummy Pipe Flash Light (kept at 0.0 W permanently — zero pipe hot-spot)
    p_flash = bpy.data.lights.new("Laser_Strike_Optical_Flash", "POINT")
    p_flash.energy = 0.0
    p_flash.color = (0.20, 0.65, 1.0)
    p_flash.shadow_soft_size = 0.004
    obj_flash = bpy.data.objects.new("Laser_Strike_Optical_Flash", p_flash)
    scene.collection.objects.link(obj_flash)
    obj_flash.location = Vector((0.0, -0.010, PIPE_OD_M / 2.0 + 0.010))
    obj_flash.light_linking.receiver_collection = col_pipe_recv
    obj_flash.parent = shuttle_obj
    lights["laser_flash"] = obj_flash

    # 6b. Upward Electric-Blue Optical Bounce illuminating BOTH the Laser Head AND the Overhead Equipment Silhouette!
    # When the blue laser fires, this light flares up and washes the conical nozzle, cooling fins, Z-column bellows,
    # central clamping collar, and overhead gantry beam in electric-blue rim light (`col_machine_recv` ONLY!).
    p_bounce = bpy.data.lights.new("Laser_Head_Belly_Bounce", "POINT")
    p_bounce.energy = 0.0
    p_bounce.color = (0.12, 0.54, 1.0)
    p_bounce.shadow_soft_size = 0.035
    obj_bounce = bpy.data.objects.new("Laser_Head_Belly_Bounce", p_bounce)
    scene.collection.objects.link(obj_bounce)
    obj_bounce.location = Vector((0.0, -0.095, PIPE_OD_M / 2.0 + 0.065))
    obj_bounce.light_linking.receiver_collection = col_machine_recv
    obj_bounce.parent = shuttle_obj
    lights["head_belly_bounce"] = obj_bounce

    # 6c. Wide Overhead Gantry Silhouette Reveal Strip (`col_rail_recv` ONLY — flares during the blue laser glow
    #     so the viewer clearly sees the horizontal gantry equipment holding the laser head!)
    lights["gantry_blue_reveal"] = add_strip_light(
        name="Gantry_Silhouette_Blue_Reveal",
        location=(0.0, -0.55, 0.240),
        target=(0.0, 0.0, 0.380),
        energy=0.0,
        size_x_long=1.60,
        size_y_narrow=0.14,
        color=(0.10, 0.50, 1.0),
        spread_deg=88.0,
        receiver_col=col_rail_recv,
    )

    # 6d. Dummy Kerf Light & Under-Pipe Light (kept at 0.0 W permanently)
    p_ember = bpy.data.lights.new("Laser_Kerf_Warm_Glow", "POINT")
    p_ember.energy = 0.0
    p_ember.color = (0.20, 0.65, 1.0)
    p_ember.shadow_soft_size = 0.004
    obj_ember = bpy.data.objects.new("Laser_Kerf_Warm_Glow", p_ember)
    scene.collection.objects.link(obj_ember)
    obj_ember.location = Vector((0.0, -0.012, PIPE_OD_M / 2.0 + 0.006))
    obj_ember.light_linking.receiver_collection = col_pipe_recv
    lights["kerf_ember"] = obj_ember

    p_under = bpy.data.lights.new("Under_Pipe_Pierce_Light", "POINT")
    p_under.energy = 0.0
    p_under.color = (0.0, 0.0, 0.0)
    p_under.shadow_soft_size = 0.008
    obj_under = bpy.data.objects.new("Under_Pipe_Pierce_Light", p_under)
    scene.collection.objects.link(obj_under)
    obj_under.location = Vector((0.0, +0.004, -PIPE_OD_M / 2.0 - 0.018))
    obj_under.light_linking.receiver_collection = col_pipe_recv
    obj_under.parent = shuttle_obj
    lights["under_pierce_light"] = obj_under

    return lights


def setup_camera(scene: bpy.types.Scene) -> bpy.types.Object:
    """Look-Dev v10b: True Horizontal Elevation Camera (`4.15 m` in front of the `3.20 m` 4.5" pipe).
    Fits both the left Red API 4.5" Coupling and right Red Pin Protector cleanly inside the 16:9 frame
    from a horizontal perspective, while keeping the center laser head and Z-descent large and legible!
    """
    cam_data = bpy.data.cameras.new("Hero_Horizontal_4_5in_Cam")
    cam_data.lens = CAM_LENS_MM
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.05
    cam_data.clip_end = 100.0

    cam_obj = bpy.data.objects.new("Hero_Horizontal_4_5in_Cam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    cam_obj.location = CAM_LOCATION.copy()
    direction = CAM_TARGET - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    return cam_obj


# ==============================================================================
# ANIMATION TIMELINE (HIGH POISE -> Z-DESCENT -> PAUSE -> BLUE LASER & SILHOUETTE GLOW -> COLD AFTERMATH)
# ==============================================================================
def smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - edge0) / max(1e-6, edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def animate_laser_sequence(
    shuttle_obj: bpy.types.Object,
    fx_objs: dict[str, bpy.types.Object],
    lights: dict[str, bpy.types.Object],
    mats: dict[str, bpy.types.Material],
) -> None:
    bsdf_beam = get_node_by_type(mats["beam"].node_tree, "ShaderNodeBsdfPrincipled")
    emit_sheath = get_node_by_type(mats["beam_sheath"].node_tree, "ShaderNodeEmission")
    bsdf_slot = get_node_by_type(mats["slot"].node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_spark = get_node_by_type(mats["spark"].node_tree, "ShaderNodeBsdfPrincipled")
    emit_plasma = get_node_by_type(mats["plasma_halo"].node_tree, "ShaderNodeEmission")
    emit_molten = get_node_by_type(mats["molten_contact"].node_tree, "ShaderNodeEmission")
    emit_ember = get_node_by_type(mats["ember_halo"].node_tree, "ShaderNodeEmission")
    emit_atmo = get_node_by_type(mats["blue_atmo_glow"].node_tree, "ShaderNodeEmission")
    emit_under = get_node_by_type(mats["under_pierce_halo"].node_tree, "ShaderNodeEmission")

    flash_light = lights["laser_flash"].data
    bounce_light = lights["head_belly_bounce"].data
    gantry_reveal_light = lights["gantry_blue_reveal"].data
    ember_light = lights["kerf_ember"].data
    under_light = lights["under_pierce_light"].data

    sparks_obj = fx_objs["sparks"]
    beam_obj = fx_objs["beam"]
    sheath_obj = fx_objs["beam_sheath"]
    plasma_bloom = fx_objs["plasma_bloom"]
    molten_contact = fx_objs["molten_contact"]
    nozzle_glint = fx_objs["nozzle_glint"]
    anamorphic_streak = fx_objs["anamorphic_streak"]
    blue_atmo_glow = fx_objs["blue_atmo_glow"]
    ember_shimmer = fx_objs["ember_shimmer"]
    under_exit_glow = fx_objs["under_exit_glow"]
    slot_obj = fx_objs["slot"]

    strike_only_objs = (beam_obj, sheath_obj, sparks_obj, molten_contact, anamorphic_streak)
    pre_and_strike_objs = (plasma_bloom, nozzle_glint, blue_atmo_glow)

    saddle_obj = shuttle_obj.parent
    half_stroke = 0.5 * SLOT_LEN_M  # 0.055 m (110 mm total high-speed axial traverse)
    for f in range(FRAME_START, FRAME_END + 1):
        # 1. X-Axis Traverse on the Overhead Saddle (`saddle_obj` moves -55 mm -> +55 mm across Frames 68..72)
        if f <= FRAME_FIRE_START:
            x_shuttle = -half_stroke
        elif f >= FRAME_FIRE_END:
            x_shuttle = +half_stroke
        else:
            u_move = (f - FRAME_FIRE_START) / float(FRAME_FIRE_END - FRAME_FIRE_START)
            x_shuttle = -half_stroke + SLOT_LEN_M * u_move

        # 2. Z-Axis Descent on the Optical Laser Head (`shuttle_obj` lowers +62 mm -> 0 mm across Frames 18..46):
        # - Frames 1..18: Poised high at +62 mm (`HEAD_Z_LIFT_M`)
        # - Frames 18..46 (1.17s): Smooth S-curve servo descent down to `0.000 m` cutting standoff
        # - Frames 47..160: Locked at `0.000 m` cutting standoff
        if f <= FRAME_DESCEND_START:
            z_shuttle = HEAD_Z_LIFT_M
        elif f >= FRAME_DESCEND_END:
            z_shuttle = 0.0
        else:
            u_desc = smoothstep(float(FRAME_DESCEND_START), float(FRAME_DESCEND_END), float(f))
            z_shuttle = HEAD_Z_LIFT_M * (1.0 - u_desc)

        if saddle_obj is not None:
            saddle_obj.location = Vector((x_shuttle, 0.0, 0.0))
            saddle_obj.keyframe_insert(data_path="location", frame=f)
            shuttle_obj.location = Vector((0.0, 0.0, z_shuttle))
            shuttle_obj.keyframe_insert(data_path="location", frame=f)
        else:
            shuttle_obj.location = Vector((x_shuttle, 0.0, z_shuttle))
            shuttle_obj.keyframe_insert(data_path="location", frame=f)

        # Permanently hide under_exit_glow so the bottom of the pipe is 100% untouched
        under_exit_glow.hide_render = True
        under_exit_glow.keyframe_insert(data_path="hide_render", frame=f)

        if f < FRAME_PRE_PULSE:
            # Beat 1a (Frames 1..18): High poise (+62 mm)
            # Beat 1b (Frames 19..46): Z-axis lowering movement (+62 mm -> 0 mm)
            # Beat 1c (Frames 47..64): Suspenseful pause at cutting standoff before the blue laser fires
            beam_em = 0.0
            sheath_em = 0.0
            plasma_em = 0.0
            molten_em = 0.0
            ember_halo_em = 0.0
            atmo_em = 0.0
            under_halo_em = 0.0
            slot_em = 0.0
            spark_em = 0.0
            flash_w = 0.0
            bounce_w = 0.0
            gantry_w = 0.0
            ember_w = 0.0
            under_w = 0.0
            slot_scale_x = 0.001
            hide_pre = True
            hide_strike = True
            hide_afterglow = True
        elif FRAME_PRE_PULSE <= f < FRAME_FIRE_START:
            # Beat 1d (Frames 65..67, 0.12s): Pre-strike blue optical lock-on & subtle machine silhouette pre-glow
            u_pre = (f - FRAME_PRE_PULSE + 1) / float(FRAME_FIRE_START - FRAME_PRE_PULSE)
            beam_em = 0.0
            sheath_em = 0.0
            plasma_em = 24.0 * u_pre
            molten_em = 0.0
            ember_halo_em = 0.0
            atmo_em = 1.6 * u_pre
            under_halo_em = 0.0
            slot_em = 0.0
            spark_em = 0.0
            flash_w = 0.0
            bounce_w = 18.0 * u_pre
            gantry_w = 6.5 * u_pre
            ember_w = 0.0
            under_w = 0.0
            slot_scale_x = 0.001
            hide_pre = False
            hide_strike = True
            hide_afterglow = True
        elif FRAME_FIRE_START <= f <= FRAME_FIRE_END:
            # Beat 2 (Frames 68..72, 0.17s / 4 frames): Ultra-fast 110 mm Electric-Blue Laser Strike
            # + Brief Atmospheric Blue Glow illuminating the Overhead Machine Silhouette!
            u = (f - FRAME_FIRE_START) / float(FRAME_FIRE_END - FRAME_FIRE_START)
            pulse = 1.0 + 0.12 * math.sin(u * math.pi * 2.0)
            beam_em = 2600.0 * pulse
            sheath_em = 75.0 * pulse
            plasma_em = 110.0 * pulse
            molten_em = 42.0 * pulse
            ember_halo_em = 10.0 * pulse
            atmo_em = 5.2 * pulse
            under_halo_em = 0.0
            slot_em = 28.0 * pulse
            spark_em = 280.0 * pulse
            flash_w = 0.0
            bounce_w = 95.0 * pulse
            gantry_w = 38.0 * pulse
            ember_w = 0.0
            under_w = 0.0
            slot_scale_x = max(0.05, u)
            hide_pre = False
            hide_strike = False
            hide_afterglow = False
        else:
            # Beat 3 (Frames 73..160): Instant beam shutoff + brief (~0.35s) decay of the blue machine-silhouette
            # glow, leaving the cold silver-blue machined kerf hairline along the 110 mm top spine!
            dt_frames = float(f - FRAME_FIRE_END)
            if dt_frames >= 24.0:
                gas_decay = 0.0
            else:
                gas_decay = math.exp(-dt_frames / 8.0) * (1.0 - dt_frames / 24.0)
            if dt_frames >= 10.0:
                glow_decay = 0.0
            else:
                glow_decay = math.exp(-dt_frames / 2.8) * (1.0 - dt_frames / 10.0)

            beam_em = 0.0
            sheath_em = 0.0
            plasma_em = 14.0 * glow_decay
            molten_em = 0.0
            ember_halo_em = 1.6 + 4.5 * gas_decay
            atmo_em = 1.8 * glow_decay
            under_halo_em = 0.0
            slot_em = 6.5 + 8.0 * gas_decay
            spark_em = 0.0
            flash_w = 0.0
            bounce_w = 28.0 * glow_decay
            gantry_w = 12.0 * glow_decay
            ember_w = 0.0
            under_w = 0.0
            slot_scale_x = 1.0
            hide_pre = glow_decay <= 0.001
            hide_strike = True
            hide_afterglow = False

        bsdf_beam.inputs["Emission Strength"].default_value = beam_em
        bsdf_beam.inputs["Emission Strength"].keyframe_insert(data_path="default_value", frame=f)

        emit_sheath.inputs["Strength"].default_value = sheath_em
        emit_sheath.inputs["Strength"].keyframe_insert(data_path="default_value", frame=f)

        emit_plasma.inputs["Strength"].default_value = plasma_em
        emit_plasma.inputs["Strength"].keyframe_insert(data_path="default_value", frame=f)

        emit_molten.inputs["Strength"].default_value = molten_em
        emit_molten.inputs["Strength"].keyframe_insert(data_path="default_value", frame=f)

        emit_ember.inputs["Strength"].default_value = ember_halo_em
        emit_ember.inputs["Strength"].keyframe_insert(data_path="default_value", frame=f)

        emit_atmo.inputs["Strength"].default_value = atmo_em
        emit_atmo.inputs["Strength"].keyframe_insert(data_path="default_value", frame=f)

        emit_under.inputs["Strength"].default_value = under_halo_em
        emit_under.inputs["Strength"].keyframe_insert(data_path="default_value", frame=f)

        bsdf_slot.inputs["Emission Strength"].default_value = slot_em
        bsdf_slot.inputs["Emission Strength"].keyframe_insert(data_path="default_value", frame=f)

        bsdf_spark.inputs["Emission Strength"].default_value = spark_em
        bsdf_spark.inputs["Emission Strength"].keyframe_insert(data_path="default_value", frame=f)

        flash_light.energy = flash_w
        flash_light.keyframe_insert(data_path="energy", frame=f)

        bounce_light.energy = bounce_w
        bounce_light.keyframe_insert(data_path="energy", frame=f)

        gantry_reveal_light.energy = gantry_w
        gantry_reveal_light.keyframe_insert(data_path="energy", frame=f)

        ember_light.energy = ember_w
        ember_light.keyframe_insert(data_path="energy", frame=f)

        under_light.energy = under_w
        under_light.keyframe_insert(data_path="energy", frame=f)

        slot_obj.scale = Vector((slot_scale_x, 1.0, 1.0))
        slot_obj.keyframe_insert(data_path="scale", frame=f)

        for o in pre_and_strike_objs:
            o.hide_render = hide_pre
            o.keyframe_insert(data_path="hide_render", frame=f)

        for o in strike_only_objs:
            o.hide_render = hide_strike
            o.keyframe_insert(data_path="hide_render", frame=f)

        ember_shimmer.hide_render = hide_afterglow
        ember_shimmer.keyframe_insert(data_path="hide_render", frame=f)


# ==============================================================================
# RENDER ENGINE & SELF-CRITIQUE GATES
# ==============================================================================
def configure_cycles_optix(scene: bpy.types.Scene, width: int = 1920, height: int = 1080, samples: int = 96) -> str:
    scene.render.engine = "CYCLES"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100

    cp = bpy.context.preferences.addons["cycles"].preferences
    cp.compute_device_type = "OPTIX"
    cp.refresh_devices()
    optix_devices = [d for d in cp.devices if d.type == "OPTIX"]
    if not optix_devices:
        raise RuntimeError("No OPTIX GPU device found — refusing silent CPU fallback!")
    for d in cp.devices:
        d.use = d.type == "OPTIX"

    scene.cycles.device = "GPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.transparent_max_bounces = 16

    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "High Contrast"
    scene.view_settings.exposure = 0.0

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    return ", ".join(f"{d.name} ({d.type})" for d in optix_devices if d.use)


def audit_scene_geometry(
    scene: bpy.types.Scene,
    cam: bpy.types.Object,
    pipe_objs: dict[str, bpy.types.Object],
    head_objs: dict[str, bpy.types.Object],
) -> dict:
    """Gate 0 & Gate 2: Verify true metric dimensions and horizontal camera projection of all key subjects."""
    bpy.context.view_layer.update()

    pipe = pipe_objs["pipe"]
    coup = pipe_objs["coupling"]
    prot = pipe_objs["protector"]
    shroud = head_objs["head_shroud"]
    shuttle = head_objs["nozzle"]

    assert abs(pipe.dimensions.x - PIPE_LEN_M) < 0.005, f"Pipe length mismatch: {pipe.dimensions.x}"
    assert abs(pipe.dimensions.z - PIPE_OD_M) < 0.002, f"Pipe OD mismatch: {pipe.dimensions.z}"
    assert abs(coup.dimensions.z - COUPLING_OD_M) < 0.002, f"Coupling OD mismatch: {coup.dimensions.z}"
    assert abs(prot.dimensions.z - PROTECTOR_OD_M) < 0.005, f"Protector OD mismatch: {prot.dimensions.z}"

    key_points = {
        "left_red_coupling": Vector((PIPE_X_START - 0.02, 0.0, 0.0)),
        "center_top_spine": Vector((0.0, 0.0, PIPE_OD_M / 2.0)),
        "right_red_protector": Vector((PIPE_X_END + 0.02, 0.0, 0.0)),
        "stealth_laser_shuttle": Vector((0.0, 0.0, 0.210)),
        "sleek_linear_stage_bar": Vector((0.0, 0.0, 0.380)),
    }
    projections = {}
    for label, pt in key_points.items():
        ndc = world_to_camera_view(scene, cam, pt)
        in_frame = (0.02 <= ndc.x <= 0.98) and (0.05 <= ndc.y <= 0.95) and (ndc.z > 0.0)
        assert in_frame, f"Gate 2 FAILED: {label} projected out of frame at NDC=({ndc.x:.3f}, {ndc.y:.3f}, {ndc.z:.3f})"
        projections[label] = {"ndc_x": round(ndc.x, 4), "ndc_y": round(ndc.y, 4), "depth_m": round(ndc.z, 3)}

    span_ndc_x = projections["right_red_protector"]["ndc_x"] - projections["left_red_coupling"]["ndc_x"]
    assert 0.76 <= span_ndc_x <= 0.95, f"Pipe horizontal span {span_ndc_x:.3f} outside target [0.76, 0.95]"

    return {
        "pipe_dimensions_m": [round(v, 4) for v in pipe.dimensions],
        "coupling_dimensions_m": [round(v, 4) for v in coup.dimensions],
        "protector_dimensions_m": [round(v, 4) for v in prot.dimensions],
        "sleek_stage_dimensions_m": [round(v, 4) for v in shroud.dimensions],
        "stealth_shuttle_dimensions_m": [round(v, 4) for v in shuttle.dimensions],
        "horizontal_pipe_span_fraction": round(span_ndc_x, 4),
        "projections": projections,
    }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    out_dir = Path(r"c:\Users\kyle\MPS\slotted-liner\marketing\blender\renders\v10_lookdev")
    scene_dir = Path(r"c:\Users\kyle\MPS\slotted-liner\marketing\blender\scenes")
    out_dir.mkdir(parents=True, exist_ok=True)
    scene_dir.mkdir(parents=True, exist_ok=True)

    scene = clear_and_init_scene()
    mats = build_materials()
    pipe_objs = build_pipe_and_red_ends(mats)
    head_objs = build_mysterious_laser_head(mats)
    fx_objs = build_center_slot_and_laser_fx(mats, head_objs["nozzle"])
    lights = setup_world_and_lights(scene, pipe_objs, head_objs)
    cam = setup_camera(scene)

    animate_laser_sequence(head_objs["nozzle"], fx_objs, lights, mats)
    device_str = configure_cycles_optix(scene, width=1920, height=1080, samples=96)
    scene.render.use_persistent_data = True

    scene.frame_set(CHECK_FRAMES["beat1c_lowered_pause"])
    audit = audit_scene_geometry(scene, cam, pipe_objs, head_objs)

    blend_path = scene_dir / "laser_slotted_liner_teaser_v10.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    rendered_files: dict[str, dict] = {}
    seen_hashes: set[str] = set()
    ffmpeg_bin = r"C:\Users\kyle\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"

    for beat_name, frame_num in CHECK_FRAMES.items():
        scene.frame_set(frame_num)
        bpy.context.view_layer.update()
        img_path = out_dir / f"{beat_name}_f{frame_num:03d}.png"
        scene.render.filepath = str(img_path)
        bpy.ops.render.render(write_still=True)

        assert img_path.exists() and img_path.stat().st_size > 10000, f"Render failed or empty: {img_path}"
        digest = sha256_file(img_path)
        assert digest not in seen_hashes, f"Gate 1b FAILED: duplicate frame hash for {beat_name}"
        seen_hashes.add(digest)
        rendered_files[beat_name] = {
            "frame": frame_num,
            "path": str(img_path),
            "bytes": img_path.stat().st_size,
            "sha256": digest,
        }
        print(f"RENDERED {beat_name} (frame {frame_num}) -> {img_path} [{digest[:12]}]")

        # Also generate 2.5x center-zoom inspection crop
        zoom_path = out_dir / f"{beat_name}_center_zoom_f{frame_num:03d}.png"
        subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-i",
                str(img_path),
                "-vf",
                "crop=768:432:576:220,scale=1920:1080:flags=lanczos",
                "-frames:v",
                "1",
                "-update",
                "1",
                str(zoom_path),
            ],
            check=True,
        )

    receipt = {
        "blender_version": bpy.app.version_string,
        "device": device_str,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "samples": scene.cycles.samples,
        "blend_file": str(blend_path),
        "blend_sha256": sha256_file(blend_path),
        "audit": audit,
        "renders": rendered_files,
    }
    receipt_path = out_dir / "v10_lookdev_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("LOOKDEV_V10_DONE", json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
