"""Keyswitch sockets and related shapes, ported from `spkb.keyswitch`.

All shapes are in the key's local frame: the top of the plate is at Z=0 and the switch points up (+Z).
"""
from build123d import Box, Part, Pos, Rot, Solid, Rectangle, Plane, loft

from spkb.keyswitch import Keyswitch


def _frustum_y(x0: float, z0: float, y0: float, x1: float, z1: float, y1: float) -> Solid:
    """A ruled solid between an X×Z rectangle at Y=y0 and another at Y=y1."""
    return loft([
        Plane.XZ.offset(-y0) * Rectangle(x0, z0),
        Plane.XZ.offset(-y1) * Rectangle(x1, z1),
    ], ruled=True)


def _frustum_z(sections: list[tuple[float, float, float]]) -> Solid:
    """A ruled solid through X×Y rectangles given as (width, length, z)."""
    return loft([Plane.XY.offset(z) * Rectangle(w, l) for (w, l, z) in sections], ruled=True)


def mounting_socket(k: Keyswitch, extra_depth: float = 0) -> Part:
    """The negative shape for mounting the switch, including notches for its clips."""
    # Extra height above the top of the plate to ensure subtraction doesn't leave stray faces.
    extra_height = 1
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


def plate(k: Keyswitch, extra_depth: float = 0) -> Part:
    """A segment of plate for mounting the switch (always plate-thickness deep; no screw support)."""
    size = k.plate_size()
    thickness = k.plate_thickness + extra_depth
    return Pos(0, 0, -thickness / 2) * Box(size.x, size.y, thickness) - mounting_socket(k, extra_depth=extra_depth + 1)


def switch(k: Keyswitch) -> Solid:
    """Approximation of the top half of an MX-style switch body (used as clearance above the plate)."""
    return _frustum_z([
        (k.switch_midline_width, k.switch_midline_length, 0),
        (k.switch_midline_width, k.switch_midline_length, 0.1),
        (k.switch_topline_width, k.switch_topline_length, k.switch_height_above_plate),
    ])


PCB_THICKNESS = 1.57
PCB_SIZE = 19
SPKB_KEYSWITCH_DEPTH = 5.08
"spkb.single_key_pcb positions the board using the MX depth regardless of the switch definition."


def single_key_board(extra_spacing: float = 0) -> Box:
    """Simplified single-key PCB (a rectangular prism), as `spkb.single_key_pcb.single_key_board(simple=True)`."""
    size = PCB_SIZE + extra_spacing * 2
    return Pos(0, 0, -(PCB_THICKNESS / 2 + SPKB_KEYSWITCH_DEPTH + extra_spacing / 2)) * Box(
        size, size, PCB_THICKNESS + extra_spacing
    )
