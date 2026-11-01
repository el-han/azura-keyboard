"""Cherry MX-style keyswitches: their measurements, the sockets for them, and models of them (originally ported from
`spkb.keyswitch`).

All shapes are in the key's local frame: the top of the plate is at Z=0 and the switch points up (+Z).
"""
from functools import cache
from pathlib import Path

from build123d import Box, Compound, Part, Plane, Pos, Rectangle, Rot, Solid, loft

from ..geometry.step import import_step_colored, transformed

class Keyswitch:
    """All measurements related to Cherry MX-style switches.

    The top of the plate is at Z=0.
    """
    keyswitch_length: float = 14.0
    "The length (front to back) of the keyswitch mounting hole"
    keyswitch_width: float = 14.0
    "The width (left to right) of the keyswitch mounting hole"
    keyswitch_depth: float = 5.08
    "From the base of the switch to the mounting plate face"

    plate_thickness: float = 3
    "The thickness of the plate above the origin"
    notch_plate_thickness: float = 1.3
    "The thickness of the plate at the notches where the switch's clips are located"
    notch_width: float = 5
    "The width of the notch for the switch's clips at the deepest part of the notch"
    notch_width_outer: float = 6
    "The width of the notch for the switch's clips at the edge of the mounting hole"
    notch_depth: float = 0.5
    "The depth of the notch for the switch's clips"
    notch_height: float = 8
    "The height of the notch for the switch's clips at the deepest part of the notch"
    notch_height_outer: float = 9
    "The height of the notch for the switch's clips at the edge of the mounting hole"

    switch_midline_width: float = 15.7
    "The width (left to right) of the switch's housing flange on top of the plate, plus a little clearance"
    switch_midline_length: float = 15.7
    "The length (front to back) of the switch's housing flange on top of the plate, plus a little clearance"
    switch_flange_height: float = 1.0
    "How far the switch's housing flange rises straight up from the plate before it tapers"
    switch_topline_width: float = 10.5
    "The width (left to right) of the switch at its top"
    switch_topline_length: float = 10.5
    "The length (front to back) of the switch at its top"
    switch_height_above_plate: float = 6.2
    "The height of the switch body above the top of the plate"


MX_SWITCH_STEP = Path(__file__).resolve().parents[2] / "resources" / "SW_Cherry_MX_Plate.stp"
"Cherry MX plate-mount switch from https://github.com/kiswitch/kiswitch (MIT / CC-BY-SA 4.0)"
MX_SWITCH_STEP_PLATE_Z = 5.0
"Height of the plate's top surface in the STEP model's frame (whose origin is the bottom of the switch housing)"
MX_STEM_TOP = 10.44
"Height of the MX stem's top above the plate, at rest (measured from the STEP model)"
MX_TRAVEL = 4.0
"Total travel of an MX switch"


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


@cache
def _mx_switch_step() -> Compound:
    return import_step_colored(MX_SWITCH_STEP, label="Cherry MX")


def mx_switch_model() -> Compound:
    """A Cherry MX switch for collision checks (not printed), in the key's local frame."""
    return transformed(_mx_switch_step(), Pos(0, 0, -MX_SWITCH_STEP_PLATE_Z))


def mx_switch_envelope() -> Part:
    """A few boxes around a Cherry MX switch, for quick collision checks (not printed), in the key's local frame:
    the top housing and stem above the plate, the bottom housing in the plate's 14 mm hole, and the pins below.
    """
    top_housing = Pos(0, 0, 4.65 / 2) * Box(15.6, 15.6, 4.65) + Pos(0, 0, 6.25 / 2) * Box(14.7, 14.7, 6.25)
    stem = Pos(0, 0, MX_STEM_TOP / 2) * Box(8.9, 5.7, MX_STEM_TOP)
    bottom_housing = Pos(0, 0, -7.46 / 2) * Box(14, 14, 7.46)
    pins = Pos(0, 3.97, -7.81) * Box(9.8, 3.16, 0.7)
    return top_housing + stem + bottom_housing + pins
