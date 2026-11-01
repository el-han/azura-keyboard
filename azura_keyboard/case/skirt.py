"""The skirt under the finger case, which the keyboard stands on.
"""
import copy
import math

from build123d import Box, Face, Kind, Part, Polygon, Pos, Rot, Vector, extrude, offset

from ..geometry import surface
from ..geometry.key_layout import KeyLayout
from .dimensions import Dimensions


class Skirt:
    def __init__(self, layout: KeyLayout, dimensions: Dimensions):
        self.layout = layout
        self.dimensions = dimensions

    def outline(self, finger_outer: Part) -> Face:
        """The skirt's outside in top view: the finger case's underside's outline, shrunk by `skirt_inset`."""
        d = self.dimensions
        underside = surface.torus_face(finger_outer, self.layout.row_radius + d.cavity_depth + d.wall)
        outline = Polygon(
            *[(p.X, p.Y) for p in underside.outer_wire().positions([i / 400 for i in range(400)])], align=None
        )
        return offset(outline, -d.skirt_inset, kind=Kind.ARC)

    def beside(self, outline: Face) -> Part:
        """Everything on the +X side of the line along the skirt's outside toward -X (from its front corner to its
        back end)."""
        points = [v.center() for v in outline.vertices()]
        front = min(points, key=lambda p: p.X)
        back_y = max(p.Y for p in points)
        back = min((p for p in points if p.Y > back_y - 0.5), key=lambda p: p.X)
        along = (back - front).normalized()
        normal = Vector(along.Y, -along.X, 0)  # toward +X
        size = 4 * self.dimensions.max_height
        return Pos(front + normal * (size / 2)) * Rot(0, 0, math.degrees(math.atan2(normal.Y, normal.X))) * Box(
            size, size, size
        )

    def added_to(self, bottom: Part, finger_outer: Part) -> Part:
        """`bottom` with the skirt: a wall from the table up to the bottom half's underside, along the underside's
        outline in top view, shrunk by `skirt_inset`, closed by a floor on the table.
        """
        d = self.dimensions
        outside = self.outline(finger_outer)
        ring = outside - offset(outside, -d.wall, kind=Kind.ARC)
        # Up to `max_height`, which stays below the far side of the torus
        skirt = Pos(0, 0, d.table_z) * extrude(ring, d.max_height, dir=(0, 0, 1)) - copy.deepcopy(bottom)
        skirt -= surface.torus(self.layout, depth=d.cavity_depth + d.wall)
        # Closed at the bottom by a floor of `wall`, which stays out of the finger case's inside
        floor = Pos(0, 0, d.table_z) * extrude(outside, d.wall, dir=(0, 0, 1))
        floor -= surface.torus(self.layout, depth=d.cavity_depth)
        return (bottom + skirt + floor).fix()
