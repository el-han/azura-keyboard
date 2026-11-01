"""The layout of a finger well.
"""
import math
from collections.abc import Iterable
from typing import Tuple

from ..components.keyswitch import Keyswitch
from ..geometry.key_layout import KeyLayout
from ..geometry.transform import Transform


class FingerLayout(KeyLayout):
    """The layout of a finger well.
    """
    def __init__(self, columns: int = 6, rows: int = 5, keyswitch: Keyswitch = Keyswitch()):
        super(FingerLayout, self).__init__(columns=columns, rows=rows, keyswitch=keyswitch)

        self.placement_transform = (0, 0, 1.6 + 3.0 + 5.0 + 9.0)

        self.positions_to_skip = ((0, 4), (1, 4), (2, 4))
        "Grid positions without a key: the bottom row under the index and middle fingers, where the thumb goes"

        self.outline_corners = (
            (-0.5, -0.75),
            (-0.5, 3.5),
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
                if column == 2:
                    row += -0.25
                elif column >= 4:
                    row += 0.25
                positions.append((column, row))
        return positions

    def layout_place(self, transform: Transform) -> Transform:
        """Place the layout.

        :param transform: the placement so far
        """
        return transform \
            .up(self.plate_thickness) \
            .translate(self.placement_transform)
