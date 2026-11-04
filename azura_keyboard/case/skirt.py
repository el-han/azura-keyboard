"""The skirt under the finger case, which the keyboard stands on.
"""
import copy

from build123d import Face, Kind, Part, Polygon, Pos, extrude, offset

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
