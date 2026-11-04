"""The thumb keys: their layout and their part of the case.
"""
import math
from collections.abc import Iterable
from typing import Tuple

from build123d import Box, Cylinder, Location, Part, Plane, Pos, Rot, Vector

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
        """Keys 0 (the bottom one) and 2 are 1.25u wide."""
        return 1.25 if column in (0, 2) else 1.0

    def extra_width(self, column: float, row: float) -> float:
        """How much wider than 1u the key at the given position is (mm)."""
        return (self.key_size(column, row) - 1) * self.unit_width

    def key_angle(self, column: float, row: float) -> float:
        """The angle of the key around the thumb arc (degrees); 0 is the bottom, positive angles go toward -X."""
        return self.column_angle(column)

    def wide_keys(self, row: float = 0) -> list[tuple[float, float]]:
        """The wider keys on the arc as (angle, extra width), by angle."""
        return sorted(
            (self.key_angle(column, key_row), self.extra_width(column, key_row))
            for (column, key_row) in self.generate_positions()
            if key_row == row and self.extra_width(column, key_row) > 0
        )

    @staticmethod
    def tangent(angle: float) -> tuple[float, float]:
        """The arc's direction toward larger angles at `angle`, as (x, z) in the layout's base frame."""
        a = math.radians(angle)
        return -math.cos(a), math.sin(a)

    def shift(self, angle: float, row: float = 0) -> tuple[float, float]:
        """How far the arc at `angle` is moved, as (x, z) in the layout's base frame, to make room for the wider keys.

        The arc is split at each wider key, and a straight strip as long as the key's extra width goes in along the
        arc's direction there; everything further from the bottom moves on by that much, the key itself by half. A
        strip at the bottom pushes both halves apart, half each way.
        """
        x = z = 0.0
        for at, extra in self.wide_keys(row):
            if abs(at) < 1e-9:
                share = 0 if abs(angle) < 1e-9 else math.copysign(0.5, angle)
            elif abs(angle - at) < 1e-9:
                share = math.copysign(0.5, at)
            elif (at > 0 and angle > at) or (at < 0 and angle < at):
                share = math.copysign(1, at)
            else:
                share = 0
            tx, tz = self.tangent(at)
            x, z = x + share * extra * tx, z + share * extra * tz
        return x, z

    def placement_adjust(self, column: float, row: float, transform: Transform) -> Transform:
        """Make room for wider keys: each sits centered on a straight strip of the arc as long as its extra width
        (see `shift()`).

        :param column: the column to place the key in
        :param row: the row to place the key in
        :param transform: the placement so far
        """
        x, z = self.shift(self.key_angle(column, row), row)
        return transform.translate((x, 0, z))

    def layout_place(self, transform: Transform) -> Transform:
        """Place the layout.

        :param transform: the placement so far
        """
        transform = transform.rotate(15, (0, 0, 1))
        transform = transform.translate(self.placement_transform)
        return transform


