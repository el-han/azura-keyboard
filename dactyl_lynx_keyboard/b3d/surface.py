"""The doubly-curved key surface of a layout, as an exact torus.

`Layout.key_transform()` rotates each key about an X axis at `row_radius` and then about a Y axis at `column_radius`.
Every key position therefore lies on a torus whose axis is parallel to Y at height `column_radius`, with major
radius `column_radius - row_radius` and minor radius `row_radius`; the keys sit on the inside of its outer equator.
Offsetting the surface by `d` along the key normals gives the concentric torus with minor radius `row_radius + d`.

This only holds while the layout's `placement_adjust()` and `layout_place()` are the same for every key, which is
the case for `FingerWellLayout` but not for `ThumbWellLayout`.
"""
import math
from collections.abc import Sequence

from build123d import Face, Location, Polygon, Pos, Rot, Solid, Torus

from ..layouts.layout import Layout
from ..layouts.transform import Transform
from .placement import to_location


def surface_location(layout: Layout) -> Location:
    """The placement of the whole key surface (the parts of the key transform shared by all keys)."""
    return to_location(layout.layout_place(layout.placement_adjust(0, 0, Transform())))


def torus(layout: Layout, depth: float = 0) -> Solid:
    """The solid torus whose surface lies `depth` below the top of the switch plates.

    Everything inside it is above that surface (on the keycap side).
    """
    major_radius = layout.column_radius - layout.row_radius
    # Start the minor circle on the inner equator: by default OCCT puts the torus seam on the outer equator, right
    # along the bottom of the key well, where it makes fusing the walls to the plate fail.
    return surface_location(layout) * Pos(0, 0, layout.column_radius) * Rot(90, 0, 0) * Torus(
        major_radius, layout.row_radius + depth, minor_start_angle=180, minor_end_angle=540
    )


Point2D = tuple[float, float]


def _enclosing_line(points: Sequence[Point2D], enclose: Sequence[Point2D]) -> tuple[Point2D, Point2D]:
    """The chord from the first to the last point, moved outward (to its right) just enough to enclose all `points`
    and `enclose`."""
    (x0, y0), (x1, y1) = points[0], points[-1]
    length = math.hypot(x1 - x0, y1 - y0)
    nx, ny = (y1 - y0) / length, -(x1 - x0) / length
    shift = max((px - x0) * nx + (py - y0) * ny for (px, py) in [*points, *enclose])
    return (x0 + nx * shift, y0 + ny * shift), (x1 + nx * shift, y1 + ny * shift)


def _intersection(a: tuple[Point2D, Point2D], b: tuple[Point2D, Point2D]) -> Point2D:
    """Intersection of the (infinite) lines through two segments."""
    (x1, y1), (x2, y2) = a
    (x3, y3), (x4, y4) = b
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def outline(
    layout: Layout,
    straight_columns: Sequence[float] = (),
    straight_rows: Sequence[float] = (),
    enclose: Sequence[Point2D] = (),
    step: float = 0.25,
) -> Face:
    """The footprint of the layout's plate (`Layout.outline_corners`, edges along the key surface), projected onto
    the XY plane.

    :param straight_columns: edge columns (e.g. -0.5 for the left edge of column 0) whose boundary should be a straight
        line in top view instead of following the projected key surface
    :param straight_rows: likewise for edge rows (e.g. the top edge)
    :param enclose: points (XY) that the straightened edges must also enclose
    :param step: sampling distance along the edges, in key units
    """
    corners = list(layout.outline_corners)

    def xy(column: float, row: float) -> Point2D:
        return layout.key_transform(column, row).apply((0, 0, 0))[:2]

    edges: list[tuple[bool, list[Point2D]]] = []
    for (c0, r0), (c1, r1) in zip(corners, corners[1:] + corners[:1]):
        straight = (c0 == c1 and c0 in straight_columns) or (r0 == r1 and r0 in straight_rows)
        steps = max(1, math.ceil(max(abs(c1 - c0), abs(r1 - r0)) / step))
        samples = [xy(c0 + (c1 - c0) * i / steps, r0 + (r1 - r0) * i / steps) for i in range(steps + 1)]
        edges.append((straight, list(_enclosing_line(samples, enclose)) if straight else samples[:-1]))

    # Where two straight edges meet, the corner is where their lines cross.
    for i, (straight, points) in enumerate(edges):
        previous_straight, previous_points = edges[i - 1]
        if straight and previous_straight:
            corner = _intersection((previous_points[0], previous_points[1]), (points[0], points[1]))
            previous_points[1] = points[0] = corner

    points = [point for (_, edge_points) in edges for point in edge_points]
    # Drop consecutive duplicates (from shared corners)
    points = [p for i, p in enumerate(points) if math.dist(p, points[i - 1]) > 1e-9]
    return Polygon(*points, align=None)
