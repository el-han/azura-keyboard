"""The skirt under the finger case, which the keyboard stands on.
"""
import copy

from build123d import Compound, Edge, Face, Kind, Part, Pos, Rectangle, Until, Wire, extrude, offset
from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.Geom import Geom_OffsetCurve, Geom_TrimmedCurve
from OCP.GeomAbs import GeomAbs_C2
from OCP.GeomConvert import GeomConvert_ApproxCurve

from ..geometry import surface
from ..geometry.key_layout import KeyLayout
from .dimensions import Dimensions


def without_offset_curves(face: Face, tolerance: float = 1e-5) -> Face:
    """`face` with each edge on an offset curve replaced by a B-spline approximation: OCCT's STEP writer has no
    translation for offset curves and silently drops every edge on one, and with it the faces they bound."""

    def edge(original: Edge) -> Edge:
        curve, first, last = BRep_Tool.Curve_s(original.wrapped, 0.0, 1.0), *BRep_Tool.Range_s(original.wrapped)
        basis = curve.BasisCurve() if isinstance(curve, Geom_TrimmedCurve) else curve
        if not isinstance(basis, Geom_OffsetCurve):
            return original
        approximation = GeomConvert_ApproxCurve(Geom_TrimmedCurve(curve, first, last), tolerance, GeomAbs_C2, 100, 8)
        if not approximation.HasResult():
            raise ValueError("no B-spline approximation of an offset curve")
        spline = approximation.Curve()
        return Edge(BRepBuilderAPI_MakeEdge(spline, spline.FirstParameter(), spline.LastParameter()).Edge())

    def wire(original: Wire) -> Wire:
        # (joined end to end: the approximations' ends match the originals' to within the tolerance)
        return Wire.combine([edge(e) for e in original.edges()], tol=1e-4)[0]

    return Face(wire(face.outer_wire()), [wire(w) for w in face.inner_wires()])


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
        return without_offset_curves(
            offset(self.underside_outline(finger_outer), -self.dimensions.skirt_inset, kind=Kind.ARC).face()
        )

    def inside(self, finger_outer: Part) -> Face:
        """The skirt's inside in top view: the underside's projection, shrunk by `skirt_inset` and a wall (from the
        projection, not from the outside: offsetting that again gives curves OCCT's booleans fail on)."""
        d = self.dimensions
        return without_offset_curves(
            offset(self.underside_outline(finger_outer), -(d.skirt_inset + d.wall), kind=Kind.ARC).face()
        )

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
