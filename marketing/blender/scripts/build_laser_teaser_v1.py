#!/usr/bin/env python3
"""Build and render Look-Dev v2 for the Laser Slotted Liner Teaser Campaign.

Scene Specification (Kyle's brief, 2026-10-16):
- Pipe: API 5CT 7" OD (0.1778 m OD, 0.1571 m ID), 9.0 m length (Range 2 joint), along X axis.
- Pipe Finish: Deep black-oxide / dark gunmetal steel (not silver-grey, not pitch-flat black)
  with a sleek longitudinal metallic sheen contrasting against the pure black background.
- Left End (-X): Red API 7" Box Coupling (0.1945 m OD, 0.270 m length, beveled shoulders, center recess).
- Right End (+X): Matching Red Pin Thread Protector (0.1915 m OD, 0.210 m length, ribbed cap).
- Above Center (x = 0): Mysterious high-tech equipment hovering in low-key silhouette just above
  the pipe spine — shrouded in darkness during Beat 1 so the viewer can tell *something* is poised
  above the pipe without knowing what it is.
- Action at Center (x = 0): One single surgical pass along the 12 o'clock top spine.
  - The viewer NEVER sees the slot face directly (camera is dead-level side profile; cut is at 12 o'clock).
  - Beat 1 (Frame 45): Pre-fire stillness — dark black pipe with sleek sheen, red coupling & protector,
    and the mysterious silhouetted apparatus barely visible above the center.
  - Beat 2 (Frame 76): Surgical 12 kW laser strike — intense pinpoint plasma & coaxial beam ignites
    in the millimeter gap between nozzle and top pipe spine, casting dramatic upward light onto the
    underside of the mysterious head and a horizontal anamorphic glint across the pipe spine.
  - Beat 3 (Frame 105): Instant cutoff & inference — the laser snaps off dead; the head has translated
    60 mm along the top spine, leaving only a razor-thin residual thermal shimmer along the 12 o'clock
    top edge so the viewer infers a precision cut just happened.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector


# ==============================================================================
# ENGINEERING & SCENE PARAMETERS (METRES)
# ==============================================================================
PIPE_OD_M = 0.1778          # 7.000 in API 5CT casing/liner OD
PIPE_ID_M = 0.1571          # 6.184 in ID (29 lb/ft wall = 10.36 mm)
PIPE_LEN_M = 9.000          # 9.0 m Range 2 joint (-4.5 m to +4.5 m)

COUPLING_OD_M = 0.1945      # 7.656 in API 7" coupling OD
COUPLING_LEN_M = 0.270      # Box coupling length on left (-X) end

PROTECTOR_OD_M = 0.1915     # 7.54 in closed-end pin thread protector OD
PROTECTOR_LEN_M = 0.210     # Pin protector length on right (+X) end

SLOT_LEN_M = 0.060          # 60 mm single center pass along top spine

# Keyframes for the 3-beat teaser (24 fps, 160 frames = 6.67 s)
FRAME_START = 1
FRAME_FIRE_START = 68       # 2.83 s: after viewer registers the pipe & mystery head
FRAME_FIRE_END = 84         # 3.50 s: fast, surgical 0.67 s cut!
FRAME_END = 160             # 6.67 s: lingering afterglow on the top-edge horizon

CHECK_FRAMES = {
    "beat1_stillness": 45,
    "beat2_laser_strike": 76,
    "beat3_afterglow": 105,
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
    # Stretch micro-striations longitudinally along X so 4x zoom is silky rolled steel without mottled grain
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

    # 2. Machined Thread Standoff Ring (subtle dark steel shoulder next to red coupling)
    mat_machined = bpy.data.materials.new("Machined_Steel_Accent")
    bsdf_m = get_node_by_type(mat_machined.node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_m.inputs["Base Color"].default_value = (0.18, 0.20, 0.23, 1.0)
    bsdf_m.inputs["Metallic"].default_value = 0.92
    bsdf_m.inputs["Roughness"].default_value = 0.26
    mats["machined"] = mat_machined

    # 3. Red Coupling & Thread Protector (Rich Oilfield Crimson Satin — deep & saturated, not pink)
    mat_red = bpy.data.materials.new("Red_Coupling_Protector")
    nt_r = mat_red.node_tree
    bsdf_r = get_node_by_type(nt_r, "ShaderNodeBsdfPrincipled")
    bsdf_r.inputs["Base Color"].default_value = (0.46, 0.014, 0.014, 1.0)
    bsdf_r.inputs["Metallic"].default_value = 0.25
    bsdf_r.inputs["Roughness"].default_value = 0.28
    bsdf_r.inputs["Coat Weight"].default_value = 0.40
    bsdf_r.inputs["Coat Roughness"].default_value = 0.12
    bevel_r = nt_r.nodes.new("ShaderNodeBevel")
    bevel_r.inputs["Radius"].default_value = 0.0008
    bevel_r.samples = 4
    nt_r.links.new(bevel_r.outputs["Normal"], bsdf_r.inputs["Normal"])
    mats["red"] = mat_red

    # 4. Look-Dev v6 Precision Linear Guide Rail (Hardened ground tool steel with longitudinal anisotropic sheen)
    mat_rail = bpy.data.materials.new("Linear_Rail_Steel")
    nt_rl = mat_rail.node_tree
    bsdf_rl = get_node_by_type(nt_rl, "ShaderNodeBsdfPrincipled")
    bsdf_rl.inputs["Base Color"].default_value = (0.016, 0.018, 0.022, 1.0)
    bsdf_rl.inputs["Metallic"].default_value = 0.85
    bsdf_rl.inputs["Roughness"].default_value = 0.40
    bsdf_rl.inputs["Anisotropic"].default_value = 0.80
    bsdf_rl.inputs["Anisotropic Rotation"].default_value = 0.0
    bevel_rl = nt_rl.nodes.new("ShaderNodeBevel")
    bevel_rl.inputs["Radius"].default_value = 0.0006
    bevel_rl.samples = 4
    nt_rl.links.new(bevel_rl.outputs["Normal"], bsdf_rl.inputs["Normal"])
    mats["rail"] = mat_rail

    # 4b. Look-Dev v6 Aerospace CNC Machined Billet Carriage Plate (Deep hard-anodized dark graphite aluminum)
    mat_carriage = bpy.data.materials.new("Laser_Carriage_Billet")
    nt_c = mat_carriage.node_tree
    bsdf_c = get_node_by_type(nt_c, "ShaderNodeBsdfPrincipled")
    bsdf_c.inputs["Base Color"].default_value = (0.010, 0.011, 0.014, 1.0)
    bsdf_c.inputs["Metallic"].default_value = 0.82
    bsdf_c.inputs["Roughness"].default_value = 0.48
    bevel_c = nt_c.nodes.new("ShaderNodeBevel")
    bevel_c.inputs["Radius"].default_value = 0.0008
    bevel_c.samples = 4
    nt_c.links.new(bevel_c.outputs["Normal"], bsdf_c.inputs["Normal"])
    mats["carriage"] = mat_carriage
    mats["shroud"] = mat_carriage  # Backward-compatible alias

    # 4c. Look-Dev v6 Linear Runner Blocks (Ground bearing steel body - dark oxide)
    mat_steel = bpy.data.materials.new("Linear_Runner_Steel")
    nt_st = mat_steel.node_tree
    bsdf_st = get_node_by_type(nt_st, "ShaderNodeBsdfPrincipled")
    bsdf_st.inputs["Base Color"].default_value = (0.014, 0.015, 0.018, 1.0)
    bsdf_st.inputs["Metallic"].default_value = 0.85
    bsdf_st.inputs["Roughness"].default_value = 0.42
    bevel_st = nt_st.nodes.new("ShaderNodeBevel")
    bevel_st.inputs["Radius"].default_value = 0.0005
    bevel_st.samples = 4
    nt_st.links.new(bevel_st.outputs["Normal"], bsdf_st.inputs["Normal"])
    mats["steel"] = mat_steel

    # 4d. Look-Dev v6 Stainless Hardware, QBH Receptacle, Cooling Fin Rims & Gas Fittings
    mat_stainless = bpy.data.materials.new("Stainless_Hardware_Fittings")
    nt_ss = mat_stainless.node_tree
    bsdf_ss = get_node_by_type(nt_ss, "ShaderNodeBsdfPrincipled")
    bsdf_ss.inputs["Base Color"].default_value = (0.055, 0.058, 0.065, 1.0)
    bsdf_ss.inputs["Metallic"].default_value = 0.92
    bsdf_ss.inputs["Roughness"].default_value = 0.24
    bevel_ss = nt_ss.nodes.new("ShaderNodeBevel")
    bevel_ss.inputs["Radius"].default_value = 0.0004
    bevel_ss.samples = 4
    nt_ss.links.new(bevel_ss.outputs["Normal"], bsdf_ss.inputs["Normal"])
    mats["stainless"] = mat_stainless

    # 4e. Look-Dev v6 Runner Wiper Seals (Dark synthetic elastomer end-seals)
    mat_wiper = bpy.data.materials.new("Runner_Wiper_Seal")
    bsdf_wp = get_node_by_type(mat_wiper.node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_wp.inputs["Base Color"].default_value = (0.006, 0.006, 0.008, 1.0)
    bsdf_wp.inputs["Metallic"].default_value = 0.08
    bsdf_wp.inputs["Roughness"].default_value = 0.65
    mats["wiper"] = mat_wiper

    # 4f. Look-Dev v6 Technical Stealth Ceramic Isolator Ring (Capacitive height sensor ring - dark matte)
    mat_ceramic = bpy.data.materials.new("Sensor_Ceramic_Isolator")
    bsdf_cer = get_node_by_type(mat_ceramic.node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_cer.inputs["Base Color"].default_value = (0.015, 0.015, 0.016, 1.0)
    bsdf_cer.inputs["Metallic"].default_value = 0.05
    bsdf_cer.inputs["Roughness"].default_value = 0.70
    mats["ceramic"] = mat_ceramic

    # 4g. Look-Dev v6 Knurled Dark Bronze/Graphite Sensor Retention Collar (stealth low-specular)
    mat_brass = bpy.data.materials.new("Knurled_Brass_Collar")
    bsdf_br = get_node_by_type(mat_brass.node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_br.inputs["Base Color"].default_value = (0.010, 0.010, 0.011, 1.0)
    bsdf_br.inputs["Metallic"].default_value = 0.40
    bsdf_br.inputs["Roughness"].default_value = 0.60
    mats["brass"] = mat_brass

    # 5. Indistinguishable Tiny Laser Emitter Tip (Stealth matte dark carbon cone — zero specular streak)
    mat_nozzle = bpy.data.materials.new("Laser_Stealth_Aperture")
    nt_n = mat_nozzle.node_tree
    bsdf_n = get_node_by_type(nt_n, "ShaderNodeBsdfPrincipled")
    bsdf_n.inputs["Base Color"].default_value = (0.003, 0.003, 0.004, 1.0)
    bsdf_n.inputs["Metallic"].default_value = 0.10
    bsdf_n.inputs["Roughness"].default_value = 0.72
    bevel_n = nt_n.nodes.new("ShaderNodeBevel")
    bevel_n.inputs["Radius"].default_value = 0.0006
    bevel_n.samples = 4
    nt_n.links.new(bevel_n.outputs["Normal"], bsdf_n.inputs["Normal"])
    mats["nozzle"] = mat_nozzle

    # 6. Laser Beam Core (Brilliant Cyan-White 12 kW Fiber Laser Jet)
    mat_beam = bpy.data.materials.new("Laser_Beam_Core")
    bsdf_b = get_node_by_type(mat_beam.node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_b.inputs["Base Color"].default_value = (0.90, 0.98, 1.0, 1.0)
    bsdf_b.inputs["Emission Color"].default_value = (0.78, 0.95, 1.0, 1.0)
    bsdf_b.inputs["Emission Strength"].default_value = 0.0
    mats["beam"] = mat_beam

    # 7. Procedural Optical Plasma Halo & Anamorphic Glint Shader
    # Uses Transparent BSDF + Emission MixShader driven by radial distance from quad center
    # (in bmesh.create_grid(size=1.0), Object coords span [-0.5, +0.5], so radius = 0.5 is the quad edge!)
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
        emit_g.inputs["Strength"].default_value = 0.0  # Keyframed during animation

        # Object coordinates on a size=1.0 grid in X-Z plane span [-0.5, +0.5] -> radius 0.0..0.5
        tc = n_g.new("ShaderNodeTexCoord")
        vec_len = n_g.new("ShaderNodeVectorMath")
        vec_len.operation = "LENGTH"
        l_g.new(tc.outputs["Object"], vec_len.inputs[0])

        map_r = n_g.new("ShaderNodeMapRange")
        map_r.inputs["From Min"].default_value = 0.0
        map_r.inputs["From Max"].default_value = 0.48  # Reaches 0.0 slightly before the 0.50 quad boundary!
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

    mats["plasma_halo"] = make_radial_glow_mat("Laser_Plasma_Halo", (0.48, 0.84, 1.0), exponent=4.0)
    mats["ember_halo"] = make_radial_glow_mat("Laser_Ember_Halo", (1.0, 0.42, 0.08), exponent=3.4)

    # 8. Top-Spine Hairline Thermal Horizon Edge (strictly at 12 o'clock top dead center)
    mat_slot = bpy.data.materials.new("Top_Spine_Thermal_Horizon")
    bsdf_sl = get_node_by_type(mat_slot.node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_sl.inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1.0)
    bsdf_sl.inputs["Emission Color"].default_value = (1.0, 0.42, 0.08, 1.0)
    bsdf_sl.inputs["Emission Strength"].default_value = 0.0
    mats["slot"] = mat_slot

    # 9. Molten Micro-Spark / Plasma Plume Material
    mat_spark = bpy.data.materials.new("Laser_Plasma_Sparks")
    bsdf_sp = get_node_by_type(mat_spark.node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_sp.inputs["Base Color"].default_value = (1.0, 0.78, 0.38, 1.0)
    bsdf_sp.inputs["Emission Color"].default_value = (0.75, 0.92, 1.0, 1.0)
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
    r_out = PIPE_OD_M / 2.0
    r_in = PIPE_ID_M / 2.0
    half_len = PIPE_LEN_M / 2.0
    chamfer = 0.003

    # 1. 9.0 m 7" OD Hollow Liner Pipe (-4.50 m to +4.50 m)
    pipe_profile = [
        (-half_len, r_in),
        (-half_len, r_out - chamfer),
        (-half_len + chamfer, r_out),
        (0.0, r_out),
        (half_len - chamfer, r_out),
        (half_len, r_out - chamfer),
        (half_len, r_in),
        (-half_len, r_in),
    ]
    objs["pipe"] = create_lathed_profile("Liner_Pipe_7in_9m", pipe_profile, segments=128, material=mats["pipe"])

    # 2. Machined thread-standoff bands just inside the coupling & protector shoulders
    x_left_shoulder = -half_len + 0.190
    standoff_left = [
        (x_left_shoulder - 0.002, r_out + 0.0002),
        (x_left_shoulder + 0.008, r_out + 0.0002),
        (x_left_shoulder + 0.008, r_out - 0.001),
    ]
    objs["standoff_left"] = create_lathed_profile("Thread_Standoff_Left", standoff_left, segments=96, material=mats["machined"])

    x_right_shoulder = half_len - 0.165
    standoff_right = [
        (x_right_shoulder - 0.008, r_out - 0.001),
        (x_right_shoulder - 0.008, r_out + 0.0002),
        (x_right_shoulder + 0.002, r_out + 0.0002),
    ]
    objs["standoff_right"] = create_lathed_profile("Thread_Standoff_Right", standoff_right, segments=96, material=mats["machined"])

    # 3. Red API 7" Box Coupling on Left End (-X: -4.58 m to -4.31 m)
    r_coup = COUPLING_OD_M / 2.0
    x_c0 = -half_len - 0.080
    x_c1 = x_c0 + COUPLING_LEN_M
    x_cmid = 0.5 * (x_c0 + x_c1)
    bev = 0.006
    coupling_profile = [
        (x_c0, r_in + 0.004),
        (x_c0, r_coup - bev),
        (x_c0 + bev, r_coup),
        (x_cmid - 0.006, r_coup),
        (x_cmid - 0.004, r_coup - 0.0018),
        (x_cmid + 0.004, r_coup - 0.0018),
        (x_cmid + 0.006, r_coup),
        (x_c1 - bev, r_coup),
        (x_c1, r_coup - bev),
        (x_c1, r_out + 0.0001),
        (x_c0, r_in + 0.004),
    ]
    objs["coupling"] = create_lathed_profile("Red_Coupling_Box_Left", coupling_profile, segments=96, material=mats["red"])

    # 4. Red Pin-End Thread Protector on Right End (+X: +4.335 m to +4.545 m)
    r_prot = PROTECTOR_OD_M / 2.0
    x_p0 = half_len - 0.165
    x_p1 = x_p0 + PROTECTOR_LEN_M
    p_bev = 0.005
    protector_profile = [
        (x_p0, r_out + 0.0001),
        (x_p0, r_prot - p_bev),
        (x_p0 + p_bev, r_prot),
        (x_p0 + 0.045, r_prot),
        (x_p0 + 0.050, r_prot - 0.003),
        (x_p0 + 0.075, r_prot - 0.003),
        (x_p0 + 0.080, r_prot + 0.002),
        (x_p1 - 0.025, r_prot + 0.002),
        (x_p1 - p_bev, r_prot),
        (x_p1, r_prot - p_bev),
        (x_p1, r_in * 0.65),
        (x_p1 - 0.018, r_in * 0.65),
        (x_p1 - 0.018, 0.0),
    ]
    objs["protector"] = create_lathed_profile("Red_Thread_Protector_Right", protector_profile, segments=96, material=mats["red"])

    return objs


# ------------------------------------------------------------------------------
# Look-Dev v6 Geometry Construction Helpers
# ------------------------------------------------------------------------------
def create_cylinder_bmesh(
    bm: bmesh.types.BMesh,
    radius: float,
    z_min: float,
    z_max: float,
    center_xy: tuple[float, float] = (0.0, 0.0),
    segments: int = 32,
    mat_idx: int = 0,
    cap_top: bool = True,
    cap_bottom: bool = True,
) -> None:
    cx, cy = center_xy
    top_ring = []
    bot_ring = []
    for i in range(segments):
        a = (2.0 * math.pi * i) / segments
        x = cx + radius * math.cos(a)
        y = cy + radius * math.sin(a)
        top_ring.append(bm.verts.new((x, y, z_max)))
        bot_ring.append(bm.verts.new((x, y, z_min)))
    for i in range(segments):
        inext = (i + 1) % segments
        f = bm.faces.new((bot_ring[i], bot_ring[inext], top_ring[inext], top_ring[i]))
        f.smooth = True
        f.material_index = mat_idx
    if cap_bottom:
        f = bm.faces.new(bot_ring)
        f.smooth = False
        f.material_index = mat_idx
    if cap_top:
        f = bm.faces.new(reversed(top_ring))
        f.smooth = False
        f.material_index = mat_idx


def create_box_bmesh(
    bm: bmesh.types.BMesh,
    min_pt: tuple[float, float, float],
    max_pt: tuple[float, float, float],
    mat_idx: int = 0,
) -> None:
    x0, y0, z0 = min_pt
    x1, y1, z1 = max_pt
    verts = [
        bm.verts.new((x0, y0, z0)),
        bm.verts.new((x1, y0, z0)),
        bm.verts.new((x1, y1, z0)),
        bm.verts.new((x0, y1, z0)),
        bm.verts.new((x0, y0, z1)),
        bm.verts.new((x1, y0, z1)),
        bm.verts.new((x1, y1, z1)),
        bm.verts.new((x0, y1, z1)),
    ]
    faces = [
        bm.faces.new((verts[0], verts[3], verts[2], verts[1])),  # Bottom (-Z)
        bm.faces.new((verts[4], verts[5], verts[6], verts[7])),  # Top (+Z)
        bm.faces.new((verts[0], verts[1], verts[5], verts[4])),  # Front (-Y)
        bm.faces.new((verts[2], verts[3], verts[7], verts[6])),  # Back (+Y)
        bm.faces.new((verts[0], verts[4], verts[7], verts[3])),  # Left (-X)
        bm.faces.new((verts[1], verts[2], verts[6], verts[5])),  # Right (+X)
    ]
    for f in faces:
        f.smooth = False
        f.material_index = mat_idx


def create_shcs_bolt(
    bm: bmesh.types.BMesh,
    pos: tuple[float, float, float],
    dir_axis: str = "Z",
    head_rad: float = 0.0030,
    head_len: float = 0.0026,
    socket_rad: float = 0.0015,
    socket_depth: float = 0.0016,
    mat_idx: int = 2,
) -> None:
    px, py, pz = pos
    if dir_axis == "Z":
        create_cylinder_bmesh(bm, head_rad, pz, pz + head_len, (px, py), segments=16, mat_idx=mat_idx, cap_top=True, cap_bottom=False)
        hex_ring = []
        for i in range(6):
            a = (2.0 * math.pi * i) / 6.0
            x = px + socket_rad * math.cos(a)
            y = py + socket_rad * math.sin(a)
            hex_ring.append(bm.verts.new((x, y, pz + head_len - socket_depth)))
        f = bm.faces.new(hex_ring)
        f.smooth = False
        f.material_index = mat_idx
    elif dir_axis == "-Y":
        ring_back = []
        ring_front = []
        for i in range(16):
            a = (2.0 * math.pi * i) / 16.0
            x = px + head_rad * math.cos(a)
            z = pz + head_rad * math.sin(a)
            ring_back.append(bm.verts.new((x, py, z)))
            ring_front.append(bm.verts.new((x, py - head_len, z)))
        for i in range(16):
            inext = (i + 1) % 16
            f = bm.faces.new((ring_back[i], ring_back[inext], ring_front[inext], ring_front[i]))
            f.smooth = True
            f.material_index = mat_idx
        f = bm.faces.new(ring_front)
        f.smooth = False
        f.material_index = mat_idx


def create_elbow_fitting(
    bm: bmesh.types.BMesh,
    pos: tuple[float, float, float],
    dir_x: float = 1.0,
    mat_idx: int = 2,
) -> None:
    px, py, pz = pos
    # Hex collar
    create_cylinder_bmesh(bm, 0.0055, pz - 0.003, pz + 0.003, (px, py), segments=6, mat_idx=mat_idx)
    # Vertical fitting stem
    create_cylinder_bmesh(bm, 0.0040, pz + 0.003, pz + 0.010, (px, py), segments=16, mat_idx=mat_idx)
    # Corner junction cube
    create_box_bmesh(bm, (px - 0.004, py - 0.004, pz + 0.008), (px + 0.004, py + 0.004, pz + 0.016), mat_idx=mat_idx)
    # Horizontal elbow tube running rearward (+Y)
    y_start = py + 0.004
    y_end = py + 0.018
    r_tube = 0.0035
    ring1 = []
    ring2 = []
    for i in range(16):
        a = (2.0 * math.pi * i) / 16.0
        x = px + r_tube * math.cos(a)
        z = (pz + 0.012) + r_tube * math.sin(a)
        ring1.append(bm.verts.new((x, y_start, z)))
        ring2.append(bm.verts.new((x, y_end, z)))
    for i in range(16):
        inext = (i + 1) % 16
        f = bm.faces.new((ring1[i], ring1[inext], ring2[inext], ring2[i]))
        f.smooth = True
        f.material_index = mat_idx
    f_end = bm.faces.new(reversed(ring2))
    f_end.smooth = False
    f_end.material_index = mat_idx


def build_mysterious_laser_head(mats: dict[str, bpy.types.Material]) -> dict[str, bpy.types.Object]:
    """Look-Dev v6: Engineered High-Precision CNC Laser Cutting Head & Linear Stage Assembly:
    - Maintains the low-profile scale approved in v5 (height = 36 mm, only 20% of 177.8 mm pipe OD!).
    - Upgrades from a plain extruded rectangular bar into an authentic multi-component industrial laser assembly:
      1. Stationary Linear Guide Rail (`Linear_Rail_Track`):
         - 440 mm long precision ground tool steel rail (x = -0.220 m .. +0.220 m) with Gothic-arch ball raceways,
           7 counterbored SHCS bolts, and machined aluminum end-stop blocks with rubber bumpers.
      2. Moving Engineered Laser Head & Carriage Assembly (`Laser_Machined_Carriage`):
         - Dual linear runner blocks (THK/Rexroth recirculating ball carriages) with wiper end-seals, front grease nipples,
           and mounting bolts.
         - Aerospace pocketed billet aluminum CNC carriage plate (280 mm wide x 36 mm tall) with chamfered pocket rims,
           internal stiffening web trusses (ribs), and perimeter SHCS bolt heads.
         - Central vertical optical collimator barrel (co-axial at x = 0, y = 0) with 4 precision annular cooling fins /
           heat dissipation flutes that catch crisp, parallel specular highlights under rim lighting.
         - Upper QBH fiber optic cable receiver with stainless knurled locking collar and flexible armored conduit relief.
         - Dual assist gas manifold ports (stainless 90-deg elbow compression fittings).
         - Dynamic Z-axis capacitive sensor ring with knurled brass collar and white technical ceramic isolator ring.
         - Indistinguishable tiny stealth conical nozzle (9 mm standoff above pipe top spine).
    """
    objs: dict[str, bpy.types.Object] = {}
    r_pipe = PIPE_OD_M / 2.0  # 0.0889 m
    aperture_tip_z = r_pipe + 0.0090  # 0.0979 m (9.0 mm standoff gap above pipe top spine)

    # --------------------------------------------------------------------------
    # 1. Stationary Profiled Linear Guide Rail (`Linear_Rail_Track`)
    # --------------------------------------------------------------------------
    mesh_rail = bpy.data.meshes.new("Linear_Rail_Track")
    bm_r = bmesh.new()

    # Ground steel rail profile extruded along X (-0.220 m .. +0.220 m = 440 mm)
    # Y: +0.020 m .. +0.038 m (18 mm wide)
    # Z: +0.148 m .. +0.168 m (20 mm tall)
    # With Gothic-arch ball raceway grooves along both Y flanks at z = 0.155 .. 0.161 m
    rail_yz = [
        (0.0200, 0.1480),  # Bottom front
        (0.0380, 0.1480),  # Bottom back
        (0.0380, 0.1550),  # Back lower
        (0.0368, 0.1565),  # Back Gothic-arch raceway groove (recessed 1.2 mm)
        (0.0368, 0.1595),
        (0.0380, 0.1610),  # Back upper
        (0.0380, 0.1668),
        (0.0368, 0.1680),  # Top chamfer back
        (0.0212, 0.1680),  # Top face
        (0.0200, 0.1668),  # Top chamfer front
        (0.0200, 0.1610),  # Front upper
        (0.0212, 0.1595),  # Front Gothic-arch raceway groove (recessed 1.2 mm)
        (0.0212, 0.1565),
        (0.0200, 0.1550),  # Front lower
    ]

    x_left = -0.220
    x_right = +0.220
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

    # 7 Counterbored SHCS bolts along top face (z = 0.168 m) at regular 60 mm pitch
    bolt_x = [-0.180, -0.120, -0.060, 0.0, 0.060, 0.120, 0.180]
    for bx in bolt_x:
        create_shcs_bolt(bm_r, (bx, 0.029, 0.168), dir_axis="Z", head_rad=0.0030, head_len=0.0025, socket_rad=0.0015, socket_depth=0.0016, mat_idx=2)

    # Rail end-stop bumpers with cap screws at both ends
    for ex in [-0.222, +0.220]:
        create_box_bmesh(bm_r, (ex - 0.002, 0.019, 0.147), (ex + 0.002, 0.039, 0.169), mat_idx=2)
        create_shcs_bolt(bm_r, (ex, 0.029, 0.169), dir_axis="Z", head_rad=0.0025, head_len=0.0020, mat_idx=2)

    bmesh.ops.recalc_face_normals(bm_r, faces=bm_r.faces)
    bm_r.to_mesh(mesh_rail)
    bm_r.free()

    obj_rail = bpy.data.objects.new("Linear_Rail_Track", mesh_rail)
    bpy.context.scene.collection.objects.link(obj_rail)
    obj_rail.data.materials.append(mats["rail"])       # Slot 0: ground rail steel
    obj_rail.data.materials.append(mats["steel"])      # Slot 1: structural steel
    obj_rail.data.materials.append(mats["stainless"])  # Slot 2: stainless hardware
    objs["rail"] = obj_rail
    objs["head_shroud"] = obj_rail  # Stationary reference

    # --------------------------------------------------------------------------
    # 2. Moving Engineered Laser Head & Carriage Assembly (`Laser_Machined_Carriage`)
    # --------------------------------------------------------------------------
    mesh_c = bpy.data.meshes.new("Laser_Machined_Carriage")
    bm = bmesh.new()

    # Materials mapping in bmesh:
    # 0 = mat_carriage (billet dark hard-anodized aluminum)
    # 1 = mat_steel (ground steel runner block)
    # 2 = mat_stainless (fittings, cooling fins, bolts)
    # 3 = mat_wiper (black wiper seal)
    # 4 = mat_ceramic (capacitive isolator ring)
    # 5 = mat_brass (knurled collar)
    # 6 = mat_nozzle (stealth carbon nozzle)

    # A. Dual Linear Runner Blocks (recirculating ball carriages)
    # Left: x = -0.135 .. -0.085 m (50 mm wide)
    # Right: x = +0.085 .. +0.135 m (50 mm wide)
    # Wraps rail: y = 0.016 .. 0.042 m, z = 0.145 .. 0.171 m
    for bx0, bx1 in [(-0.135, -0.085), (+0.085, +0.135)]:
        # Outer steel body
        create_box_bmesh(bm, (bx0, 0.016, 0.164), (bx1, 0.042, 0.172), mat_idx=1)  # Top bridge
        create_box_bmesh(bm, (bx0, 0.016, 0.145), (bx1, 0.020, 0.164), mat_idx=1)  # Front flank
        create_box_bmesh(bm, (bx0, 0.038, 0.145), (bx1, 0.042, 0.164), mat_idx=1)  # Back flank

        # Wiper seal end-plates (1.5 mm thick at each end)
        for wx in [bx0 - 0.0015, bx1]:
            create_box_bmesh(bm, (wx, 0.015, 0.144), (wx + 0.0015, 0.020, 0.172), mat_idx=3)
            create_box_bmesh(bm, (wx, 0.038, 0.144), (wx + 0.0015, 0.043, 0.172), mat_idx=3)
            create_box_bmesh(bm, (wx, 0.020, 0.168), (wx + 0.0015, 0.038, 0.172), mat_idx=3)

        # Front grease fitting nipple
        cx = 0.5 * (bx0 + bx1)
        create_cylinder_bmesh(bm, 0.0022, 0.157, 0.161, (cx, 0.015), segments=8, mat_idx=5)
        create_cylinder_bmesh(bm, 0.0012, 0.158, 0.160, (cx, 0.013), segments=8, mat_idx=2)

        # 4 SHCS bolts mounting block to carriage plate
        for sx in [bx0 + 0.012, bx1 - 0.012]:
            for sy in [0.022, 0.036]:
                create_shcs_bolt(bm, (sx, sy, 0.172), dir_axis="Z", head_rad=0.0026, head_len=0.0022, mat_idx=2)

    # B. Main CNC Carriage Plate / Chassis (Aerospace Pocketed Billet)
    # Spans x = -0.140 .. +0.140 m (280 mm wide), y = -0.024 .. +0.016 m (40 mm deep), z = 0.128 .. 0.164 m (36 mm tall)
    create_box_bmesh(bm, (-0.140, -0.021, 0.128), (+0.140, 0.016, 0.164), mat_idx=0)

    # Stepped front face with weight-reduction pockets:
    # Outer pocket rims (raised perimeter flanges of thickness 3 mm, depth 2.5 mm)
    # Left pocket: x = -0.128 .. -0.032 m, z = 0.134 .. 0.158 m
    # Right pocket: x = +0.032 .. +0.128 m, z = 0.134 .. 0.158 m
    for px0, px1 in [(-0.128, -0.032), (+0.032, +0.128)]:
        # Front pocket border frame
        create_box_bmesh(bm, (px0 - 0.003, -0.0235, 0.131), (px0, -0.021, 0.161), mat_idx=0)
        create_box_bmesh(bm, (px1, -0.0235, 0.131), (px1 + 0.003, -0.021, 0.161), mat_idx=0)
        create_box_bmesh(bm, (px0, -0.0235, 0.158), (px1, -0.021, 0.161), mat_idx=0)
        create_box_bmesh(bm, (px0, -0.0235, 0.131), (px1, -0.021, 0.134), mat_idx=0)
        # Structural stiffening diagonal/vertical web rib inside pocket
        rx_mid = 0.5 * (px0 + px1)
        create_box_bmesh(bm, (rx_mid - 0.0018, -0.0225, 0.134), (rx_mid + 0.0018, -0.021, 0.158), mat_idx=0)

    # 8 Front face countersunk SHCS bolts along perimeter margins
    for bx in [-0.132, -0.080, 0.080, 0.132]:
        for bz in [0.131, 0.161]:
            create_shcs_bolt(bm, (bx, -0.0235, bz), dir_axis="-Y", head_rad=0.0022, head_len=0.0018, mat_idx=2)

    # C. Central Optical Collimator Column (The Core Laser Barrel)
    # Co-axial with pipe top spine at x = 0.0, y = 0.0. Height: z = 0.124 .. 0.166 m (flush with rail top)
    create_cylinder_bmesh(bm, 0.018, 0.124, 0.166, (0.0, 0.0), segments=36, mat_idx=0, cap_top=True, cap_bottom=False)

    # 4 Machined Annular Cooling Fins / Heat Dissipation Flutes
    # Fin outer radius = 21.0 mm (diameter 42 mm), thickness = 1.5 mm
    fin_z_list = [0.1460, 0.1505, 0.1550, 0.1595]
    for fz in fin_z_list:
        create_cylinder_bmesh(bm, 0.0210, fz, fz + 0.0015, (0.0, 0.0), segments=36, mat_idx=2, cap_top=True, cap_bottom=True)

    # D. Upper QBH Fiber Optic Cable Collimator Receiver (Compact, flush with rail horizon)
    # Rises only 5 mm above rail top (z = 0.166 .. 0.173 m)
    create_cylinder_bmesh(bm, 0.012, 0.166, 0.170, (0.0, 0.0), segments=24, mat_idx=2)
    # Armored conduit strain-relief gland (angled slightly back by 15 deg into darkness)
    create_cylinder_bmesh(bm, 0.0075, 0.170, 0.174, (0.0, 0.002), segments=16, mat_idx=0)

    # E. Dual Assist Gas Manifold Ports (N2 / O2 90-deg stainless elbow compression fittings)
    create_elbow_fitting(bm, (-0.036, 0.006, 0.144), dir_x=-1.0, mat_idx=2)
    create_elbow_fitting(bm, (+0.036, 0.006, 0.144), dir_x=+1.0, mat_idx=2)

    # F. Dynamic Z-Axis Sensor Collar & Technical Ceramic Isolator Ring
    # 1. Knurled brass/bronze retention ring (z = 0.118 .. 0.124 m, radius 13 mm)
    create_cylinder_bmesh(bm, 0.013, 0.118, 0.124, (0.0, 0.0), segments=32, mat_idx=5)
    # 2. High-purity white ceramic electrical isolation ring (z = 0.112 .. 0.118 m, radius 11 mm)
    create_cylinder_bmesh(bm, 0.011, 0.112, 0.118, (0.0, 0.0), segments=32, mat_idx=4)

    # G. Indistinguishable Tiny Laser Emitter Tip (Conical Stealth Nozzle)
    # Standoff above pipe top spine (z = 0.0889 m): tip at z = 0.0979 m (9.0 mm clearance)
    # Tapers smoothly from 9.5 mm radius at ceramic ring to 4.5 mm radius at tip with 2.0 mm exit orifice
    tip_z = aperture_tip_z
    top_z = 0.112
    noz_rings = []
    noz_profile = [
        (tip_z, 0.0020),          # Inner exit orifice (4 mm diameter)
        (tip_z, 0.0045),          # Outer tip lip (9 mm diameter)
        (tip_z + 0.003, 0.0055),  # Conical taper
        (tip_z + 0.008, 0.0075),
        (top_z, 0.0095),          # Collar meeting ceramic ring
    ]
    segs = 32
    for z_v, r_v in noz_profile:
        ring = []
        for i in range(segs):
            a = (2.0 * math.pi * i) / segs
            ring.append(bm.verts.new((r_v * math.cos(a), r_v * math.sin(a), z_v)))
        noz_rings.append(ring)
    for r_i in range(len(noz_rings) - 1):
        for i in range(segs):
            inext = (i + 1) % segs
            f = bm.faces.new((noz_rings[r_i][i], noz_rings[r_i][inext], noz_rings[r_i + 1][inext], noz_rings[r_i + 1][i]))
            f.smooth = True
            f.material_index = 6
    f_top = bm.faces.new(reversed(noz_rings[-1]))
    f_top.smooth = False
    f_top.material_index = 6
    f_bot = bm.faces.new(noz_rings[0])
    f_bot.smooth = False
    f_bot.material_index = 6

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh_c)
    bm.free()

    obj_carriage = bpy.data.objects.new("Laser_Machined_Carriage", mesh_c)
    bpy.context.scene.collection.objects.link(obj_carriage)
    obj_carriage.data.materials.append(mats["carriage"])   # Slot 0: billet anodized aluminum
    obj_carriage.data.materials.append(mats["steel"])      # Slot 1: ground runner steel
    obj_carriage.data.materials.append(mats["stainless"])  # Slot 2: stainless hardware & fins
    obj_carriage.data.materials.append(mats["wiper"])      # Slot 3: dark wiper seal
    obj_carriage.data.materials.append(mats["ceramic"])    # Slot 4: white ceramic isolator
    obj_carriage.data.materials.append(mats["brass"])      # Slot 5: knurled brass collar
    obj_carriage.data.materials.append(mats["nozzle"])     # Slot 6: stealth carbon nozzle

    objs["carriage"] = obj_carriage
    objs["nozzle"] = obj_carriage  # Moving shuttle parented to all laser FX

    return objs


def build_center_slot_and_laser_fx(
    mats: dict[str, bpy.types.Material],
    shuttle_obj: bpy.types.Object,
) -> dict[str, bpy.types.Object]:
    """Build the 12 o'clock top-spine laser strike FX parented to the tiny stealth shuttle (`shuttle_obj`).
    No visible slot face on the side of the pipe—the viewer must infer what happened from the surgical
    60 mm axial laser pass along the top spine.
    """
    objs: dict[str, bpy.types.Object] = {}
    r_pipe = PIPE_OD_M / 2.0  # 0.0889 m

    # 1. Hairline Top-Spine Thermal Horizon Edge (strictly at 12 o'clock top dead center, y = 0, z = r_pipe)
    mesh_slot = bpy.data.meshes.new("Top_Spine_Thermal_Edge")
    bm_s = bmesh.new()
    x0, x1 = -SLOT_LEN_M / 2.0, SLOT_LEN_M / 2.0
    half_w = 0.0005
    z_top = r_pipe + 0.0003

    v0 = bm_s.verts.new((x0, -half_w, z_top))
    v1 = bm_s.verts.new((x1, -half_w, z_top))
    v2 = bm_s.verts.new((x1, +half_w, z_top))
    v3 = bm_s.verts.new((x0, +half_w, z_top))
    bm_s.faces.new((v0, v1, v2, v3))
    bmesh.ops.recalc_face_normals(bm_s, faces=bm_s.faces)
    bm_s.to_mesh(mesh_slot)
    bm_s.free()

    obj_slot = bpy.data.objects.new("Top_Spine_Thermal_Edge", mesh_slot)
    bpy.context.scene.collection.objects.link(obj_slot)
    obj_slot.data.materials.append(mats["slot"])
    objs["slot"] = obj_slot

    # 2. Razor-Thin Coaxial Laser Beam Cylinder (bridges the 8.5 mm standoff gap at 12 o'clock, y = 0)
    mesh_beam = bpy.data.meshes.new("Laser_Beam_Jet")
    bm_b = bmesh.new()
    bmesh.ops.create_cone(
        bm_b,
        cap_ends=True,
        cap_tris=False,
        segments=32,
        radius1=0.0009,  # 1.8 mm surgical needle core
        radius2=0.0013,
        depth=0.011,
    )
    for v in bm_b.verts:
        v.co.z += r_pipe + 0.0042
        v.co.y = 0.0
    bm_b.to_mesh(mesh_beam)
    bm_b.free()

    obj_beam = bpy.data.objects.new("Laser_Beam_Jet", mesh_beam)
    bpy.context.scene.collection.objects.link(obj_beam)
    obj_beam.data.materials.append(mats["beam"])
    obj_beam.parent = shuttle_obj
    objs["beam"] = obj_beam

    # 3. Camera-facing Optical Plasma Keyhole Halo + Anamorphic Horizontal Streak (parented to tiny shuttle)
    def make_glow_quad(
        name: str, scale_x: float, scale_z: float, z_pos: float, mat: bpy.types.Material, parent: bpy.types.Object | None = None
    ) -> bpy.types.Object:
        m_q = bpy.data.meshes.new(name)
        bm_q = bmesh.new()
        bmesh.ops.create_grid(bm_q, x_segments=16, y_segments=16, size=1.0)
        bmesh.ops.rotate(bm_q, verts=bm_q.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90.0), 3, "X"))
        bm_q.to_mesh(m_q)
        bm_q.free()
        o_q = bpy.data.objects.new(name, m_q)
        bpy.context.scene.collection.objects.link(o_q)
        o_q.location = Vector((0.0, -0.005, z_pos))
        o_q.scale = Vector((scale_x, 1.0, scale_z))
        o_q.data.materials.append(mat)
        o_q.visible_shadow = False
        o_q.visible_diffuse = False
        if parent is not None:
            o_q.parent = parent
        return o_q

    # 3a. Tight surgical plasma bloom right in the 8.5 mm gap
    objs["plasma_bloom"] = make_glow_quad("Laser_Plasma_Bloom", 0.052, 0.036, r_pipe + 0.0040, mats["plasma_halo"], shuttle_obj)
    # 3b. Subtle high-tech horizontal anamorphic optical flare streak during laser ignition
    objs["anamorphic_streak"] = make_glow_quad("Laser_Anamorphic_Streak", 0.340, 0.010, r_pipe + 0.0032, mats["plasma_halo"], shuttle_obj)
    # 3c. Post-cut warm residual horizon shimmer right at 12 o'clock top spine (Beat 3 inference cue!)
    objs["ember_shimmer"] = make_glow_quad("Top_Spine_Ember_Shimmer", 0.055, 0.013, r_pipe + 0.002, mats["ember_halo"], None)

    # 4. Tight High-Velocity Micro-Spark / Ionized Vapor Plume skimming along the 12 o'clock top spine
    mesh_sparks = bpy.data.meshes.new("Laser_Micro_Sparks")
    bm_sp = bmesh.new()
    spark_vectors = [
        (-0.024, -0.005, 0.012, 0.0008),
        (-0.038, -0.008, 0.008, 0.0007),
        (0.020, -0.005, 0.011, 0.0008),
        (0.035, 0.004, 0.007, 0.0007),
        (-0.012, -0.008, 0.016, 0.0007),
        (0.010, 0.005, 0.015, 0.0007),
        (-0.048, -0.004, 0.004, 0.0006),
        (0.045, -0.004, 0.004, 0.0006),
    ]
    origin = Vector((0.0, 0.0, r_pipe + 0.0016))
    for dx, dy, dz, rad in spark_vectors:
        tip = origin + Vector((dx, dy, dz))
        mid = origin.lerp(tip, 0.5)
        vec = tip - origin
        length = vec.length
        ret = bmesh.ops.create_cone(
            bm_sp,
            cap_ends=True,
            cap_tris=True,
            segments=8,
            radius1=rad,
            radius2=rad * 0.2,
            depth=length,
        )
        rot_mat = vec.normalized().to_track_quat("Z", "X").to_matrix().to_4x4()
        bmesh.ops.transform(bm_sp, matrix=Matrix.Translation(mid) @ rot_mat, verts=ret["verts"])

    bm_sp.to_mesh(mesh_sparks)
    bm_sp.free()
    obj_sparks = bpy.data.objects.new("Laser_Micro_Sparks", mesh_sparks)
    bpy.context.scene.collection.objects.link(obj_sparks)
    obj_sparks.data.materials.append(mats["spark"])
    obj_sparks.parent = shuttle_obj
    objs["sparks"] = obj_sparks

    return objs


# ==============================================================================
# LIGHTING, WORLD & CAMERA (CONTROLLED SHEEN + MYSTERY SILHOUETTE)
# ==============================================================================
def setup_world_and_lights(
    scene: bpy.types.Scene,
    pipe_objs: dict[str, bpy.types.Object],
    head_objs: dict[str, bpy.types.Object],
) -> dict[str, bpy.types.Object]:
    lights: dict[str, bpy.types.Object] = {}
    shuttle_obj = head_objs["nozzle"]

    # Create Blender 5.2 Light-Linking Receiver Collections:
    # - Pipe lights ONLY illuminate the pipe & red bookends (zero spill on mystery mechanism above!)
    # - Overhead mechanism rim lights ONLY illuminate the large upper carriage (`head_shroud`),
    #   leaving the tiny lower laser emitter (`nozzle`) completely unlit and indistinguishable!
    col_pipe_recv = bpy.data.collections.new("LL_Pipe_Receivers")
    for obj in pipe_objs.values():
        col_pipe_recv.objects.link(obj)

    col_head_recv = bpy.data.collections.new("LL_Head_Receivers")
    if "rail" in head_objs:
        col_head_recv.objects.link(head_objs["rail"])
    if "carriage" in head_objs:
        col_head_recv.objects.link(head_objs["carriage"])
    elif "head_shroud" in head_objs:
        col_head_recv.objects.link(head_objs["head_shroud"])

    # 1. World Shader: Ultra-low-strength desaturated studio.exr (0.006) so dark black steel stays
    # deep black outside its studio rim highlights; pure black (0.0004) for camera rays.
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
    bg_cam.inputs["Color"].default_value = (0.0004, 0.0005, 0.0007, 1.0)
    bg_cam.inputs["Strength"].default_value = 1.0

    light_path = nodes.new("ShaderNodeLightPath")
    mix = nodes.new("ShaderNodeMixShader")
    links.new(light_path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    links.new(bg_refl.outputs["Background"], mix.inputs[1])
    links.new(bg_cam.outputs["Background"], mix.inputs[2])

    out = nodes.new("ShaderNodeOutputWorld")
    links.new(mix.outputs["Shader"], out.inputs["Surface"])

    # Helper to create rectangular AREA strip lights parallel to X axis with beam spread & Light Linking
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

    # 2. Primary Pipe Upper-Shoulder Sheen Strip (Light-linked strictly to Pipe & Red Ends):
    lights["pipe_key_strip"] = add_strip_light(
        name="Pipe_Sheen_Key_Strip",
        location=(0.0, -1.60, 1.55),
        target=(0.0, 0.0, 0.055),
        energy=48.0,
        size_x_long=10.2,
        size_y_narrow=0.11,
        color=(0.90, 0.94, 1.0),
        spread_deg=34.0,
        receiver_col=col_pipe_recv,
    )

    # 3. Lower Edge Separation Strip (Light-linked strictly to Pipe & Red Ends):
    lights["pipe_bottom_rim"] = add_strip_light(
        name="Pipe_Bottom_Rim_Strip",
        location=(0.0, -1.60, -1.35),
        target=(0.0, 0.0, -0.060),
        energy=22.0,
        size_x_long=10.0,
        size_y_narrow=0.09,
        color=(0.76, 0.84, 1.0),
        spread_deg=32.0,
        receiver_col=col_pipe_recv,
    )

    # 4. Left & Right Red Accent Kickers (Light-linked strictly to Pipe & Red Ends)
    lights["left_coupling_kicker"] = add_strip_light(
        name="Left_Coupling_Kicker",
        location=(-4.45, -1.25, 0.42),
        target=(-4.45, 0.0, 0.0),
        energy=12.0,
        size_x_long=0.45,
        size_y_narrow=0.22,
        color=(1.0, 0.94, 0.90),
        spread_deg=35.0,
        receiver_col=col_pipe_recv,
    )
    lights["right_protector_kicker"] = add_strip_light(
        name="Right_Protector_Kicker",
        location=(4.45, -1.25, 0.42),
        target=(4.45, 0.0, 0.0),
        energy=12.0,
        size_x_long=0.45,
        size_y_narrow=0.22,
        color=(1.0, 0.94, 0.90),
        spread_deg=35.0,
        receiver_col=col_pipe_recv,
    )

    # 5. Whisper-Soft Specular Hairline Rim on the Sleek Linear Rail & Cooling Fins (`col_head_recv` ONLY):
    # Gives understated metallic edge hairlines along the linear rail top and fin contours
    # while leaving the lower nozzle and carriage front in deep, indistinguishable shadow!
    lights["mystery_head_rim_left"] = add_strip_light(
        name="Mystery_Head_Rim_Left",
        location=(-0.60, -0.18, 0.24),
        target=(-0.10, 0.025, 0.165),
        energy=0.65,
        size_x_long=0.12,
        size_y_narrow=0.12,
        color=(0.72, 0.82, 1.0),
        spread_deg=28.0,
        receiver_col=col_head_recv,
    )
    lights["mystery_head_rim_right"] = add_strip_light(
        name="Mystery_Head_Rim_Right",
        location=(0.60, -0.18, 0.24),
        target=(0.10, 0.025, 0.165),
        energy=0.45,
        size_x_long=0.12,
        size_y_narrow=0.12,
        color=(0.72, 0.82, 1.0),
        spread_deg=28.0,
        receiver_col=col_head_recv,
    )
    lights["mystery_head_top_rim"] = add_strip_light(
        name="Mystery_Head_Top_Rim",
        location=(0.0, -0.22, 0.46),
        target=(0.0, 0.025, 0.168),
        energy=0.85,
        size_x_long=0.46,
        size_y_narrow=0.025,
        color=(0.76, 0.86, 1.0),
        spread_deg=24.0,
        receiver_col=col_head_recv,
    )

    # 6. Dynamic Laser Strike Point Lights (0 W in Beat 1; ignite in Beat 2!)
    # 6a. Tight Pinpoint Flash right at the 12 o'clock top spine gap (light-linked to pipe so stealth collar stays dark)
    p_flash = bpy.data.lights.new("Laser_Strike_Optical_Flash", "POINT")
    p_flash.energy = 0.0
    p_flash.color = (0.68, 0.88, 1.0)
    p_flash.shadow_soft_size = 0.006
    obj_flash = bpy.data.objects.new("Laser_Strike_Optical_Flash", p_flash)
    scene.collection.objects.link(obj_flash)
    obj_flash.location = Vector((0.0, -0.018, PIPE_OD_M / 2.0 + 0.010))
    obj_flash.light_linking.receiver_collection = col_pipe_recv
    obj_flash.parent = shuttle_obj
    lights["laser_flash"] = obj_flash

    # 6b. Upward Cyan-White Bounce Illumination on the Sleek Linear Rail Belly (`col_head_recv` ONLY)
    p_bounce = bpy.data.lights.new("Laser_Head_Belly_Bounce", "POINT")
    p_bounce.energy = 0.0
    p_bounce.color = (0.62, 0.86, 1.0)
    p_bounce.shadow_soft_size = 0.025
    obj_bounce = bpy.data.objects.new("Laser_Head_Belly_Bounce", p_bounce)
    scene.collection.objects.link(obj_bounce)
    obj_bounce.location = Vector((0.0, -0.045, PIPE_OD_M / 2.0 + 0.022))
    obj_bounce.light_linking.receiver_collection = col_head_recv
    obj_bounce.parent = shuttle_obj
    lights["head_belly_bounce"] = obj_bounce

    # 6c. Warm Molten Kerf Afterglow Point Light right at the 12 o'clock top spine (`col_pipe_recv` ONLY — zero nozzle reflection!)
    p_ember = bpy.data.lights.new("Laser_Kerf_Warm_Glow", "POINT")
    p_ember.energy = 0.0
    p_ember.color = (1.0, 0.42, 0.08)
    p_ember.shadow_soft_size = 0.004
    obj_ember = bpy.data.objects.new("Laser_Kerf_Warm_Glow", p_ember)
    scene.collection.objects.link(obj_ember)
    obj_ember.location = Vector((0.0, -0.018, PIPE_OD_M / 2.0 + 0.008))
    obj_ember.light_linking.receiver_collection = col_pipe_recv
    lights["kerf_ember"] = obj_ember

    return lights


def setup_camera(scene: bpy.types.Scene) -> bpy.types.Object:
    """Option A: True Dead-Level Side-Profile Wide 16:9 framing the entire 9.0 m pipe from red coupling
    to red thread protector, plus the mysterious overhead mechanism poised above the center.
    Because the camera is dead-level with the side of the pipe, the 12 o'clock top-spine cut is
    strictly edge-on: the viewer never sees the slot face directly and must infer what is happening.
    """
    cam_data = bpy.data.cameras.new("Hero_Side_Wide_Cam")
    cam_data.lens = 85.0
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.05
    cam_data.clip_end = 100.0

    cam_obj = bpy.data.objects.new("Hero_Side_Wide_Cam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    target = Vector((0.0, 0.0, 0.14))  # Dead-level horizon at z = 0.14 m
    desired_width_m = 10.05
    dist_y = desired_width_m * (cam_data.lens / cam_data.sensor_width)  # ~23.73 m
    cam_obj.location = Vector((0.0, -dist_y, 0.14))  # Dead-level side profile (0 deg pitch)

    direction = target - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    return cam_obj


# ==============================================================================
# ANIMATION TIMELINE (BEAT 1 STILLNESS -> BEAT 2 SURGICAL STRIKE -> BEAT 3 AFTERGLOW)
# ==============================================================================
def animate_laser_sequence(
    shuttle_obj: bpy.types.Object,
    fx_objs: dict[str, bpy.types.Object],
    lights: dict[str, bpy.types.Object],
    mats: dict[str, bpy.types.Material],
) -> None:
    bsdf_beam = get_node_by_type(mats["beam"].node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_slot = get_node_by_type(mats["slot"].node_tree, "ShaderNodeBsdfPrincipled")
    bsdf_spark = get_node_by_type(mats["spark"].node_tree, "ShaderNodeBsdfPrincipled")
    emit_plasma = get_node_by_type(mats["plasma_halo"].node_tree, "ShaderNodeEmission")
    emit_ember = get_node_by_type(mats["ember_halo"].node_tree, "ShaderNodeEmission")

    flash_light = lights["laser_flash"].data
    bounce_light = lights["head_belly_bounce"].data
    ember_light = lights["kerf_ember"].data
    sparks_obj = fx_objs["sparks"]
    beam_obj = fx_objs["beam"]
    plasma_bloom = fx_objs["plasma_bloom"]
    anamorphic_streak = fx_objs["anamorphic_streak"]
    ember_shimmer = fx_objs["ember_shimmer"]
    slot_obj = fx_objs["slot"]

    # The large overhead mechanism (`head_shroud`) stays poised over x = 0, while the tiny
    # indistinguishable laser shuttle (`shuttle_obj`) settles into start of center pass (-0.030 m)
    # during Beat 1, zips across the 60 mm pass (-0.030 -> +0.030 m) during frames 68..84, and stops dead.
    shuttle_keyframes = [
        (1, -0.030, 0.008),
        (12, -0.030, 0.0),
        (FRAME_FIRE_START, -0.030, 0.0),
        (FRAME_FIRE_END, +0.030, 0.0),
        (FRAME_END, +0.030, 0.0),
    ]
    for frame, x_pos, z_offset in shuttle_keyframes:
        shuttle_obj.location = Vector((x_pos, 0.0, z_offset))
        shuttle_obj.keyframe_insert(data_path="location", frame=frame)

    for f in range(FRAME_START, FRAME_END + 1):
        if f < FRAME_FIRE_START:
            # Beat 1: Stillness — complete quiet before the laser fires
            beam_em = 0.0
            plasma_em = 0.0
            ember_halo_em = 0.0
            slot_em = 0.0
            spark_em = 0.0
            flash_w = 0.0
            bounce_w = 0.0
            ember_w = 0.0
            slot_scale_x = 0.001
            hide_strike = True
            hide_afterglow = True
        elif FRAME_FIRE_START <= f <= FRAME_FIRE_END:
            # Beat 2: Surgical 12 kW Fiber Laser Strike (frames 68..84)
            u = (f - FRAME_FIRE_START) / float(FRAME_FIRE_END - FRAME_FIRE_START)
            pulse = 1.0 + 0.20 * math.sin(u * math.pi * 6.0)
            beam_em = 950.0 * pulse
            plasma_em = 195.0 * pulse
            ember_halo_em = 45.0
            slot_em = 140.0
            spark_em = 220.0 * pulse
            flash_w = 95.0 * pulse
            bounce_w = 26.0 * pulse
            ember_w = 24.0
            slot_scale_x = max(0.05, u)
            hide_strike = False
            hide_afterglow = False
        else:
            # Beat 3: Instant laser cutoff, subtle residual thermal horizon shimmer at 12 o'clock
            dt = (f - FRAME_FIRE_END) / float(FRAME_END - FRAME_FIRE_END)
            decay = math.exp(-2.2 * dt)
            beam_em = 0.0
            plasma_em = 0.0
            ember_halo_em = 38.0 * decay
            slot_em = 75.0 * decay
            spark_em = 0.0
            flash_w = 0.0
            bounce_w = 0.0
            ember_w = 14.0 * decay
            slot_scale_x = 1.0
            hide_strike = True
            hide_afterglow = False

        bsdf_beam.inputs["Emission Strength"].default_value = beam_em
        bsdf_beam.inputs["Emission Strength"].keyframe_insert(data_path="default_value", frame=f)

        emit_plasma.inputs["Strength"].default_value = plasma_em
        emit_plasma.inputs["Strength"].keyframe_insert(data_path="default_value", frame=f)

        emit_ember.inputs["Strength"].default_value = ember_halo_em
        emit_ember.inputs["Strength"].keyframe_insert(data_path="default_value", frame=f)

        bsdf_slot.inputs["Emission Strength"].default_value = slot_em
        bsdf_slot.inputs["Emission Strength"].keyframe_insert(data_path="default_value", frame=f)

        bsdf_spark.inputs["Emission Strength"].default_value = spark_em
        bsdf_spark.inputs["Emission Strength"].keyframe_insert(data_path="default_value", frame=f)

        flash_light.energy = flash_w
        flash_light.keyframe_insert(data_path="energy", frame=f)

        bounce_light.energy = bounce_w
        bounce_light.keyframe_insert(data_path="energy", frame=f)

        ember_light.energy = ember_w
        ember_light.keyframe_insert(data_path="energy", frame=f)

        slot_obj.scale = Vector((slot_scale_x, 1.0, 1.0))
        slot_obj.keyframe_insert(data_path="scale", frame=f)

        for o in (beam_obj, sparks_obj, plasma_bloom, anamorphic_streak):
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
    """Gate 0 & Gate 2: Verify true metric dimensions and camera projection of all key subjects."""
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
        "left_red_coupling": Vector((-4.55, 0.0, 0.0)),
        "center_top_spine": Vector((0.0, 0.0, PIPE_OD_M / 2.0)),
        "right_red_protector": Vector((4.52, 0.0, 0.0)),
        "stealth_laser_shuttle": Vector((0.0, 0.0, PIPE_OD_M / 2.0 + 0.02)),
        "sleek_linear_stage_bar": Vector((0.0, 0.0, 0.160)),
    }
    projections = {}
    for label, pt in key_points.items():
        ndc = world_to_camera_view(scene, cam, pt)
        in_frame = (0.02 <= ndc.x <= 0.98) and (0.05 <= ndc.y <= 0.95) and (ndc.z > 0.0)
        assert in_frame, f"Gate 2 FAILED: {label} projected out of frame at NDC=({ndc.x:.3f}, {ndc.y:.3f}, {ndc.z:.3f})"
        projections[label] = {"ndc_x": round(ndc.x, 4), "ndc_y": round(ndc.y, 4), "depth_m": round(ndc.z, 3)}

    span_ndc_x = projections["right_red_protector"]["ndc_x"] - projections["left_red_coupling"]["ndc_x"]
    assert 0.82 <= span_ndc_x <= 0.95, f"Pipe horizontal span {span_ndc_x:.3f} outside target [0.82, 0.95]"

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
    out_dir = Path(r"c:\Users\kyle\MPS\slotted-liner\marketing\blender\renders\v6_lookdev")
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

    scene.frame_set(CHECK_FRAMES["beat1_stillness"])
    audit = audit_scene_geometry(scene, cam, pipe_objs, head_objs)

    blend_path = scene_dir / "laser_slotted_liner_teaser_v6.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    rendered_files: dict[str, dict] = {}
    seen_hashes: set[str] = set()
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
    receipt_path = out_dir / "v6_lookdev_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("LOOKDEV_V6_DONE", json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
