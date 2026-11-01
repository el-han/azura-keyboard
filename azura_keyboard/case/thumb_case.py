"""The thumb keys: their layout and their part of the case.
"""
import math
from collections.abc import Iterable
from typing import Tuple

from build123d import Box, Cylinder, Part, Pos, Rot

from ..components import key_pcb
from ..components.keyswitch import Keyswitch
from ..geometry.key_layout import KeyLayout
from ..geometry.placement import to_location
from ..geometry.transform import Transform
from .dimensions import Dimensions


class ThumbLayout(KeyLayout):
    """The layout of the thumb keys.
    """
    def __init__(self, keyswitch: Keyswitch = Keyswitch(), keys: int = 5):
        super(ThumbLayout, self).__init__(keyswitch=keyswitch)

        self.keys = keys
        "Number of keys on the arc, from the one next to the finger case (column -1) outward"

        self.rad_per_col = 2 * math.pi / 8
        "Angle between neighbouring keys on the arc"
        self.offset_per_col = 14

        self.placement_transform = (-38, -49, 15)

    def column_angle(self, column: float) -> float:
        """Calculate the Y rotation angle for the given column.

        :param column: the row number to rotate for
        """
        return math.degrees(self.rad_per_col * column)

    def generate_positions(self) -> Iterable[Tuple[float, float]]:
        """Generate the list of locations within the layout.
        """
        return tuple((column, 0) for column in range(-1, self.keys - 1))

    def key_size(self, column: float, row: float) -> float:
        """The bottom key (column 0) is 1.25u wide."""
        return 1.25 if column == 0 else 1.0

    def extra_width(self, column: float, row: float) -> float:
        """How much wider than 1u the key at the given position is (mm)."""
        return (self.key_size(column, row) - 1) * self.unit_width

    def key_angle(self, column: float, row: float) -> float:
        """The angle of the key around the thumb arc (degrees); 0 is the bottom, positive angles go toward -X."""
        return self.column_angle(column)

    def flat_width(self, row: float = 0) -> float:
        """Width of the flat strip at the bottom of the arc (mm): the combined extra width of the keys sitting there."""
        return sum(
            self.extra_width(column, key_row)
            for (column, key_row) in self.generate_positions()
            if key_row == row and abs(self.key_angle(column, key_row)) < 1e-9
        )

    def side_shift(self, column: float, row: float) -> float:
        """X shift of the key's side of the arc: the arc is split at the bottom and pulled apart by the flat strip."""
        angle = self.key_angle(column, row)
        if abs(angle) < 1e-9:
            return 0
        return math.copysign(self.flat_width(row) / 2, -angle)

    def placement_adjust(self, column: float, row: float, transform: Transform) -> Transform:
        """Make room for wider keys at the bottom of the arc.

        Keys at the bottom of the circle sit centered on a flat strip as wide as their extra width; the two halves of
        the arc on either side are moved apart by that much.

        :param column: the column to place the key in
        :param row: the row to place the key in
        :param transform: the placement so far
        """
        return transform.translate((self.side_shift(column, row), 0, 0))

    def layout_place(self, transform: Transform) -> Transform:
        """Place the layout.

        :param transform: the placement so far
        """
        transform = transform.rotate(15, (0, 0, 1))
        transform = transform.translate(self.placement_transform)
        return transform


