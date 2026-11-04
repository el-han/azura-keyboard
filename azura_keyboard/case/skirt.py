"""The skirt under the finger case, which the keyboard stands on.
"""
from build123d import Edge, Face, Kind, Part, Pos, Wire, extrude, offset
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.Geom import Geom_Plane
from OCP.GeomConvert import GeomConvert
from OCP.GeomProjLib import GeomProjLib
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

from ..geometry import surface
from ..geometry.key_layout import KeyLayout
from .dimensions import Dimensions


def _shrunk(face: Face, amount: float) -> Face:
    """A face shrunk by `amount` all round, its edges as plain B-splines (OCCT's offset gives offset curves)."""
    shrunk = offset(face, -amount, kind=Kind.ARC)
    edges = [
        Edge(BRepBuilderAPI_MakeEdge(GeomConvert.CurveToBSplineCurve_s(
            BRepAdaptor_Curve(e.wrapped).Curve().Curve()), e.param_at(0), e.param_at(1)).Edge())
        if e.geom_type.name == "OFFSET" else e
        for e in shrunk.faces()[0].outer_wire().order_edges()
    ]
    return Face(Wire.combine(edges, tol=1e-4)[0])


class Skirt:
    def __init__(self, layout: KeyLayout, dimensions: Dimensions):
        self.layout = layout
        self.dimensions = dimensions

    def underside_outline(self, finger_outer: Part) -> Face:
        """The finger case's underside projected straight down onto the table plane.

        The underside's edges run along the torus's parallels and meridians; each is projected as it is (a line,
        circle or ellipse arc), not sampled.
        """
        d = self.dimensions
        underside = surface.torus_face(finger_outer, self.layout.row_radius + d.cavity_depth + d.wall)
        table = Geom_Plane(gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)))
        down = lambda p: gp_Pnt(p.X, p.Y, 0)
        edges = []
        for edge in underside.outer_wire().order_edges():
            adaptor = BRepAdaptor_Curve(edge.wrapped)
            first, last = adaptor.FirstParameter(), adaptor.LastParameter()
            try:
                # (keeping the parametrization, so the edge's own range ends right below its ends)
                flat = GeomProjLib.ProjectOnPlane_s(adaptor.Curve().Curve(), table, gp_Dir(0, 0, 1), True)
                edges.append(Edge(BRepBuilderAPI_MakeEdge(flat, first, last).Edge()))
            except Exception:
                # A circle in an upright plane (a meridian seen from above) projects onto a line
                edges.append(Edge(BRepBuilderAPI_MakeEdge(down(edge.position_at(0)), down(edge.position_at(1))).Edge()))
        # Joined end to end (the projected ends match to within the curves' tolerance)
        return Face(Wire.combine(edges, tol=1e-4)[0])

    def outline(self, finger_outer: Part) -> Face:
        """The skirt's outside in top view: the underside's projection, shrunk by `skirt_inset`."""
        return _shrunk(self.underside_outline(finger_outer), self.dimensions.skirt_inset)

    def skirt(self, finger_outer: Part) -> Part:
        """The skirt on its own: a wall a wall's thickness inside its outline, from the table up to the finger case's
        underside (the torus at the floor's underside), closed by a floor on the table."""
        d = self.dimensions
        underside = self.underside_outline(finger_outer)
        outside = _shrunk(underside, d.skirt_inset)
        # The inside a wall's thickness further in, shrunk from the underside's projection too (offsetting the
        # outside again gives curves OCCT's booleans silently fail on)
        ring = outside - _shrunk(underside, d.skirt_inset + d.wall)
        # Up to the underside: a prism up to `max_height` (which stays below the far side of the torus), less the torus
        wall = Pos(0, 0, d.table_z) * extrude(ring, d.max_height, dir=(0, 0, 1))
        wall -= surface.torus(self.layout, depth=d.cavity_depth + d.wall)
        # Closed at the bottom by a floor of `wall`, which stays out of the finger case's inside
        floor = Pos(0, 0, d.table_z) * extrude(outside, d.wall, dir=(0, 0, 1))
        floor -= surface.torus(self.layout, depth=d.cavity_depth)
        return (wall + floor).fix()

    def added_to(self, bottom: Part, finger_outer: Part) -> Part:
        """`bottom` with the skirt (see `skirt()`)."""
        return (bottom + self.skirt(finger_outer)).fix()
