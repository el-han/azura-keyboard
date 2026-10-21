"""The doubly-curved key surface of a layout, as an exact torus.

`Layout.key_transform()` rotates each key about an X axis at `row_radius` and then about a Y axis at `column_radius`.
Every key position therefore lies on a torus whose axis is parallel to Y at height `column_radius`, with major
radius `column_radius - row_radius` and minor radius `row_radius`; the keys sit on the inside of its outer equator.
Offsetting the surface by `d` along the key normals gives the concentric torus with minor radius `row_radius + d`.

This only holds while the layout's `placement_adjust()` and `layout_place()` are the same for every key, which is
the case for `FingerWellLayout` but not for `ThumbWellLayout`.
"""
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


def outline(layout: Layout) -> Face:
    """The footprint of the layout's plate (from `Layout.plate_edge_nodes()`), projected onto the XY plane."""
    points = []
    for (column, row, *_) in layout.plate_edge_nodes():
        x, y, _ = layout.key_transform(column, row).apply((0, 0, 0))
        if not points or (abs(points[-1][0] - x) > 1e-6 or abs(points[-1][1] - y) > 1e-6):
            points.append((x, y))
    if points[0] == points[-1]:
        points.pop()
    return Polygon(*points, align=None)
