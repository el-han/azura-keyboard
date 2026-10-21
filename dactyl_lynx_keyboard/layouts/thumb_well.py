"""The layout of a thumb well.
"""
import math
import operator
from collections.abc import Iterable
from functools import reduce
from itertools import chain
from typing import Optional, Tuple

from solid2 import hull
from solid2.core.object_base import OpenSCADObject

from spkb.keyswitch import Keyswitch

from .keys import Kailh
from .layout import Layout, XYAdjustCallback


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

        self.placement_transform = (-30, -45, 10)

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

    def placement_adjust(self, column: float, row: float, shape: OpenSCADObject) -> OpenSCADObject:
        """Adjust the position of the given key/location in the layout.

        :param column: the column to place the key in
        :param row: the row to place the key in
        :param shape: the shape to place
        """
        # if (isinstance(row, float) and not row.is_integer()) or (isinstance(column, float) and not column.is_integer()):
        #     return shape.translate((0, 0, -1))
        # else:
        #     return shape
        if column >= 3:
            shape = shape.translate((19*0.25, 0, 0))
        elif column == 2:
            shape = shape.translate((19*0.125, 0, 0.4))
        return shape

    def layout_place(self, shape: OpenSCADObject) -> OpenSCADObject:
        """Place the layout.

        :param shape: the shape to place
        """
        # shape = shape.up(self.row_radius)
        # shape = shape.rotate(90-self.row_angle(0), (1, 0, 0))
        # shape = shape.rotate(self.column_angle(0), (0, 0, 1))
        shape = shape.rotate(15, (0, 0, 1))
        shape = shape.translate(self.placement_transform)
        return shape
