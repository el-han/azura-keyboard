"""The layout of a thumb well.
"""
import math
from collections.abc import Iterable
from typing import Tuple

from .keys import Kailh, Keyswitch
from .layout import Layout
from .transform import Transform


class ThumbWellLayout(Layout):
    """The layout of a thumb well.
    """
    def __init__(self, columns: int = 3, rows: int = 3, keyswitch: Keyswitch = Kailh()):
        super(ThumbWellLayout, self).__init__(columns=columns, rows=rows, keyswitch=keyswitch)

        # Cupping amounts, in radians per row/column
        # self.rad_per_row = 2 * math.pi / 3
        self.rad_per_col = 2 * math.pi / 8

        # self.offset_per_row = self.keyswitch.plate_size().y
        # self.offset_per_row = 17.5
        # self.offset_per_col = self.keyswitch.plate_size().x
        self.offset_per_col = 14

        self.placement_transform = (-30, -45, 15)

    def column_angle(self, column: float) -> float:
        """Calculate the Y rotation angle for the given column.

        :param column: the row number to rotate for
        """
        return math.degrees(self.rad_per_col * (2 - column))

    def generate_positions(self) -> Iterable[Tuple[float, float]]:
        """Generate the list of locations within the layout.
        """
        return (
            # (column, row)
            (-1, 0),
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 0),
        )

    def key_size(self, column: float, row: float) -> float:
        """The bottom key (column 2) is 1.25u wide."""
        return 1.25 if column == 2 else 1.0

    def extra_width(self, column: float, row: float) -> float:
        """How much wider than 1u the key at the given position is (mm)."""
        return (self.key_size(column, row) - 1) * self.unit_width

    def placement_adjust(self, column: float, row: float, transform: Transform) -> Transform:
        """Make room for wider keys at the bottom of the arc.

        Wider keys sit on a flat strip at the bottom of the circle: each one shifts itself by half its extra width, and
        every key after it in the row by its full extra width.

        :param column: the column to place the key in
        :param row: the row to place the key in
        :param transform: the placement so far
        """
        shift = self.extra_width(column, row) / 2 + sum(
            self.extra_width(other_column, other_row)
            for (other_column, other_row) in self.generate_positions()
            if other_row == row and other_column < column
        )
        return transform.translate((shift, 0, 0))

    def layout_place(self, transform: Transform) -> Transform:
        """Place the layout.

        :param transform: the placement so far
        """
        # transform = transform.up(self.row_radius)
        # transform = transform.rotate(90-self.row_angle(0), (1, 0, 0))
        # transform = transform.rotate(self.column_angle(0), (0, 0, 1))
        transform = transform.rotate(15, (0, 0, 1))
        transform = transform.translate(self.placement_transform)
        return transform