class ThumbCase:
    """The thumb keys' part of the case: an arc, with a hook to the bottom at its free end."""
    def __init__(self, layout: ThumbLayout, dimensions: Dimensions):
        self.layout = layout
        self.dimensions = dimensions

    def _arc(
        self,
        center_x: float,
        start_angle: float,
        end_angle: float,
        length: float,
        top_depth: float,
        bottom_depth: float,
    ) -> Part:
        """An arc of the case's cylinder between two depths below the key plane, in the layout's base frame.

        Angles are column angles (degrees): 0 is the bottom of the circle, positive angles go toward -X. The arc's
        ends are radial planes, so they follow the surface normals.
        """
        radius = self.layout.column_radius
        arc = end_angle - start_angle
        # A cylinder's arc starts on its local +X axis; after turning its axis onto Y, local angle a points along
        # (cos a, 0, sin a), and a column angle c along (-sin c, 0, -cos c), i.e. local angle -90 - c.
        # (align=None keeps the cylinder's axis at the origin; otherwise a partial cylinder is centered on its bounds.)
        tube = Pos(0, 0, -length / 2) * (
            Cylinder(radius + bottom_depth, length, arc_size=arc, align=None)
            - Cylinder(radius + top_depth, length, arc_size=arc, align=None)
        )
        return Pos(center_x, 0, radius) * Rot(90, 0, 0) * Rot(0, 0, -90 - end_angle) * tube

    def _band(
        self, top_depth: float, bottom_depth: float, length: float, inset: float = 0, longer: bool = True
    ) -> Part:
        """The key surface thickened between two depths along its normals, in the layout's base frame.

        The arc is split at the bottom of the circle (angle 0) and its halves are moved apart by the flat strip
        under the keys sitting there (see `ThumbLayout.placement_adjust()`). Each half reaches half a key
        spacing past its outermost key, less `inset` (mm, measured on the key plane). With `longer`, the free end
        reaches further, to take the hook there (see `hook()`).
        """
        layout = self.layout
        half_step = math.degrees(layout.rad_per_col) / 2 - math.degrees(inset / layout.column_radius)
        angles = [layout.key_angle(column, row) for (column, row) in layout.generate_positions()]
        flat = layout.flat_width()
        left_end = max(angles) + half_step  # toward -X
        if longer:
            extra = self.dimensions.thumb_cavity_extra + (0 if inset else self.dimensions.thumb_end_extra)
            left_end += math.degrees(extra / layout.column_radius)
        right_end = min(angles) - half_step  # toward +X

        pieces = []
        if left_end > 0:
            pieces.append(self._arc(-flat / 2, max(right_end, 0), left_end, length, top_depth, bottom_depth))
        if right_end < 0:
            pieces.append(self._arc(flat / 2, right_end, min(left_end, 0), length, top_depth, bottom_depth))
        if flat > 0:
            pieces.append(
                Pos(0, 0, -(top_depth + bottom_depth) / 2) * Box(flat, length, bottom_depth - top_depth)
            )
        return pieces[0].fuse(*pieces[1:]) if len(pieces) > 1 else pieces[0]

    @property
    def inner_length(self) -> float:
        """Length of the inside across the arc: a PCB plus clearance."""
        return key_pcb.PCB_SIZE + 2 * self.dimensions.clearance

    def _placed(self, band: Part) -> Part:
        """A shape from the layout's base frame, where it goes."""
        return to_location(self.layout.layout_place(Transform())) * band

    def floor_extension(self) -> Part:
        """The floor, reaching well past the case's back end (to be cut off at the skirt)."""
        d = self.dimensions
        e = 40
        length = self.inner_length + 2 * d.wall + e
        return self._placed(Pos(0, e / 2, 0) * self._band(d.cavity_depth, d.cavity_depth + d.wall, length, longer=False))

    def above(self, depth: float) -> Part:
        """Everything of the case (from almost its arc's axis) down to `depth` below its key plane."""
        length = 2 * (self.inner_length + 2 * self.dimensions.wall)
        return self._placed(self._band(1 - self.layout.column_radius, depth, length))

    def shapes(self) -> tuple[Part, Part, Part, Part]:
        """The case as (plate, bottom outside, cavity, everything above the plate's underside), built like
        `FingerCase.shapes()`, without any holes.

        The surface is made of cylinder arcs and a flat strip, whose normals are radial or vertical, so moving
        it along its normals just means larger radii and a lower strip.
        """
        d = self.dimensions
        # The case is as long as a PCB plus clearance and walls; along the arc, the walls sit inside the half key
        # spacing past the outermost keys, which leaves room for the PCBs.
        length = self.inner_length + 2 * d.wall
        return tuple(self._placed(band) for band in (
            self._band(0, d.plate_thickness, length),
            self._band(d.plate_thickness, d.cavity_depth + d.wall, length),
            self._band(-1, d.cavity_depth, self.inner_length, inset=d.wall),
            # Everything from (almost) the arc's axis down to the plate's underside
            self._band(1 - self.layout.column_radius, d.plate_thickness, length),
        ))

    def hook(self) -> tuple[Part, Part]:
        """The hook at the free end and the pocket for it in the end wall, as (hook, pocket).

        Inside the case, an arm stands on the floor, and from it a tongue points along the arc into the end wall. So the
        bottom can't open away from the top there; it is hung in first and swung shut. It needs no spring.
        """
        layout, d = self.layout, self.dimensions
        width, thickness, reach, arm = d.tongue
        gap = d.tongue_clearance
        degrees = lambda length: math.degrees(length / layout.column_radius)
        # Where the cavity ends, on the key plane
        wall = (
            max(layout.key_angle(column, row) for column, row in layout.generate_positions())
            + math.degrees(layout.rad_per_col) / 2
            + degrees(d.thumb_cavity_extra - d.wall)
        )
        # The tongue runs midway between the plate and the floor
        middle = (d.plate_thickness + d.cavity_depth) / 2
        tongue_top, tongue_bottom = middle - thickness / 2, middle + thickness / 2
        arm_end = wall - degrees(2 * gap)
        arm_start = arm_end - degrees(arm)

        def arc(start: float, stop: float, top: float, bottom: float, length: float = width) -> Part:
            return self._placed(self._arc(-layout.flat_width() / 2, start, stop, length, top, bottom))

        hook = (
            arc(arm_start, arm_end, tongue_top - gap, d.cavity_depth + 1)
            + arc(arm_start, wall + degrees(reach), tongue_top, tongue_bottom)
        )
        pocket = arc(wall - degrees(1), wall + degrees(reach + 2 * gap), tongue_top - gap, tongue_bottom + gap, width + 2 * gap)
        return hook.fix(), pocket
