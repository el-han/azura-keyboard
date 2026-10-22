"""Keyswitch measurements (formerly from `spkb.keyswitch`).
"""
from typing import NamedTuple


class Offset2D(NamedTuple):
    x: float
    y: float


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

    wall_thickness: float = 1.5
    "The thickness of the mounting hole walls"

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

    def plate_size(self) -> Offset2D:
        """The size of the plate segment around one switch."""
        return Offset2D(self.keyswitch_width + self.wall_thickness * 2, self.keyswitch_length + self.wall_thickness * 2)


class Kailh(Keyswitch):
    """MX-style switches as used here; the plate-to-base depth doubles as the plate thickness."""
    keyswitch_depth: float = 3
    "From the base of the switch to the mounting plate face"