class ThumbCase:
    """The thumb keys' part of the case: an arc."""
    def __init__(self, layout: ThumbLayout, dimensions: Dimensions):
        self.layout = layout
        self.dimensions = dimensions

    def _arc(
        self,
        center: tuple[float, float],
        start_angle: float,
        end_angle: float,
        length: float,
        top_depth: float,
        bottom_depth: float,
    ) -> Part:
        """An arc of the case's cylinder between two depths below the key plane, in the layout's base frame.

        Angles are column angles (degrees): 0 is the bottom of the circle, positive angles go toward -X. The arc's
        ends are radial planes, so they follow the surface normals. `center` moves it, as (x, z) (see
        `ThumbLayout.shift()`).
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
        return Pos(center[0], 0, radius + center[1]) * Rot(90, 0, 0) * Rot(0, 0, -90 - end_angle) * tube

    def _band(
        self, top_depth: float, bottom_depth: float, length: float, inset: float = 0
    ) -> Part:
        """The key surface thickened between two depths along its normals, in the layout's base frame.

        The arc is split at each wider key and its pieces are moved apart by straight strips under them (see
        `ThumbLayout.shift()`). Each end reaches half a key spacing past its outermost key, less `inset` (mm,
        measured on the key plane).
        """
        layout = self.layout
        half_step = math.degrees(layout.rad_per_col) / 2 - math.degrees(inset / layout.column_radius)
        angles = [layout.key_angle(column, row) for (column, row) in layout.generate_positions()]
        left_end = max(angles) + half_step  # toward -X
        right_end = min(angles) - half_step  # toward +X

        wide = [(at, extra) for at, extra in layout.wide_keys() if right_end < at < left_end]
        breaks = [right_end] + [at for at, _ in wide] + [left_end]
        pieces = [
            self._arc(layout.shift((a + b) / 2), a, b, length, top_depth, bottom_depth)
            for a, b in zip(breaks, breaks[1:])
        ]
        radius, middle = layout.column_radius, (top_depth + bottom_depth) / 2
        for at, extra in wide:
            # The strip, centered where the key's middle sits, along the arc's direction there
            x, z = layout.shift(at)
            a = math.radians(at)
            pieces.append(
                Pos(x - (radius + middle) * math.sin(a), 0, z + radius - (radius + middle) * math.cos(a))
                * Rot(0, at, 0) * Box(extra, length, bottom_depth - top_depth)
            )
        return pieces[0].fuse(*pieces[1:]) if len(pieces) > 1 else pieces[0]

    @property
    def inner_length(self) -> float:
        """Length of the inside across the arc: a PCB plus clearance."""
        return key_pcb.PCB_SIZE + 2 * self.dimensions.clearance

    def _placed(self, band: Part) -> Part:
        """A shape from the layout's base frame, where it goes."""
        return to_location(self.layout.layout_place(Transform())) * band

    def above(self, depth: float) -> Part:
        """Everything of the case (from almost its arc's axis) down to `depth` below its key plane."""
        length = 2 * (self.inner_length + 2 * self.dimensions.wall)
        return self._placed(self._band(1 - self.layout.column_radius, depth, length))

    def inside_and_above(self) -> Part:
        """Everything above the inside of the case's walls: its inside, and the room above its keys up to (almost)
        the arc's axis."""
        d = self.dimensions
        return self._placed(self._band(1 - self.layout.column_radius, d.cavity_depth, self.inner_length, inset=d.wall))

    def between_sides(self) -> Part:
        """Everything between the planes of the outsides of the case's front and back walls."""
        d = self.dimensions
        size = 4000
        return self._placed(Box(size, self.inner_length + 2 * d.wall, size))

    def front_wall_slab(self) -> Part:
        """Everything between the planes of the outside and the inside of the case's front wall."""
        d = self.dimensions
        size = 4000
        front = -(self.inner_length + 2 * d.wall) / 2
        return self._placed(Pos(0, front + d.wall / 2, 0) * Box(size, d.wall, size))

    def inside_carried_on(self) -> Part:
        """The room inside the case carried on toward +X past its free end: everything between the planes of the
        insides of its front and back walls, below the plane of the inside of its free end's wall (on the keys' side
        of it: the end plane slopes down toward +X, so below it reaches on past the end) and outside the cylinder of
        its top, where the switches sit."""
        layout, d = self.layout, self.dimensions
        radius = layout.column_radius
        half_step = math.degrees(layout.rad_per_col) / 2 - math.degrees(d.wall / radius)
        end = min(layout.key_angle(column, row) for column, row in layout.generate_positions()) - half_step
        x, z = layout.shift(end + 1e-6)  # the arc piece the end is on
        axis = Vector(x, 0, radius + z)
        a = math.radians(end)
        size = 4000
        # A column angle's direction from the axis is (-sin a, 0, -cos a); toward the keys it turns along
        # (-cos a, 0, sin a)
        toward_keys = Vector(-math.cos(a), 0, math.sin(a))
        below_end = Location(Plane(origin=axis, z_dir=toward_keys)) * Pos(0, 0, size / 2) * Box(size, size, size)
        between_walls = Box(size, self.inner_length, size)
        # and outside the cylinder of the case's top (its key plane), carried on round the same axis
        top = Pos(axis) * Rot(90, 0, 0) * Cylinder(radius, size)
        return self._placed(between_walls & below_end - top)

    def back_wall(self) -> Part:
        """The case's back wall (toward the finger case), raised to (almost) the arc's axis: a flat slab across the
        arc, to be cut down to the finger case's key plane."""
        d = self.dimensions
        length = self.inner_length + 2 * d.wall
        return self._placed(Pos(0, (length - d.wall) / 2, 0) * self._band(1 - self.layout.column_radius, d.cavity_depth + d.wall, d.wall))

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
