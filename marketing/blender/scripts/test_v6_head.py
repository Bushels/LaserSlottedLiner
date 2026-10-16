"""Test script to build the complete Look-Dev v6 Engineered Laser Head & Linear Stage Assembly.
"""
import sys
import math
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

# Reset scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Reference dimensions
PIPE_OD_M = 0.1778  # 7.000 inches
r_pipe = PIPE_OD_M / 2.0  # 0.0889 m
aperture_tip_z = r_pipe + 0.0090  # 0.0979 m (9 mm standoff)

# ------------------------------------------------------------------------------
# Geometry Helper Functions
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
        bm.verts.new((x0, y0, z0)),  # 0
        bm.verts.new((x1, y0, z0)),  # 1
        bm.verts.new((x1, y1, z0)),  # 2
        bm.verts.new((x0, y1, z0)),  # 3
        bm.verts.new((x0, y0, z1)),  # 4
        bm.verts.new((x1, y0, z1)),  # 5
        bm.verts.new((x1, y1, z1)),  # 6
        bm.verts.new((x0, y1, z1)),  # 7
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
    head_rad: float = 0.0032,
    head_len: float = 0.0028,
    socket_rad: float = 0.0016,
    socket_depth: float = 0.0018,
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
    """Stainless 90-deg compression elbow fitting for assist gas."""
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

