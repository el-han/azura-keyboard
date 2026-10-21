"""Assembly of the keyboard parts with build123d.
"""
import math

from build123d import Box, Compound, Cylinder, Part, Plane, Polygon, Pos, Rot, extrude

from ..layouts.finger_well import FingerWellLayout
from ..layouts.keys import Kailh
from ..layouts.layout import Layout
from ..layouts.thumb_well import ThumbWellLayout
from . import keyswitch, surface
from ..layouts.transform import Transform
from .placement import key_location, to_location


def place_all(layout: Layout, shape: Part) -> list[Part]:
    """Place a copy of `shape` at every key position of the layout."""
    return [key_location(layout, column, row) * shape for (column, row) in layout.generate_positions()]


class KeyboardAssembly:
    def __init__(self, columns: int = 6, rows: int = 5):
        k = Kailh()
        self.finger_layout = FingerWellLayout(columns=columns, rows=rows, use_1_5u_keys=False, keyswitch=k)
        self.thumb_layout = ThumbWellLayout(keyswitch=k)

        self.plate_thickness = self.finger_layout.web_thickness
        self.max_height = 120
        "Upper bound for the height of any part (must stay below the far side of the key surface torus)"
        self.finger_straight_columns = (-0.5,)
        "Edges of the finger well that should be straight in top view (see `surface.outline()`)"
        "Upper bound for the height of any part (must stay below the far side of the key surface torus)"

    def switch_plates(self) -> Compound:
        """All switch plates of the finger and thumb wells, without any web between them."""
        plate = keyswitch.plate(self.finger_layout.keyswitch)
        return Compound(
            place_all(self.finger_layout, plate) + place_all(self.thumb_layout, plate)
        )

    def finger_part(self) -> Part:
        """The finger well: plate on the key surface with switch sockets."""
        layout = self.finger_layout
        k = layout.keyswitch
        footprint = surface.outline(layout, straight_columns=self.finger_straight_columns)

        plate = (
            extrude(footprint, self.max_height)
            & (surface.torus(layout, depth=self.plate_thickness) - surface.torus(layout))
        )
        # Drop slivers from where the torus turns over beyond the footprint; keep the key surface itself.
        shape = max(plate.solids(), key=lambda solid: solid.volume)

        # Extend the hole well beyond both sides of the shell: when it ends close to the curved surfaces, OCCT
        # sometimes keeps the cut-out piece as a separate solid.
        shape -= place_all(layout, keyswitch.mounting_socket(k, extra_depth=1, extra_height=3))
        shape -= place_all(layout, keyswitch.switch(k))
        shape -= place_all(layout, keyswitch.single_key_board(extra_spacing=0.02))
        return shape

    def _thumb_arc(self, center_x: float, start_angle: float, end_angle: float, length: float) -> Part:
        """A plate-thick arc of the thumb well's cylinder, in the layout's base frame.

        Angles are column angles (degrees): 0 is the bottom of the circle, positive angles go toward -X.
        """
        layout = self.thumb_layout
        radius = layout.column_radius
        tube = Pos(center_x, 0, radius) * Rot(90, 0, 0) * (
            Cylinder(radius + self.plate_thickness, length) - Cylinder(radius, length)
        )
        steps = max(2, math.ceil(abs(end_angle - start_angle) / 15))
        far = 3 * radius
        rays = [
            (center_x - far * math.sin(math.radians(a)), radius - far * math.cos(math.radians(a)))
            for a in (start_angle + (end_angle - start_angle) * i / steps for i in range(steps + 1))
        ]
        sector = extrude(Plane.XZ * Polygon((center_x, radius), *rays, align=None), length, both=True)
        return tube & sector

    def thumb_part(self) -> Part:
        """The thumb well: a cylindrical arc of keys, split at the bottom by a flat strip where the right part of the
        arc is shifted outward.
        """
        layout = self.thumb_layout
        k = layout.keyswitch
        columns = [column for (column, _) in layout.generate_positions()]
        length = layout.offset_per_row

        # The bottom key (column 2) sits on the flat strip; columns past it are shifted by its width.
        shift = layout.placement_adjust(3, 0, Transform()).apply((0, 0, 0))[0]
        left = self._thumb_arc(0, 0, layout.column_angle(min(columns) - 0.5), length)
        right = self._thumb_arc(shift, layout.column_angle(max(columns) + 0.5), 0, length)
        flat = Pos(shift / 2, 0, -self.plate_thickness / 2) * Box(shift, length, self.plate_thickness)

        shape = to_location(layout.layout_place(Transform())) * (left + right + flat)

        shape -= place_all(layout, keyswitch.mounting_socket(k, extra_depth=1, extra_height=3))
        shape -= place_all(layout, keyswitch.switch(k))
        shape -= place_all(layout, keyswitch.single_key_board(extra_spacing=0.02))
        return shape
