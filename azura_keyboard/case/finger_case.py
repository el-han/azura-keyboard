"""The finger keys: their layout and their part of the case.
"""
import math
from collections.abc import Iterable
from typing import Tuple

from build123d import Face, Part, Polygon, Pos, Rot, Solid, extrude
from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
from OCP.BRepLib import BRepLib
from OCP.Geom2d import Geom2d_Line
from OCP.ShapeFix import ShapeFix_Face
from OCP.gp import gp_Dir2d, gp_Pnt2d

from ..components import key_pcb
from ..components.keyswitch import Keyswitch
from ..geometry import surface
from ..geometry.key_layout import KeyLayout
from ..geometry.transform import Transform
from .dimensions import Dimensions


class FingerLayout(KeyLayout):
    """The layout of the finger keys.
    """
    def __init__(self, columns: int = 6, rows: int = 5, keyswitch: Keyswitch = Keyswitch()):
        super(FingerLayout, self).__init__(columns=columns, rows=rows, keyswitch=keyswitch)

        self.placement_transform = (0, 0, 1.6 + 3.0 + 5.0 + 9.0)

        self.positions_to_skip = ((0, 4), (1, 4), (2, 4), (5, 4))
        "Grid positions without a key: the bottom row under the index and middle fingers, where the thumb goes"

        self.outline_corners = (
            (-0.5, -0.75),
            (-0.5, 3.75),
            (2.5, 3.75),
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
                if column <= 0:
                    row += 0.125
                if column == 2:
                    row += -0.25
                elif column == 4:
                    row += 0.25
                elif column >= 5:
                    row += 0.5
                positions.append((column, row))
        return positions

    def layout_place(self, transform: Transform) -> Transform:
        """Place the layout.

        :param transform: the placement so far
        """
        return transform \
            .up(self.plate_thickness) \
            .translate(self.placement_transform)


def _union_outline(polygon: list[tuple[float, float]], rectangles: list[tuple[float, float, float, float]]) -> list[tuple[float, float]]:
    """The outline of the union of a polygon with edges along u and v and some rectangles (u0, v0, u1, v1),
    counter-clockwise: built from the grid of all their coordinates, keeping the cells inside any of them."""
    us = sorted({p[0] for p in polygon} | {x for r in rectangles for x in (r[0], r[2])})
    vs = sorted({p[1] for p in polygon} | {y for r in rectangles for y in (r[1], r[3])})

    def in_polygon(u: float, v: float) -> bool:
        inside = False
        for (u0, v0), (u1, v1) in zip(polygon, polygon[1:] + polygon[:1]):
            if (v0 > v) != (v1 > v) and u < u0 + (v - v0) * (u1 - u0) / (v1 - v0):
                inside = not inside
        return inside

    def filled(i: int, j: int) -> bool:
        if not (0 <= i < len(us) - 1 and 0 <= j < len(vs) - 1):
            return False
        u, v = (us[i] + us[i + 1]) / 2, (vs[j] + vs[j + 1]) / 2
        return in_polygon(u, v) or any(r[0] <= u <= r[2] and r[1] <= v <= r[3] for r in rectangles)

    cells = {(i, j) for i in range(len(us) - 1) for j in range(len(vs) - 1) if filled(i, j)}
    # Boundary edges of the filled cells, each counter-clockwise around its cell, as grid index pairs
    edges = {}
    for i, j in cells:
        if (i, j - 1) not in cells:
            edges[(i, j)] = (i + 1, j)
        if (i + 1, j) not in cells:
            edges[(i + 1, j)] = (i + 1, j + 1)
        if (i, j + 1) not in cells:
            edges[(i + 1, j + 1)] = (i, j + 1)
        if (i - 1, j) not in cells:
            edges[(i, j + 1)] = (i, j)
    start = min(edges)
    loop, at = [start], edges[start]
    while at != start:
        loop.append(at)
        at = edges[at]
    return [(us[i], vs[j]) for i, j in loop]


def _without_jogs(points: list[tuple[float, float]], jog: float) -> list[tuple[float, float]]:
    """A counter-clockwise polygon with edges along u and v, without points in line with their neighbours and
    without steps shorter than `jog` between two edges running the same way (moved out to the outer one)."""
    points = list(points)
    changed = True
    while changed:
        changed = False
        n = len(points)
        for k in range(n):
            a, b, c = points[k - 1], points[k], points[(k + 1) % n]
            if (abs(a[0] - b[0]) < 1e-12 and abs(b[0] - c[0]) < 1e-12) or (abs(a[1] - b[1]) < 1e-12 and abs(b[1] - c[1]) < 1e-12):
                del points[k]
                changed = True
                break
        if changed:
            continue
        for k in range(n):
            # A short edge from b to c between edges a-b and c-d that run the same way: a jog
            a, b, c, d = points[k - 1], points[k], points[(k + 1) % n], points[(k + 2) % n]
            length = abs(c[0] - b[0]) + abs(c[1] - b[1])
            along_u = abs(a[1] - b[1]) < 1e-12 and abs(c[1] - d[1]) < 1e-12
            along_v = abs(a[0] - b[0]) < 1e-12 and abs(c[0] - d[0]) < 1e-12
            if length < jog and (along_u or along_v):
                # Counter-clockwise, the outside is to the right of the direction of travel
                if along_u:
                    going = 1 if b[0] > a[0] else -1
                    v = min(b[1], c[1]) if going > 0 else max(b[1], c[1])
                    points[k], points[(k + 1) % n] = (b[0], v), (c[0], v)
                    points[k - 1] = (a[0], v)
                    points[(k + 2) % n] = (d[0], v)
                else:
                    going = 1 if b[1] > a[1] else -1
                    u = max(b[0], c[0]) if going > 0 else min(b[0], c[0])
                    points[k], points[(k + 1) % n] = (u, b[1]), (u, c[1])
                    points[k - 1] = (u, a[1])
                    points[(k + 2) % n] = (u, d[1])
                changed = True
                break
    return points


class FingerCase:
    """The finger keys' part of the case, following the key surface."""
    def __init__(self, layout: FingerLayout, dimensions: Dimensions):
        self.layout = layout
        self.dimensions = dimensions

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

    def _key_surface(self):
        """The key plane's torus: its OCCT surface (for faces on it), its parameters (u, v) of a point, and the linear
        map from grid positions (column, row) to them. Columns run along its parallels (u, the angle around its
        axis), rows along its meridians (v, the angle around its tube), so the map is linear."""
        layout = self.layout
        torus = BRep_Tool.Surface_s(surface.torus(layout, 0).faces()[0].wrapped)
        # The torus's own frame (see `surface.torus()`): its axis along Z, its tube's center circle in the XY plane
        frame = (surface.surface_location(layout) * Pos(0, 0, layout.column_radius) * Rot(90, 0, 0)).inverse()
        major = layout.column_radius - layout.row_radius

        def parameters(point) -> tuple[float, float]:
            local = (frame * Pos(*point)).position
            u = math.atan2(local.Y, local.X) % (2 * math.pi)
            v = math.atan2(local.Z, math.hypot(local.X, local.Y) - major) % (2 * math.pi)
            # Unwrapped across the seam, within the face's parameter range (from pi on)
            return u, v + 2 * math.pi if v < math.pi else v

        at = lambda c, r: parameters(layout.key_transform(c, r).apply((0, 0, 0)))
        (u0, v0), (u1, _), (_, v1) = at(0, 0), at(1, 0), at(0, 1)
        return torus, (lambda c, r: (u0 + c * (u1 - u0), v0 + r * (v1 - v0))), parameters

    def _lengths(self, v: float) -> tuple[float, float]:
        """Length on the key plane per radian of u (along a parallel) and of v (along a meridian) at `v`: a
        parallel's radius, and the tube's."""
        layout = self.layout
        major, minor = layout.column_radius - layout.row_radius, layout.row_radius
        return major + minor * math.cos(v), minor

    def _inner_region(self) -> list[tuple[float, float]]:
        """The inside on the key surface, as a polygon in the torus's parameters (u, v) whose edges run along its
        parallels and meridians: the plate outline and every key's room for its PCB (the PCB plus clearance,
        projected onto the surface)."""
        _, uv, parameters = self._key_surface()
        layout, d = self.layout, self.dimensions
        half = key_pcb.PCB_SIZE / 2 + d.clearance
        rectangles = []
        for column, row in layout.generate_positions():
            # The PCB's room as a rectangle along parallels and meridians around the key, just enclosing the flat
            # square projected onto the surface (which comes out a little skewed)
            key = layout.key_transform(column, row)
            u, v = uv(column, row)
            corners = [parameters(key.apply((x, y, 0))) for x in (-half, half) for y in (-half, half)]
            du = max(abs(cu - u) for cu, _ in corners)
            dv = max(abs(cv - v) for _, cv in corners)
            rectangles.append((u - du, v - dv, u + du, v + dv))
        outline = [uv(c, r) for c, r in layout.outline_corners]
        points = _union_outline(outline, rectangles)
        # Where a PCB's room reaches past the plate outline by a hair, the outer of the two lines is the edge, all
        # along it, instead of a step of that hair
        jog = 0.02 * (uv(1, 1)[0] - uv(0, 0)[0])
        return _without_jogs(points, jog)

    def _outer_region(self, inner: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """The inside's region grown by a wall along the key surface. Each edge runs along a parallel or a meridian
        and moves out to the next one a wall away: along a meridian the distance between parallels is the same
        everywhere, along a parallel the distance between meridians shrinks toward the torus's axis, so those
        edges are a wall away at their middle."""
        d = self.dimensions
        n = len(inner)
        moved = []
        for k in range(n):
            (u0, v0), (u1, v1) = inner[k], inner[(k + 1) % n]
            if abs(v1 - v0) < 1e-12:
                # Along a parallel (constant v): move in v, a wall along the meridian
                step = d.wall / self._lengths(v0)[1]
                # Counter-clockwise: the outside is to the right of the edge's direction
                moved.append(("v", v0 - step if u1 > u0 else v0 + step))
            else:
                step = d.wall / self._lengths((v0 + v1) / 2)[0]
                moved.append(("u", u0 + step if v1 > v0 else u0 - step))
        # Each edge's strip out to its moved line, and a corner piece at each corner; their union with the inside is
        # the outside (short edges between near steps of the PCBs' rooms would turn over when moved on their own)
        scale = 1000
        rect = lambda u_a, v_a, u_b, v_b: Polygon(*[(x * scale, y * scale) for x, y in (
            (min(u_a, u_b), min(v_a, v_b)), (max(u_a, u_b), min(v_a, v_b)),
            (max(u_a, u_b), max(v_a, v_b)), (min(u_a, u_b), max(v_a, v_b)))], align=None)
        pieces = [Polygon(*[(u * scale, v * scale) for u, v in inner], align=None)]
        for k in range(n):
            (u0, v0), (u1, v1) = inner[k], inner[(k + 1) % n]
            kind, at = moved[k]
            pieces.append(rect(u0, v0, u1, at) if kind == "v" else rect(u0, v0, at, v1))
            # The corner at the edge's end, toward the next edge's moved line
            next_kind, next_at = moved[(k + 1) % n]
            if kind == "v":
                pieces.append(rect(u1, v1, next_at, at))
            else:
                pieces.append(rect(u1, v1, at, next_at))
        region = pieces[0].fuse(*pieces[1:]).clean()
        wire = max((f.outer_wire() for f in region.faces()), key=lambda w: Face(w).area)
        corners = [(e.start_point().X / scale, e.start_point().Y / scale) for e in wire.order_edges()]
        if sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(corners, corners[1:] + corners[:1])) < 0:
            corners.reverse()
        return _without_jogs(corners, 0)

    def _face_on_surface(self, region: list[tuple[float, float]]) -> Face:
        """The key plane's face bounded by a polygon in the torus's parameters."""
        torus, _, _ = self._key_surface()
        builder = BRepBuilderAPI_MakeWire()
        n = len(region)
        for k in range(n):
            (ua, va), (ub, vb) = region[k], region[(k + 1) % n]
            length = math.hypot(ub - ua, vb - va)
            line = Geom2d_Line(gp_Pnt2d(ua, va), gp_Dir2d(ub - ua, vb - va))
            builder.Add(BRepBuilderAPI_MakeEdge(line, torus, 0, length).Edge())
        wire = builder.Wire()
        BRepLib.BuildCurves3d_s(wire)
        face = Face(BRepBuilderAPI_MakeFace(torus, wire, True).Face())
        fixer = ShapeFix_Face(face.wrapped)
        fixer.Perform()
        return Face(fixer.Face())

    def _top_view(self, face: Face) -> Face:
        """A face's outline in top view (for prisms around the case; its edges are sampled)."""
        points = [face.outer_wire().position_at(i / 400) for i in range(400)]
        return Polygon(*[(p.X, p.Y) for p in points], align=None)

    def shapes(self) -> tuple[Part, Part, Part, Face]:
        """The case as (plate, bottom outside, cavity, footprint in top view), without any holes.

        The top half is the key plate. The bottom half is a copy of it moved down along the surface normals,
        joined to the plate's rim by walls that also run along the normals, so the whole case follows the key
        surface. All edges on the key surface run along its parallels and meridians.
        """
        layout, d = self.layout, self.dimensions
        inner = self._inner_region()
        inner_face = self._face_on_surface(inner)
        outer_face = self._face_on_surface(self._outer_region(inner))
        self.key_plane_face = outer_face

        # Everything is laid on the key plane and then thickened along the surface normals, so all edges follow the
        # normals and the two halves meet flush.
        plate = self._thicken_down(outer_face, d.plate_thickness)
        plate_underside = surface.torus_face(plate, layout.row_radius + d.plate_thickness)

        # Below the plate down to the outside of the floor, hollowed out by the space inside the walls. The cavity
        # starts at the key plane, above the plate's underside, so the two never share a face.
        outer = self._thicken_down(plate_underside, d.cavity_depth + d.wall - d.plate_thickness)
        cavity = self._thicken_down(inner_face, d.cavity_depth)
        return plate, outer, cavity, self._top_view(outer_face)
