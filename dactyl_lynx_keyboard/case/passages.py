"""The cable passage between the thumb case and the finger case, where the controller sits (in the skirt, at the back
left).
"""
import copy
import math

from build123d import Box, Part, Pos, Rot, Shape, Vector

from .dimensions import CaseDimensions


def _grid(shape: Shape, n: int) -> list[Vector]:
    """Points of an n×n×n grid over the shape's bounding box that lie inside it."""
    box = shape.bounding_box()
    steps = [i / (n - 1) for i in range(n)]
    points = [
        box.min + Vector(box.size.X * u, box.size.Y * v, box.size.Z * w) for u in steps for v in steps for w in steps
    ]
    return [point for point in points if shape.is_inside(point)]


def thumb_passage(
    finger_outer: Part,
    thumb_outer: Part,
    finger_cavity: Part,
    thumb_cavity: Part,
    dimensions: CaseDimensions,
    size: tuple[float, float] = (12, 5),
) -> Part:
    """A slot of the given width and height for the thumb keys' wires, through the middle of the wall the two cases
    share, lowered until it stays within their walls and insides (and clear of the plates above)."""
    _, p, q = copy.deepcopy(thumb_cavity).distance_to_with_closest_points(copy.deepcopy(finger_cavity))
    p, q = Vector(p), Vector(q)
    shared = (copy.deepcopy(thumb_outer) & copy.deepcopy(finger_outer)).bounding_box().center()
    across = Vector((q - p).X, (q - p).Y, 0).normalized()
    along = Vector(-across.Y, across.X, 0)
    middle = (p + q) / 2 + along * (shared - (p + q) / 2).dot(along)
    angle = math.degrees(math.atan2(across.Y, across.X))
    walls_and_insides = (finger_outer, thumb_outer, finger_cavity, thumb_cavity)
    for drop in [0.5 * i for i in range(21)]:
        # Wide side horizontal
        slot = Pos(middle - Vector(0, 0, drop)) * Rot(0, 0, angle) * Box(
            4 * dimensions.wall, size[0], size[1]
        )
        if all(any(shape.is_inside(point) for shape in walls_and_insides) for point in _grid(slot, 5)):
            return slot
    raise ValueError("No room for the thumb case's cable passage")
