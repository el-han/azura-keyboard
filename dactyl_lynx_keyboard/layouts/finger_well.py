"""The layout of a finger well.
"""
import math
import operator
from collections.abc import Iterable
from functools import reduce
from itertools import chain
from typing import Optional, Tuple

from solid2.core.object_base import OpenSCADObject

from spkb.keyswitch import Keyswitch, MX

from .layout import Layout, XYAdjustCallback


class FingerWellLayout(Layout):
    """The layout of a finger well.
    """
    def __init__(self, columns: int = 6, rows: int = 5, use_1_5u_keys: bool = True, keyswitch: Keyswitch = MX()):
        super(FingerWellLayout, self).__init__(columns=columns, rows=rows, keyswitch=keyswitch)

        self.use_1_5u_keys = use_1_5u_keys

        self.placement_transform = (0, 0, 1.6 + 13.0)

        self.positions_to_skip = ((0, 4), (1, 4))

    def column_adjust(self, column: float) -> float:
        """Adjust the effective column number of a given column to account for 1.5u keys on the
        outside columns.

        :param column: the column number to adjust
        """
        if self.use_1_5u_keys and column >= 5:
            return column + (column - 4) * 0.25
        else:
            return column

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

    def placement_adjust(self, column: float, row: float, shape: OpenSCADObject) -> OpenSCADObject:
        """Adjust the position of the given key/location in the layout.

        :param column: the column to place the key in
        :param row: the row to place the key in
        :param shape: the shape to place
        """
        shape = shape.down(self.row_radius)
        shape = shape.rotate(-self.row_angle(3), (1, 0, 0))
        shape = shape.up(self.row_radius)
        shape = shape.translate((0.0, -1*self.offset_per_row, 0.0))

        shape = shape.down(self.column_radius)
        shape = shape.rotate(-self.column_angle(4), (0, 1, 0))
        shape = shape.up(self.column_radius)
        shape = shape.translate((1.5*self.offset_per_col, 0.0, 0.0))

        # shape = shape.rotate(10, (0,0,1))
        
        return shape.translate((0.5*self.offset_per_col, 0.0, 0.0))

    def key_place(self, column: float, row: float, shape: OpenSCADObject) -> OpenSCADObject:
        """Place a key (or other shape) in the layout.

        :param column: the column to place the key in

        :param row: the row to place the key in

        :param shape: the shape to place
        """

        # shift rows for middle finger and pinky
        if column == 2:
            row += -0.25
        elif column >=4:
            row += 0.25

        return super().key_place(column, row, shape)

    def layout_place(self, shape: OpenSCADObject) -> OpenSCADObject:
        """Place the layout.

        :param shape: the shape to place
        """
        return shape \
            .up(self.web_thickness) \
            .translate(self.placement_transform)

    def web_all(self, z_offset: float = 0, thickness: Optional[float] = None, size_adjust: Optional[XYAdjustCallback] = None, position_adjust: Optional[XYAdjustCallback] = None) -> OpenSCADObject:
        """Return the complete "web" between all key positions in this layout.

        :param z_offset: the offset in the Z direction of the corner blocks (before placing at the key positions)
        :param thickness: the thickness of the web; if None, default to self.web_thickness
        :param size_adjust: a callback to adjust the size of the key at this column and row
        :param position_adjust: a callback to adjust the position of the key at this column and row
        """
        web_kwargs = {
            'z_offset': z_offset,
            'thickness': thickness,
            'size_adjust': size_adjust,
            'position_adjust': position_adjust,
        }

        return reduce(
            operator.add,
            chain(
                (
                    self.web_top_left_of(column, row, **web_kwargs)
                    for (column, row) in self.generate_positions()
                    if column > 0 and row > 0 and (column > 2 or row != 4)
                ),
                (
                    self.web_left_of(column, row, **web_kwargs)
                    for (column, row) in self.generate_positions()
                    if column > 0 and (column > 2 or row != 4)
                ),
                (
                    self.web_above(column, row, **web_kwargs)
                    for (column, row) in self.generate_positions()
                    if row > 0
                ),
            )
        )
