"""Kernel-independent rigid transforms.

`Transform` mirrors the chaining API of SolidPython2 shapes (`.translate()`, `.rotate()`, `.up()`, ...), so layout
code can build a placement once and apply it to any CAD backend.
"""
import math
from collections.abc import Sequence
from typing import Tuple, Union

Matrix = Tuple[Tuple[float, float, float, float], ...]
Vector = Tuple[float, float, float]

_IDENTITY: Matrix = (
    (1.0, 0.0, 0.0, 0.0),
    (0.0, 1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.0, 1.0),
)


def _multiply(a: Matrix, b: Matrix) -> Matrix:
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4))
        for i in range(4)
    )


def _rotation_about_axis(angle: float, axis: Sequence[float]) -> Matrix:
    """Right-handed rotation by `angle` degrees about `axis`, like OpenSCAD's `rotate(a, v)`."""
    x, y, z = axis
    length = math.sqrt(x * x + y * y + z * z)
    x, y, z = x / length, y / length, z / length
    c = math.cos(math.radians(angle))
    s = math.sin(math.radians(angle))
    t = 1 - c
    return (
        (t * x * x + c, t * x * y - s * z, t * x * z + s * y, 0.0),
        (t * x * y + s * z, t * y * y + c, t * y * z - s * x, 0.0),
        (t * x * z - s * y, t * y * z + s * x, t * z * z + c, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )


class Transform:
    """An immutable 4x4 affine transform.

    Each chained call applies its operation *after* the existing transform, just like chaining calls on a shape.
    """
    def __init__(self, matrix: Matrix = _IDENTITY):
        self.matrix = matrix

    def then(self, other: "Transform") -> "Transform":
        """Apply `other` after this transform."""
        return Transform(_multiply(other.matrix, self.matrix))

    def _then_matrix(self, matrix: Matrix) -> "Transform":
        return Transform(_multiply(matrix, self.matrix))

    def translate(self, x: Union[float, Sequence[float]], y: float = 0, z: float = 0) -> "Transform":
        if isinstance(x, Sequence):
            x, y, z = x
        return self._then_matrix((
            (1.0, 0.0, 0.0, x),
            (0.0, 1.0, 0.0, y),
            (0.0, 0.0, 1.0, z),
            (0.0, 0.0, 0.0, 1.0),
        ))

    def rotate(self, a: Union[float, Sequence[float]], v: Sequence[float] = (0, 0, 1)) -> "Transform":
        """Rotate by `a` degrees about axis `v`, or by Euler angles (X, then Y, then Z) if `a` is a sequence."""
        if isinstance(a, Sequence):
            ax, ay, az = a
            return self.rotate(ax, (1, 0, 0)).rotate(ay, (0, 1, 0)).rotate(az, (0, 0, 1))
        return self._then_matrix(_rotation_about_axis(a, v))

    def up(self, z: float) -> "Transform":
        return self.translate(0, 0, z)

    def down(self, z: float) -> "Transform":
        return self.translate(0, 0, -z)

    def apply(self, point: Sequence[float]) -> Vector:
        """Transform a point."""
        x, y, z = point
        m = self.matrix
        return (
            m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
            m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
            m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3],
        )

    def as_lists(self) -> list[list[float]]:
        return [list(row) for row in self.matrix]
