"""The finger keys: their layout and their part of the case.
"""
import math
from collections.abc import Iterable
from typing import Tuple

from build123d import Face, Kind, Part, Polygon, Solid, extrude, offset

from ..components import key_pcb
from ..components.keyswitch import Keyswitch
from ..geometry import surface
from ..geometry.key_layout import KeyLayout
from ..geometry.transform import Transform
from .dimensions import CaseDimensions


class FingerLayout(KeyLayout):
    """The layout of the finger keys.
    """
    def __init__(self, columns: int = 6, rows: int = 5, keyswitch: Keyswitch = Keyswitch()):
        super(FingerLayout, self).__init__(columns=columns, rows=rows, keyswitch=keyswitch)

        self.placement_transform = (0, 0, 1.6 + 3.0 + 5.0 + 9.0)

        self.positions_to_skip = ((0, 4), (1, 4), (2, 4))
        "Grid positions without a key: the bottom row under the index and middle fingers, where the thumb goes"

        self.outline_corners = (
            (-0.5, -0.75),
            (-0.5, 3.5),
            (2.5, 3.5),
            (2.5, 4.75),
            (5.5, 4.75),
            (5.5, -0.75),
        )

    def row_angle(self, row: float) -> float:
        """Calculate the X rotation angle for the given row.

        :param row: the row number to rotate for
        """
        return math.degrees(self.rad_per_row * (2 - row))

    def column_angle(self, column: float) -> float:
        """Calculate the Y rotation angle for the given column.

        :param column: the row number to rotate for
        """
        return math.degrees(self.rad_per_col * (2.5 - column))

    def placement_adjust(self, column: float, row: float, transform: Transform) -> Transform:
        """Adjust the position of the given key/location in the layout.

        :param column: the column to place the key in
        :param row: the row to place the key in
        :param transform: the placement so far
        """
        transform = transform.down(self.row_radius)
        transform = transform.rotate(-self.row_angle(3), (1, 0, 0))
        transform = transform.up(self.row_radius)
        transform = transform.translate((0.0, -1*self.offset_per_row, 0.0))

        transform = transform.down(self.column_radius)
        transform = transform.rotate(-self.column_angle(4), (0, 1, 0))
        transform = transform.up(self.column_radius)
        transform = transform.translate((1.5*self.offset_per_col, 0.0, 0.0))

        return transform.translate((0.5*self.offset_per_col, 0.0, 0.0))

    def generate_positions(self) -> Iterable[Tuple[float, float]]:
        """Generate the list of locations within the layout, with the middle finger's column shifted up and the
        pinky's columns shifted down by a quarter key.
        """
        positions = []
        for column in range(self.columns):
            for row in range(self.rows):
                if (column, row) in self.positions_to_skip:
                    continue
                if column == 2:
                    row += -0.25
                elif column >= 4:
                    row += 0.25
                positions.append((column, row))
        return positions

    def layout_place(self, transform: Transform) -> Transform:
        """Place the layout.

        :param transform: the placement so far
        """
        return transform \
            .up(self.plate_thickness) \
            .translate(self.placement_transform)


class FingerCase:
    """The finger keys' part of the case, following the key surface."""
    def __init__(self, layout: FingerLayout, dimensions: CaseDimensions):
        self.layout = layout
        self.dimensions = dimensions
        self.straight_columns = (-0.5,)
        self.straight_rows = (-0.75,)
        "Edges that should be straight in top view (see `surface.outline()`)"

    def _surface_face(self, footprint: Face, depth: float) -> Face:
        """The key surface at `depth` below the key plane, trimmed by a vertical prism over `footprint`."""
        slab = extrude(footprint, self.dimensions.max_height) & (
            surface.torus(self.layout, depth=depth + 1) - surface.torus(self.layout, depth=depth)
        )
        return surface.torus_face(slab, self.layout.row_radius + depth)

    @staticmethod
    def _thicken_down(face: Face, amount: float) -> Solid:
        """Thicken a key surface face by `amount` along its normals, away from the keycaps."""
        pointing_up = face.normal_at(face.center()).Z > 0
        return Solid.thicken(face, -amount if pointing_up else amount)

    def _inner_footprint(self) -> Face:
        """The inside of the case in top view: the plate outline, grown to hold every key's PCB.

        The PCBs hang below the keys along the surface normals, just like the case walls, so their squares projected
        from the key plane are what has to fit.
        """
        layout = self.layout
        half = key_pcb.PCB_SIZE / 2 + self.dimensions.clearance
        # Counter-clockwise; the keys face up, so the projections stay counter-clockwise and fuse into one face.
        corners = [(-half, -half, 0), (half, -half, 0), (half, half, 0), (-half, half, 0)]
        squares = [
            [layout.key_transform(column, row).apply(corner)[:2] for corner in corners]
            for (column, row) in layout.generate_positions()
        ]
        # Straight edges are moved out far enough to hold the PCBs, instead of bulging around them.
        footprint = surface.outline(
            layout,
            straight_columns=self.straight_columns,
            straight_rows=self.straight_rows,
            enclose=[point for square in squares for point in square],
        ).fuse(*[Polygon(*square, align=None) for square in squares]).clean()
        # Fill the small notches between neighbouring squares
        smoothing = 3
        return offset(offset(footprint, smoothing, kind=Kind.ARC), -smoothing, kind=Kind.ARC)

    def shapes(self) -> tuple[Part, Part, Part, Face]:
        """The case as (plate, bottom outside, cavity, footprint in top view), without any holes.

        The top half is the key plate. The bottom half is a copy of it moved down along the surface normals,
        joined to the plate's rim by walls that also run along the normals, so the whole case follows the key
        surface.
        """
        layout, d = self.layout, self.dimensions
        inner_footprint = self._inner_footprint()
        footprint = offset(inner_footprint, d.wall, kind=Kind.ARC)

        # Everything is trimmed on the key plane and then thickened along the surface normals, so all edges follow
        # the normals and the two halves meet flush.
        plate = self._thicken_down(self._surface_face(footprint, 0), d.plate_thickness)
        plate_underside = surface.torus_face(plate, layout.row_radius + d.plate_thickness)

        # Below the plate down to the outside of the floor, hollowed out by the space inside the walls. The cavity
        # starts at the key plane, above the plate's underside, so the two never share a face.
        outer = self._thicken_down(plate_underside, d.cavity_depth + d.wall - d.plate_thickness)
        cavity = self._thicken_down(self._surface_face(inner_footprint, 0), d.cavity_depth)
        return plate, outer, cavity, footprint
