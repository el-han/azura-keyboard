"""The doubly-curved key surface of a layout, as an exact torus.

`Layout.key_transform()` rotates each key about an X axis at `row_radius` and then about a Y axis at `column_radius`.
Every key position therefore lies on a torus whose axis is parallel to Y at height `column_radius`, with major
radius `column_radius - row_radius` and minor radius `row_radius`; the keys sit on the inside of its outer equator.
Offsetting the surface by `d` along the key normals gives the concentric torus with minor radius `row_radius + d`.

This only holds while the layout's `placement_adjust()` and `layout_place()` are the same for every key, which is
the case for `FingerWellLayout` but not for `ThumbWellLayout`.
"""
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


def _straighten(
    points: list[tuple[float, float]], run: list[int], enclose: Sequence[tuple[float, float]] = ()
) -> None:
    """Replace the points at the (cyclically consecutive) indices `run` with a straight segment.

    The segment is parallel to the chord between the run's end points, moved outward just enough to enclose all of
    them and the points in `enclose`, so the footprint never shrinks.
    """
    (x0, y0), (x1, y1) = points[run[0]], points[run[-1]]
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    # Outward normal of a counter-clockwise polygon is to the right of the direction of travel.
    nx, ny = (y1 - y0) / length, -(x1 - x0) / length
    if _signed_area(points) < 0:
        nx, ny = -nx, -ny
    shift = max((px - x0) * nx + (py - y0) * ny for (px, py) in [points[i] for i in run] + list(enclose))
    start = (x0 + nx * shift, y0 + ny * shift)
    end = (x1 + nx * shift, y1 + ny * shift)
    for i in run[1:-1]:
        points[i] = None  # type: ignore[call-overload]
    points[run[0]], points[run[-1]] = start, end


def _signed_area(points: list[tuple[float, float]]) -> float:
    points = [p for p in points if p is not None]  # skip points already removed by `_straighten()`
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1])) / 2


def outline(
    layout: Layout,
    straight_columns: Sequence[float] = (),
    straight_rows: Sequence[float] = (),
    enclose: Sequence[tuple[float, float]] = (),
) -> Face:
    """The footprint of the layout's plate (from `Layout.plate_edge_nodes()`), projected onto the XY plane.

    :param straight_columns: edge columns (e.g. -0.5 for the left edge of column 0) whose boundary should be a straight
        line instead of following the projected key surface
    :param straight_rows: likewise for edge rows (e.g. the top edge)
    :param enclose: points (XY) that the straightened edges must also enclose
    """
    nodes: list[tuple[float, float]] = []
    points: list[tuple[float, float]] = []
    for (column, row, *_) in layout.plate_edge_nodes():
        x, y, _ = layout.key_transform(column, row).apply((0, 0, 0))
        if (column, row) not in nodes:
            nodes.append((column, row))
            points.append((x, y))

    edges = [(0, value) for value in straight_columns] + [(1, value) for value in straight_rows]
    for (axis, value) in edges:
        on_edge = [i for i, node in enumerate(nodes) if node[axis] == value and points[i] is not None]
        # Rotate so the run is consecutive even if it wraps around the start of the loop.
        start = next(i for i in on_edge if (i - 1) % len(nodes) not in on_edge)
        run = [(start + j) % len(nodes) for j in range(len(on_edge))]
        assert set(run) == set(on_edge), f"edge {'column' if axis == 0 else 'row'} {value} is not one consecutive run"
        _straighten(points, run, enclose)

    return Polygon(*(p for p in points if p is not None), align=None)
