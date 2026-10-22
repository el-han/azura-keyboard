"""Keyswitch sockets and related shapes, ported from `spkb.keyswitch`.

All shapes are in the key's local frame: the top of the plate is at Z=0 and the switch points up (+Z).
"""
from build123d import Box, Cylinder, Part, Plane, Pos, Rectangle, Rot, Solid, loft

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


def mx_switch_model(k: Keyswitch) -> Part:
    """A simplified Cherry MX switch for collision checks (not printed).

    Dimensions from the Cherry MX datasheet: the top of the plate is at Z=0, the bottom housing ends 5 mm below it,
    and the pins stick out another 3.3 mm.
    """
    bottom_housing_depth = 5
    stem_height = 3.6
    pin_length = 3.3
    bottom_z = -bottom_housing_depth
    return (
        switch(k)
        # Stem, at rest
        + Pos(0, 0, k.switch_height_above_plate + stem_height / 2) * Box(7.2, 5.5, stem_height)
        # Bottom housing, a hair smaller than the plate hole so it doesn't touch the hole's walls
        + Pos(0, 0, bottom_z / 2) * Box(k.keyswitch_width - 0.1, k.keyswitch_length - 0.1, bottom_housing_depth)
        # Center post and the two contact pins
        + Pos(0, 0, bottom_z - pin_length / 2) * Cylinder(2, pin_length)
        + Pos(-3.81, 2.54, bottom_z - pin_length / 2) * Cylinder(0.75, pin_length)
        + Pos(2.54, 5.08, bottom_z - pin_length / 2) * Cylinder(0.75, pin_length)
    )
