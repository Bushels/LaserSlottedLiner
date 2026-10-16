"""Test script to build Look-Dev v6 and render a high-quality test frame with Cycles locally.
"""
import sys
import math
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

# Import the base script module
sys.path.insert(0, r"c:\Users\kyle\MPS\slotted-liner\marketing\blender\scripts")
import build_laser_teaser_v1 as bld

print("Module loaded successfully.")
