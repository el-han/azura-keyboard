"""Keyswitch sockets and related shapes (originally ported from `spkb.keyswitch`).

All shapes are in the key's local frame: the top of the plate is at Z=0 and the switch points up (+Z).
"""
from functools import cache
from os.path import abspath, dirname, join

from build123d import Box, Compound, Part, Plane, Pos, Rectangle, Rot, Solid, import_step, loft

from ..layouts.keys import Keyswitch

MX_SWITCH_STEP = join(dirname(dirname(dirname(abspath(__file__)))), "resources", "SW_Cherry_MX_Plate.stp")
"Cherry MX plate-mount switch from https://github.com/kiswitch/kiswitch (MIT / CC-BY-SA 4.0)"
MX_SWITCH_STEP_PLATE_Z = 5.0
"Height of the plate's top surface in the STEP model's frame (whose origin is the bottom of the switch housing)"
MX_STEM_TOP = 10.44
"Height of the MX stem's top above the plate, at rest (measured from the STEP model)"
MX_TRAVEL = 4.0
"Total travel of an MX switch"

DSA_KEYCAP_DIR = join(dirname(dirname(dirname(abspath(__file__)))), "resources", "dsa-keycap")
"DSA keycaps from https://github.com/anhthang/dsa-keycap (MIT); modelled Y-up, bottom at Y=0, wide side along X"
DSA_KEYCAP_FILES = {
    1.0: "DSA 1u.step",
    1.25: "DSA 1.25u.step",
    1.5: "DSA 1.5u.step",
    1.75: "DSA 1.75u.step",
    2.0: "DSA 2u.step",
    2.25: "DSA 2.25u.step",
    2.75: "DSA 2.75u.step",
}
DSA_SOCKET_DEPTH = 4.7
"Depth of the keycap's stem socket above its bottom edge (measured from the STEP model)"


def _frustum_y(x0: float, z0: float, y0: float, x1: float, z1: float, y1: float) -> Solid:
    """A ruled solid between an X×Z rectangle at Y=y0 and another at Y=y1."""
    return loft([
        Plane.XZ.offset(-y0) * Rectangle(x0, z0),
        Plane.XZ.offset(-y1) * Rectangle(x1, z1),
    ], ruled=True)


def _frustum_z(sections: list[tuple[float, float, float]]) -> Solid:
    """A ruled solid through X×Y rectangles given as (width, length, z)."""
    return loft([Plane.XY.offset(z) * Rectangle(w, l) for (w, l, z) in sections], ruled=True)


def mounting_socket(k: Keyswitch, extra_depth: float = 0, extra_height: float = 1) -> Part:
    """The negative shape for mounting the switch, including notches for its clips.

    :param extra_depth: extra depth to add below the hole
    :param extra_height: how far the hole extends above the top of the plate, so subtraction doesn't leave stray faces
    """
    hole_height = k.keyswitch_depth + extra_height + extra_depth
    hole = Pos(0, 0, extra_height - hole_height / 2) * Box(k.keyswitch_width, k.keyswitch_length, hole_height)

    # Hull of the inner and outer notch boxes: the outer box, plus a taper toward the inner box's front face.
    y_edge = k.keyswitch_length / 2
    notch = (
        Pos(0, y_edge - k.notch_depth, 0) * Box(k.notch_width_outer, k.notch_depth * 2, k.notch_height_outer)
        + _frustum_y(k.notch_width_outer, k.notch_height_outer, y_edge,
                     k.notch_width, k.notch_height, y_edge + k.notch_depth)
    )
    notch = Pos(0, 0, -k.notch_plate_thickness - k.notch_height / 2) * notch

    return hole + notch + Rot(0, 0, 180) * notch


def switch(k: Keyswitch) -> Solid:
    """Approximation of the top half of an MX-style switch body (used as clearance above the plate)."""
    return _frustum_z([
        (k.switch_midline_width, k.switch_midline_length, 0),
        (k.switch_midline_width, k.switch_midline_length, k.switch_flange_height),
        (k.switch_topline_width, k.switch_topline_length, k.switch_height_above_plate),
    ])


PCB_THICKNESS = 1.57
PCB_SIZE = 19
PCB_TOP_BELOW_PLATE = 5.08
"Depth of the PCB's top below the plate's top: an MX switch housing ends 5 mm below the plate."


def single_key_board(extra_spacing: float = 0) -> Box:
    """Simplified single-key PCB (a rectangular prism)."""
    size = PCB_SIZE + extra_spacing * 2
    return Pos(0, 0, -(PCB_THICKNESS / 2 + PCB_TOP_BELOW_PLATE + extra_spacing / 2)) * Box(
        size, size, PCB_THICKNESS + extra_spacing
    )


@cache
def _mx_switch_step() -> Compound:
    return import_step(MX_SWITCH_STEP)


@cache
def _dsa_keycap_step(size: float) -> Compound:
    try:
        file_name = DSA_KEYCAP_FILES[size]
    except KeyError:
        raise ValueError(f"No DSA keycap model for {size}u keys") from None
    return import_step(join(DSA_KEYCAP_DIR, file_name))


def dsa_keycap_model(size: float = 1.0, pressed: bool = False) -> Compound:
    """A DSA keycap of the given width (in units) on an MX stem for collision checks (not printed), at rest or
    bottomed out. The wide side runs along X.
    """
    bottom = MX_STEM_TOP - DSA_SOCKET_DEPTH - (MX_TRAVEL if pressed else 0)
    return Pos(0, 0, bottom) * Rot(90, 0, 0) * _dsa_keycap_step(size)


def mx_switch_model() -> Compound:
    """A Cherry MX switch for collision checks (not printed), in the key's local frame."""
    return Pos(0, 0, -MX_SWITCH_STEP_PLATE_Z) * _mx_switch_step()
