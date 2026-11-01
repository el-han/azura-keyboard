"""Placing shapes on the keys of a layout.
"""
import copy
from collections.abc import Iterable
from typing import Callable, Optional

from build123d import Compound, Location, Part, Shape
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


def _instance(shape: Shape, location: Location) -> Shape:
    """A copy of `shape` at `location`, sharing its geometry; models with children get copies of each child."""
    if shape.children:
        return Compound(label=shape.label, children=[_instance(child, location) for child in shape.children])
    instance = copy.copy(shape)
    instance.location = location * shape.location
    return instance


def mirrored(location: Location) -> Location:
    """The location mirrored across the YZ plane, for an unmirrored part: its position and orientation are mirrored
    (X turned around), but it stays a rotation, so the part itself keeps its handedness."""
    trsf = location.wrapped.Transformation()
    sign = (-1, 1, 1, 1)  # X turned around; the last column is the translation
    values = [sign[i] * sign[j] * trsf.Value(i + 1, j + 1) for i in range(3) for j in range(4)]
    mirrored_trsf = gp_Trsf()
    mirrored_trsf.SetValues(*values)
    return Location(mirrored_trsf)


def place_instances(
    layout: KeyLayout,
    shape: Shape,
    name: str,
    positions: Optional[Iterable[tuple[float, float]]] = None,
    place: Callable[[Location], Location] = lambda location: location,
) -> list[Shape]:
    """Place an instance of `shape` at every key position (or the given ones), sharing its geometry; `place` turns
    a key's location into the instance's (e.g. mirrored for the left half).

    Exported as children of an assembly, the geometry is written to STEP only once. Each instance is labelled
    "<name> c<column> r<row>".
    """
    instances = []
    for (column, row) in layout.generate_positions() if positions is None else positions:
        location = key_location(layout, column, row)
        instance = _instance(shape, place(location))
        instance.label = f"{name} c{column:g} r{row:g}"
        instances.append(instance)
    return instances


def place_all(layout: KeyLayout, shape: Part) -> list[Part]:
    """Place a copy of `shape` at every key position of the layout."""
    return [key_location(layout, column, row) * shape for (column, row) in layout.generate_positions()]
