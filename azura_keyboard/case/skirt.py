"""The skirt under the finger case, which the keyboard stands on.
"""
import copy

from build123d import Compound, Face, Kind, Part, Pos, Rectangle, Until, Wire, extrude, offset

from ..geometry import surface
from ..geometry.key_layout import KeyLayout
from .dimensions import Dimensions


class Skirt:
    def __init__(self, layout: KeyLayout, dimensions: Dimensions):
        self.layout = layout
        self.dimensions = dimensions

    def underside_outline(self, finger_outer: Part) -> Face:
        """The finger case's underside projected straight down onto the table plane."""
        d = self.dimensions
        underside = surface.torus_face(
            copy.deepcopy(finger_outer), self.layout.row_radius + d.cavity_depth + d.wall
        )
        table = Rectangle(10 * d.max_height, 10 * d.max_height).faces()[0]  # the XY plane; moved to the table later
        projected = underside.outer_wire().project_to_shape(table, (0, 0, -1))
        # Joined end to end (the projected ends match to within the projection's tolerance)
        return Face(Wire.combine([edge for wire in projected for edge in wire.edges()], tol=1e-4)[0])

    def outline(self, finger_outer: Part) -> Face:
        """The skirt's outside in top view: the underside's projection, shrunk by `skirt_inset`."""
        return offset(self.underside_outline(finger_outer), -self.dimensions.skirt_inset, kind=Kind.ARC)

    def inside(self, finger_outer: Part) -> Face:
        """The skirt's inside in top view: the underside's projection, shrunk by `skirt_inset` and a wall (from the
        projection, not from the outside: offsetting that again gives curves OCCT's booleans fail on)."""
        d = self.dimensions
        return offset(self.underside_outline(finger_outer), -(d.skirt_inset + d.wall), kind=Kind.ARC)

    def skirt(self, finger_outer: Part) -> Part:
        """The skirt on its own: a wall a wall's thickness inside its outline, from the table up to the finger case's
        underside (the torus at the floor's underside), closed by a floor on the table."""
        d = self.dimensions
        ring = self.outline(finger_outer) - self.inside(finger_outer)
        # Extruded up until the finger case's underside: `Until.FIRST` extrudes against `dir`, here up, to the
        # farthest surface of the target there, which is the underside, the target's only face. (The whole torus as
        # target, or `Until.NEXT` up, ends up on the torus's far side.)
        # (from a copy: the extrusion's booleans alter the target, which shares its faces with the case's floors)
        underside_face = surface.torus_face(
            copy.deepcopy(finger_outer), self.layout.row_radius + d.cavity_depth + d.wall
        )
        wall = extrude(
            Pos(0, 0, d.table_z) * ring, until=Until.FIRST, target=Compound([underside_face]), dir=(0, 0, -1)
        )
        # Closed by a floor of `wall` on the table, within the wall's inside. (A floor over the whole outside would
        # share the wall's outside faces, and the fuse drops it.) Healed: the fuse leaves it invalid.
        floor = Pos(0, 0, d.table_z) * extrude(self.inside(finger_outer), d.wall, dir=(0, 0, 1))
        return (wall + floor).fix()
