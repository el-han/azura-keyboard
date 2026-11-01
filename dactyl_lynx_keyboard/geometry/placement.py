"""Bridge between the backend-independent layouts and build123d.
"""
from build123d import Location
from OCP.gp import gp_Trsf

from .key_layout import KeyLayout
from .transform import Transform


def to_location(transform: Transform) -> Location:
    """Convert a rigid `Transform` into a build123d `Location`."""
    m = transform.matrix
    trsf = gp_Trsf()
    trsf.SetValues(*m[0], *m[1], *m[2])
    return Location(trsf)


def key_location(layout: KeyLayout, column: float, row: float) -> Location:
    """Return the location of the given key position in the layout."""
    return to_location(layout.key_transform(column, row))
