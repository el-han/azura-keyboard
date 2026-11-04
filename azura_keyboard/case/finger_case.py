"""The finger keys: their layout and their part of the case.
"""
import math
from collections.abc import Iterable
from typing import Tuple

from build123d import Axis, Face, GeomType, Kind, Part, Polygon, Solid, Vector, Wire, extrude, offset

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
            (1.5, 3.75),
            (1.5, 3.5),
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


def _intersection(a0: Vector, a1: Vector, b0: Vector, b1: Vector) -> Vector:
    """Where the line through a0 and a1 crosses the line through b0 and b1, in top view."""
    da, db = a1 - a0, b1 - b0
    t = ((b0.X - a0.X) * db.Y - (b0.Y - a0.Y) * db.X) / (da.X * db.Y - da.Y * db.X)
    return Vector(a0.X + t * da.X, a0.Y + t * da.Y)


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
            straight_columns=self.dimensions.finger_straight_columns,
            straight_rows=self.dimensions.finger_straight_rows,
            enclose=[point for square in squares for point in square],
        ).fuse(*[Polygon(*square, align=None) for square in squares]).clean()
        for column in self.dimensions.finger_pcb_sides:
            away, toward = self._pcb_side(column, half)
            footprint = footprint.cut(away).fuse(toward).clean()
        # Fill the small notches between neighbouring squares
        smoothing = 3
        return offset(offset(footprint, smoothing, kind=Kind.ARC), -smoothing, kind=Kind.ARC)

    def _pcb_side(self, column: float, half: float) -> tuple[Face, Face]:
        """For the plate outline's edge at `column` (between two of its corners), what to take away from and add to the
        inside in top view, so that its wall runs straight along the PCBs beside it, `half` (half a PCB plus
        clearance) from their keys, between where that line meets the outline's neighbouring edges.

        The outline's edge itself is the key surface's grid line projected, which bends; the PCBs' squares stick out
        of it in places and stay inside it in others, which makes the wall wavy.
        """
        layout = self.layout
        corners = list(layout.outline_corners)
        i = next(i for i, (c0, c1) in enumerate(zip(corners, corners[1:] + corners[:1])) if c0[0] == c1[0] == column)
        (_, r0), (_, r1) = corners[i], corners[(i + 1) % len(corners)]
        before, after = corners[i - 1], corners[(i + 2) % len(corners)]
        xy = lambda c, r, point=(0, 0, 0): Vector(*layout.key_transform(c, r).apply(point)[:2])
        # The keys beside the edge, on the outline's inside: the column next to it that has keys along it
        low, high = min(r0, r1), max(r0, r1)
        beside = lambda c: [(kc, kr) for kc, kr in layout.generate_positions() if kc == c and kr + 0.5 > low and kr - 0.5 < high]
        keys, side = (beside(column + 0.5), -1) if beside(column + 0.5) else (beside(column - 0.5), 1)
        # Their squares' corners facing the edge, and the line along them, moved out to hold all of them
        points = [xy(kc, kr, (side * half, y, 0)) for kc, kr in keys for y in (half, -half)]
        along = (points[1] - points[0]).normalized()
        outward = Vector(-along.Y, along.X)
        inward_key = xy(*keys[0])
        outward = outward if (points[0] - inward_key).dot(outward) > 0 else -outward
        base = max(points, key=lambda p: p.dot(outward))
        # The outline's neighbouring edges, as their tangents at the corners
        def tangent(corner: tuple[float, float], toward: tuple[float, float]) -> tuple[Vector, Vector]:
            (c, r), (tc, tr) = corner, toward
            step = 0.01
            there = xy(c + step * (tc - c) / max(abs(tc - c), 1e-9), r + step * (tr - r) / max(abs(tr - r), 1e-9))
            return xy(c, r), (there - xy(c, r)).normalized()
        ends = []
        for corner, toward in ((corners[i], before), (corners[(i + 1) % len(corners)], after)):
            point, direction = tangent(corner, toward)
            ends.append((_intersection(base, base + along, point, point + direction), direction))
        (p0, d0), (p1, d1) = ends
        far = 5
        out0, out1 = (d if d.dot(outward) > 0 else -d for d in (d0, d1))
        away = Polygon(*[(p.X, p.Y) for p in (p0, p1, p1 + out1 * far, p0 + out0 * far)], align=None)
        toward = Polygon(*[(p.X, p.Y) for p in (p0, p1, p1 - outward * far, p0 - outward * far)], align=None)
        return away, toward

    def _outer_footprint(self, inner: Face) -> Face:
        """The inside's footprint grown by a wall, measured along the key surface instead of in top view: where the
        surface is steep (at the back of the key well), the same top-view offset would make a much thicker wall.

        Each straight edge of the inside's outline moves out by the top-view run that makes a wall along the key
        surface at the edge's middle (the slope changes a little along the long edges). The inside's arcs are the
        small fillets of its concave corners, which the offset closes up; the convex corners are filleted with the
        wall's run there.
        """
        d = self.dimensions
        key_surface = surface.torus(self.layout, 0).faces()[0]

        def run(point: Vector, outward: Vector) -> float:
            hits = key_surface.find_intersection_points(Axis((point.X, point.Y, 0), (0, 0, 1)))
            # The key surface is the lower one where a vertical line crosses the torus
            on_surface = min((hit for hit, _ in hits), key=lambda hit: hit.Z)
            normal = key_surface.normal_at(on_surface)
            slope = (normal.X * outward.X + normal.Y * outward.Y) / normal.Z
            return d.wall / math.sqrt(1 + slope * slope)

        face = inner.faces()[0]
        lines = []
        for edge in face.outer_wire().order_edges():
            if edge.geom_type != GeomType.LINE:
                continue
            a, b = edge.start_point(), edge.end_point()
            lines.append((Vector(a.X, a.Y), Vector(b.X, b.Y)))
        # Counter-clockwise, each line running on from the previous one
        for k in range(1, len(lines)):
            previous_end = lines[k - 1][1]
            a, b = lines[k]
            if (b - previous_end).length < (a - previous_end).length:
                lines[k] = (b, a)
        if sum(a.X * b.Y - b.X * a.Y for a, b in lines) < 0:
            lines = [(b, a) for a, b in reversed(lines)]

        moved = []
        for a, b in lines:
            along = (b - a).normalized()
            outward = Vector(along.Y, -along.X)
            middle = (a + b) * 0.5
            offset_by = run(middle, outward)
            moved.append((a + outward * offset_by, b + outward * offset_by, along, offset_by))

        corners, to_fillet = [], []
        for k, (a, b, along, offset_by) in enumerate(moved):
            next_a, next_b, next_along, next_offset = moved[(k + 1) % len(moved)]
            turn = math.atan2(along.cross(next_along).Z, along.dot(next_along))
            if abs(turn) < math.radians(1):
                # (nearly) in line: where they meet, in between
                corner = (b + next_a) * 0.5
            else:
                corner = _intersection(a, b, next_a, next_b)
            corners.append(corner)
            # Real corners get fillets; OCCT's fillet fails on the slight bends where the PCBs' squares step (a few
            # degrees), which stay as they are
            if turn > math.radians(10):
                to_fillet.append((k, corner, (offset_by + next_offset) / 2, turn))
        footprint = Face(Wire.make_polygon([Vector(p.X, p.Y, 0) for p in corners], close=True))
        # A fillet takes up radius * tan(turn / 2) of each edge; where the outline turns a little between short edges
        # (the PCBs' squares stepping), that limits it to a bit less than half of each neighbouring edge (OCCT fails
        # on exactly half)
        length = lambda k: (corners[(k + 1) % len(corners)] - corners[k]).length
        for k, corner, radius, turn in to_fillet:
            room = 0.45 * min(length(k - 1), length(k)) / math.tan(turn / 2)
            vertex = min(footprint.vertices(), key=lambda v: (v.center() - Vector(corner.X, corner.Y, 0)).length)
            footprint = footprint.fillet_2d(min(radius, room), [vertex])
        return footprint

    def shapes(self) -> tuple[Part, Part, Part, Face]:
        """The case as (plate, bottom outside, cavity, footprint in top view), without any holes.

        The top half is the key plate. The bottom half is a copy of it moved down along the surface normals,
        joined to the plate's rim by walls that also run along the normals, so the whole case follows the key
        surface.
        """
        layout, d = self.layout, self.dimensions
        inner_footprint = self._inner_footprint()
        footprint = self._outer_footprint(inner_footprint)

        # Everything is trimmed on the key plane and then thickened along the surface normals, so all edges follow
        # the normals and the two halves meet flush.
        plate = self._thicken_down(self._surface_face(footprint, 0), d.plate_thickness)
        plate_underside = surface.torus_face(plate, layout.row_radius + d.plate_thickness)

        # Below the plate down to the outside of the floor, hollowed out by the space inside the walls. The cavity
        # starts at the key plane, above the plate's underside, so the two never share a face.
        outer = self._thicken_down(plate_underside, d.cavity_depth + d.wall - d.plate_thickness)
        cavity = self._thicken_down(self._surface_face(inner_footprint, 0), d.cavity_depth)
        return plate, outer, cavity, footprint
