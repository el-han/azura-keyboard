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
        return math.degrees(self.rad_per_col * column)

    def generate_positions(self) -> Iterable[Tuple[float, float]]:
        """Generate the list of locations within the layout.
        """
        return (
            # (column, row)
            (-1, 0),
            (0, 0),
            (1, 0),
            (2, 0),
            #(3, 0),
        )

    def key_size(self, column: float, row: float) -> float:
        """The bottom key (column 0) is 1.25u wide."""
        return 1.25 if column == 0 else 1.0

    def extra_width(self, column: float, row: float) -> float:
        """How much wider than 1u the key at the given position is (mm)."""
        return (self.key_size(column, row) - 1) * self.unit_width

    def key_angle(self, column: float, row: float) -> float:
        """The angle of the key around the thumb arc (degrees); 0 is the bottom, positive angles go toward -X."""
        return self.column_angle(self.column_adjust(column))

    def flat_width(self, row: float = 0) -> float:
        """Width of the flat strip at the bottom of the arc (mm): the combined extra width of the keys sitting there."""
        return sum(
            self.extra_width(column, key_row)
            for (column, key_row) in self.generate_positions()
            if key_row == row and abs(self.key_angle(column, key_row)) < 1e-9
        )

    def side_shift(self, column: float, row: float) -> float:
        """X shift of the key's side of the arc: the arc is split at the bottom and pulled apart by the flat strip."""
        angle = self.key_angle(column, row)
        if abs(angle) < 1e-9:
            return 0
        return math.copysign(self.flat_width(row) / 2, -angle)

    def placement_adjust(self, column: float, row: float, transform: Transform) -> Transform:
        """Make room for wider keys at the bottom of the arc.

        Keys at the bottom of the circle sit centered on a flat strip as wide as their extra width; the two halves of
        the arc on either side are moved apart by that much.

        :param column: the column to place the key in
        :param row: the row to place the key in
        :param transform: the placement so far
        """
        return transform.translate((self.side_shift(column, row), 0, 0))

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