# ------------------------------------------------------------------------------
# 1. Build Stationary Profiled Linear Guide Rail
# ------------------------------------------------------------------------------
def build_linear_guide_rail() -> bpy.types.Mesh:
    mesh_rail = bpy.data.meshes.new("Linear_Rail_Track")
    bm_r = bmesh.new()

    # Ground steel rail profile extruded along X (-0.220 m .. +0.220 m = 440 mm)
    # Y: 0.014 m .. 0.032 m (18 mm wide)
    # Z: 0.148 m .. 0.168 m (20 mm tall)
    # With Gothic-arch ball raceway grooves along both Y flanks at z = 0.155 .. 0.161 m
    rail_yz = [
        # Bottom face
        (0.0140, 0.1480),
        (0.0320, 0.1480),
        # Back face lower
        (0.0320, 0.1550),
        # Back Gothic-arch raceway groove (recessed by 1.2 mm)
        (0.0308, 0.1565),
        (0.0308, 0.1595),
        (0.0320, 0.1610),
        # Back face upper
        (0.0320, 0.1668),
        # Top chamfer back
        (0.0308, 0.1680),
        # Top face
        (0.0152, 0.1680),
        # Top chamfer front
        (0.0140, 0.1668),
        # Front face upper
        (0.0140, 0.1610),
        # Front Gothic-arch raceway groove (recessed by 1.2 mm)
        (0.0152, 0.1595),
        (0.0152, 0.1565),
        # Front face lower
        (0.0140, 0.1550),
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
        create_shcs_bolt(bm_r, (bx, 0.023, 0.168), dir_axis="Z", head_rad=0.0030, head_len=0.0025, socket_rad=0.0015, socket_depth=0.0016, mat_idx=2)

    # Rail end-stop bumpers with cap screws at both ends
    for ex in [-0.222, +0.220]:
        create_box_bmesh(bm_r, (ex - 0.002, 0.013, 0.147), (ex + 0.002, 0.033, 0.169), mat_idx=2)
        create_shcs_bolt(bm_r, (ex, 0.023, 0.169), dir_axis="Z", head_rad=0.0025, head_len=0.0020, mat_idx=2)

    bmesh.ops.recalc_face_normals(bm_r, faces=bm_r.faces)
    bm_r.to_mesh(mesh_rail)
    bm_r.free()
    return mesh_rail

# ------------------------------------------------------------------------------
# 2. Build Engineered Moving Laser Head & Carriage Assembly
# ------------------------------------------------------------------------------
def build_machined_laser_carriage() -> bpy.types.Mesh:
    mesh_c = bpy.data.meshes.new("Laser_Machined_Carriage")
    bm = bmesh.new()

    # Materials mapping:
    # 0 = mat_carriage (billet anodized aluminum)
    # 1 = mat_steel (ground steel runner block)
    # 2 = mat_stainless (fittings, fins, bolts)
    # 3 = mat_wiper (black wiper seal)
    # 4 = mat_ceramic (capacitive isolator ring)
    # 5 = mat_brass (knurled collar)
    # 6 = mat_nozzle (stealth carbon nozzle)

    # A. Dual Linear Runner Blocks (recirculating ball carriages)
    # Left: x = -0.135 .. -0.085 m (50 mm wide)
    # Right: x = +0.085 .. +0.135 m (50 mm wide)
    # Wraps rail: y = 0.010 .. 0.036 m, z = 0.145 .. 0.171 m
    for bx0, bx1 in [(-0.135, -0.085), (+0.085, +0.135)]:
        # Outer steel body
        create_box_bmesh(bm, (bx0, 0.010, 0.164), (bx1, 0.036, 0.172), mat_idx=1)  # Top bridge
        create_box_bmesh(bm, (bx0, 0.010, 0.145), (bx1, 0.014, 0.164), mat_idx=1)  # Front flank
        create_box_bmesh(bm, (bx0, 0.032, 0.145), (bx1, 0.036, 0.164), mat_idx=1)  # Back flank

        # Wiper seal end-plates (1.5 mm thick at each end)
        for wx in [bx0 - 0.0015, bx1]:
            create_box_bmesh(bm, (wx, 0.009, 0.144), (wx + 0.0015, 0.014, 0.172), mat_idx=3)
            create_box_bmesh(bm, (wx, 0.032, 0.144), (wx + 0.0015, 0.037, 0.172), mat_idx=3)
            create_box_bmesh(bm, (wx, 0.014, 0.168), (wx + 0.0015, 0.032, 0.172), mat_idx=3)

        # Front grease fitting nipple
        cx = 0.5 * (bx0 + bx1)
        create_cylinder_bmesh(bm, 0.0022, 0.157, 0.161, (cx, 0.009), segments=8, mat_idx=5)
        create_cylinder_bmesh(bm, 0.0012, 0.158, 0.160, (cx, 0.007), segments=8, mat_idx=2)

        # 4 SHCS bolts mounting block to carriage plate
        for sx in [bx0 + 0.012, bx1 - 0.012]:
            for sy in [0.016, 0.030]:
                create_shcs_bolt(bm, (sx, sy, 0.172), dir_axis="Z", head_rad=0.0026, head_len=0.0022, mat_idx=2)

    # B. Main CNC Carriage Plate / Chassis (Aerospace Pocketed Billet)
    # Spans x = -0.140 .. +0.140 m (280 mm wide), y = -0.034 .. +0.010 m (44 mm deep), z = 0.128 .. 0.164 m (36 mm tall)
    # Base solid plate
    create_box_bmesh(bm, (-0.140, -0.031, 0.128), (+0.140, 0.010, 0.164), mat_idx=0)

    # Stepped front face with weight-reduction pockets:
    # Outer pocket rims (raised perimeter flanges of thickness 3 mm, depth 2.5 mm)
    # Left pocket: x = -0.125 .. -0.035 m, z = 0.134 .. 0.158 m
    # Right pocket: x = +0.035 .. +0.125 m, z = 0.134 .. 0.158 m
    for px0, px1 in [(-0.128, -0.032), (+0.032, +0.128)]:
        # Front pocket border frame
        create_box_bmesh(bm, (px0 - 0.003, -0.0335, 0.131), (px0, -0.031, 0.161), mat_idx=0)
        create_box_bmesh(bm, (px1, -0.0335, 0.131), (px1 + 0.003, -0.031, 0.161), mat_idx=0)
        create_box_bmesh(bm, (px0, -0.0335, 0.158), (px1, -0.031, 0.161), mat_idx=0)
        create_box_bmesh(bm, (px0, -0.0335, 0.131), (px1, -0.031, 0.134), mat_idx=0)
        # Structural stiffening diagonal/vertical web rib inside pocket
        rx_mid = 0.5 * (px0 + px1)
        create_box_bmesh(bm, (rx_mid - 0.0018, -0.0325, 0.134), (rx_mid + 0.0018, -0.031, 0.158), mat_idx=0)

    # 8 Front face countersunk SHCS bolts along perimeter margins
    for bx in [-0.132, -0.080, 0.080, 0.132]:
        for bz in [0.131, 0.161]:
            create_shcs_bolt(bm, (bx, -0.0335, bz), dir_axis="-Y", head_rad=0.0022, head_len=0.0018, mat_idx=2)

    # C. Central Optical Collimator Column (The Core Laser Barrel)
    # Center at x = 0.0, y = -0.014 m. Height: z = 0.124 .. 0.176 m (52 mm tall, radius 18 mm)
    cyl_cy = -0.014
    create_cylinder_bmesh(bm, 0.018, 0.124, 0.176, (0.0, cyl_cy), segments=36, mat_idx=0, cap_top=True, cap_bottom=False)

    # 4 Machined Annular Cooling Fins / Heat Dissipation Flutes
    # Fin outer radius = 21.5 mm (diameter 43 mm), thickness = 1.6 mm
    fin_z_list = [0.1500, 0.1542, 0.1584, 0.1626]
    for fz in fin_z_list:
        create_cylinder_bmesh(bm, 0.0215, fz, fz + 0.0016, (0.0, cyl_cy), segments=36, mat_idx=2, cap_top=True, cap_bottom=True)

    # D. Upper QBH Fiber Optic Cable Collimator Receiver
    # Top of optical column: z = 0.176 .. 0.192 m
    create_cylinder_bmesh(bm, 0.013, 0.176, 0.184, (0.0, cyl_cy), segments=24, mat_idx=2)
    # Knurled stainless locking ring
    create_cylinder_bmesh(bm, 0.014, 0.180, 0.183, (0.0, cyl_cy), segments=24, mat_idx=2)
    # Armored conduit strain-relief gland (angled slightly back by 10 deg)
    create_cylinder_bmesh(bm, 0.0085, 0.184, 0.194, (0.0, cyl_cy + 0.002), segments=16, mat_idx=0)

    # E. Dual Assist Gas Manifold Ports (N2 / O2 90-deg stainless elbow compression fittings)
    create_elbow_fitting(bm, (-0.036, -0.006, 0.144), dir_x=-1.0, mat_idx=2)
    create_elbow_fitting(bm, (+0.036, -0.006, 0.144), dir_x=+1.0, mat_idx=2)

    # F. Dynamic Z-Axis Sensor Collar & Technical Ceramic Isolator Ring
    # Beneath optical barrel:
    # 1. Knurled brass/bronze retention ring (z = 0.118 .. 0.124 m, radius 13 mm)
    create_cylinder_bmesh(bm, 0.013, 0.118, 0.124, (0.0, cyl_cy), segments=32, mat_idx=5)
    # 2. High-purity white ceramic electrical isolation ring (z = 0.112 .. 0.118 m, radius 11 mm)
    create_cylinder_bmesh(bm, 0.011, 0.112, 0.118, (0.0, cyl_cy), segments=32, mat_idx=4)

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
            ring.append(bm.verts.new((r_v * math.cos(a), cyl_cy + r_v * math.sin(a), z_v)))
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
    return mesh_c

print("Building linear rail mesh...")
m_rail = build_linear_guide_rail()
print(f"Rail: {len(m_rail.vertices)} verts, {len(m_rail.polygons)} polygons")

print("Building machined carriage mesh...")
m_c = build_machined_laser_carriage()
print(f"Carriage: {len(m_c.vertices)} verts, {len(m_c.polygons)} polygons")
print("All meshes constructed successfully!")
